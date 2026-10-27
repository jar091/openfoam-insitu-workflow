#!/bin/bash
# cavity3D (1M, 128 ranks) anariVis experiments. Run from the login node;
# every step is an srun into job 5270670.
#
#   bash scripts/test_anariVis_cavity3D.sh <experiment> [<experiment> ...]
#
# experiment = mode:library:compositing:rpn[:opt[,opt]]
#   mode  off | inSitu | inTransit
#   opts  mt      -> icoFoam -mpi-threads (in-situ)
#         block   -> dropPolicy block (in-transit)
#         2n      -> in-situ on 2 nodes (SIM2_NODES, 64 ranks per node)
#         rN      -> in-transit with N render ranks (one per node of RENDER_NODES)
#
# env: CASE (c3d_1M), SIM_NODE (cn627), SIM2_NODES (cn629,cn630),
#      RENDER_NODES (cn651,cn652,cn653,cn654,cn655), NP (128)
JOB=${JOB:-5270670}
CASE=${CASE:-c3d_1M}
NP=${NP:-128}
SIM_NODE=${SIM_NODE:-cn627}
SIM2_NODES=${SIM2_NODES:-cn629,cn630}
RENDER_NODES=${RENDER_NODES:-cn651,cn652,cn653,cn654,cn655}
R=/mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/run_anariVis_cavity3D.sh
RUNS=/scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis
L=$RUNS/logs
mkdir -p "$L"

for e in "$@"; do
    IFS=: read -r mode lib comp rpn opts <<< "$e"
    mt=0; block=0; twonodes=0; nrender=2
    IFS=, read -ra ol <<< "$opts"
    for o in "${ol[@]}"; do
        case $o in
            mt) mt=1 ;;
            block) block=1 ;;
            2n) twonodes=1 ;;
            r[0-9]*) nrender=${o#r} ;;
        esac
    done
    tag=${mode}_${lib}_${comp}_rpn${rpn}${opts:+_${opts//,/_}}
    [ "$mode" = inTransit ] && tag=${mode}_${lib}_${comp}_r${nrender}${block:+}$( [ $block = 1 ] && echo _block )
    TAG=$( [ "$mode" = inTransit ] && echo "_r${nrender}$( [ $block = 1 ] && echo _block )" || echo "${opts:+_${opts//,/_}}" )

    # configure (one task on the simulation node)
    TAG=$TAG srun --jobid=$JOB --overlap -N1 -n1 -c 2 -w $SIM_NODE \
        bash $R config $CASE $mode ${lib:-barney_cpu} ${comp:-auto} ${rpn:-1} > /dev/null
    pol=drop; [ $block = 1 ] && pol=block
    srun --jobid=$JOB --overlap -N1 -n1 -c 2 -w $SIM_NODE bash -c \
        "sed -i 's/^\(    dropPolicy *\).*;/\1$pol;/' $RUNS/$CASE/system/anariVisDict"

    log=$L/${CASE}_$tag.log
    start=$(date +%s)
    if [ "$mode" = inTransit ]; then
        rnodes=$(echo $RENDER_NODES | cut -d, -f1-$nrender)
        timeout 3600 srun --jobid=$JOB --overlap --mpi=pmix \
            -N1 -n$NP -w $SIM_NODE bash $R runsim $CASE \
            : -N$nrender -n$nrender --ntasks-per-node=1 -w $rnodes bash $R render $CASE \
            > $log 2>&1
    elif [ $twonodes = 1 ]; then
        MPITHREADS=$mt timeout 3600 srun --jobid=$JOB --overlap --mpi=pmix \
            -N2 -n$NP --ntasks-per-node=$((NP/2)) -w $SIM2_NODES bash $R run $CASE > $log 2>&1
    else
        MPITHREADS=$mt timeout 3600 srun --jobid=$JOB --overlap --mpi=pmix \
            -N1 -n$NP -w $SIM_NODE bash $R run $CASE > $log 2>&1
    fi
    rc=$?
    echo "== $tag rc=$rc wall=$(( $(date +%s) - start ))s log=$log"
    grep -E "^ExecutionTime" $log | tail -1
    grep -E "^anariVis anariVis: (mode|[0-9]+ frames)|^anariVisRender: ([0-9]+ frames|render ranks)|FATAL|ERROR" $log | head -6
done
