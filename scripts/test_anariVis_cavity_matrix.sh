#!/bin/bash
# Phase 1/2 test matrix on the 64x64 cavity (in-situ). Run from the login
# node; every step is an srun into job 5270670 on node $NODE.
#   NODE=cn629 NP=8 bash scripts/test_anariVis_cavity_matrix.sh [configs...]
# config = lib:compositing:renderRanksPerNode[:mt]   (mt -> -mpi-threads)
JOB=${JOB:-5270670}; NODE=${NODE:-cn629}; NP=${NP:-8}; NAME=${NAME:-cav_par$NP}
R=/mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/run_anariVis_cavity.sh
L=/scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis/logs
mkdir -p $L
configs=("$@")
[ ${#configs[@]} -eq 0 ] && configs=(barney_cpu:auto:4:mt barney_cpu:auto:4 helide:deep:4 ptc:ptc:4 cycles:deep:4 barney_cpu:deep:4:mt helide:none:1)

if [ "${PREPARE:-0}" = 1 ] || [ ! -d /scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis/$NAME ]; then
    srun --jobid=$JOB --overlap -N1 -n1 -c 16 -w $NODE bash $R prepare $NAME $NP > $L/${NAME}_prepare.log 2>&1
fi
for c in "${configs[@]}"; do
    IFS=: read -r lib comp rpn mt <<< "$c"
    tag=${lib}_${comp}_rpn${rpn}${mt:+_mt}
    TAG=${mt:+_mt} srun --jobid=$JOB --overlap -N1 -n1 -c 4 -w $NODE bash $R config $NAME $lib $comp $rpn > /dev/null 2>&1
    MT=0; [ "$mt" = mt ] && MT=1
    start=$(date +%s)
    if [ "$NP" -gt 1 ]; then
        MPITHREADS=$MT timeout 1800 srun --jobid=$JOB --overlap --mpi=pmix -N1 -n$NP -w $NODE \
            bash $R run $NAME > $L/${NAME}_$tag.log 2>&1
    else
        MPITHREADS=$MT timeout 1800 srun --jobid=$JOB --overlap -N1 -n1 -c 128 -w $NODE \
            bash $R run $NAME > $L/${NAME}_$tag.log 2>&1
    fi
    rc=$?
    echo "== $tag rc=$rc wall=$(( $(date +%s) - start ))s"
    grep -E "^anariVis anariVis: (mode|[0-9]+ frames)|FATAL|ERROR" $L/${NAME}_$tag.log | head -5
done
