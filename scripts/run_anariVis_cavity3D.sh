#!/bin/bash
# anariVis on the HPC committee cavity3D case (icoFoam, 1M or 8M cells).
#
#   prepare <case> <1M|8M> <nProcs> [endTime]       (1 task)
#   config  <case> <inSitu|inTransit|off> <library> <compositing> [renderRanksPerNode]
#                                                   (1 task; TAG env -> image dir suffix)
#   run     <case>        (all tasks of an srun --mpi=pmix step; solver only)
#   runsim  <case>        (solver part of an MPMD in-transit step: -world sim)
#   render  <case>        (renderer part of an MPMD in-transit step: -world render)
#   env: MPITHREADS=1 -> -mpi-threads for icoFoam (in-situ Barney)
#
# Case dir: /scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis/<case>
set -e
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
# Sourcing the module environment in every rank of a 128-rank step costs
# minutes (Lmod on NFS); use a cached dump if available (action mkenv)
ENV_CACHE=/scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis/env_cache.sh
if [ "$1" != mkenv ] && [ -f "$ENV_CACHE" ]; then
    source "$ENV_CACHE"
else
    source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_anari_openfoam.sh
fi

PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
RUNS=/scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis
DATA=$PROJ/data/openfoam/anariVis_cavity3D
action=$1; name=$2
case_dir=$RUNS/$name

case "$action" in
mkenv)
    mkdir -p "$(dirname "$ENV_CACHE")"
    export -p | grep -v -E ' (SLURM|PMIX|PMI|OMPI|PRTE|HOSTNAME|SRUN|TMPDIR)' > "$ENV_CACHE"
    echo "wrote $ENV_CACHE"
    ;;
prepare)
    size=${3:-1M}; np=${4:-128}; endTime=${5:-0.2}
    rm -rf "$case_dir"; mkdir -p "$RUNS"
    cp -r "$PROJ/src/hpc/incompressible/icoFoam/cavity3D/$size/fixedIter" "$case_dir"
    cd "$case_dir"
    sed -i "s/^numberOfSubdomains .*/numberOfSubdomains $np;/" system/decomposeParDict
    sed -i "s/^endTime .*/endTime         $endTime;/; s/^writeFormat .*/writeFormat     binary;/; s/^runTimeModifiable .*/runTimeModifiable false;/" system/controlDict
    sed -i 's|^// \*\*\*\*\*.*$||' system/controlDict
    printf 'functions\n{\n    #include "functions"\n}\n' >> system/controlDict
    cp "$DATA/functions" "$DATA/anariVisDict" system/
    blockMesh > log.blockMesh 2>&1
    decomposePar -force > log.decomposePar 2>&1
    echo "prepared $case_dir ($size, $np ranks, endTime $endTime)"
    ;;
config)
    mode=${3:-inSitu}; lib=${4:-barney_cpu}; comp=${5:-auto}; rpn=${6:-1}
    cd "$case_dir"
    if [ "$mode" = off ]; then
        echo '// all function objects disabled' > system/functions.off
        sed -i 's|#include "functions.*"|#include "functions.off"|' system/controlDict
        echo "functions disabled"; exit 0
    fi
    sed -i 's|#include "functions.*"|#include "functions"|' system/controlDict
    sed -i "s/^\(    mode *\).*;/\1$mode;/; s/^\(    library *\).*;/\1$lib;/; s/^\(    compositing *\).*;/\1$comp;/; s/^\(    renderRanksPerNode *\).*;/\1$rpn;/" system/anariVisDict
    sed -i "s|^\(    outputDir *\).*;|\1\"<case>/images_${mode}_${lib}_${comp}_rpn${rpn}${TAG:-}\";|" system/anariVisDict
    grep -E "^    (mode|library|compositing|renderRanksPerNode|outputDir) " system/anariVisDict
    ;;
run)
    cd "$case_dir"
    extra=""; [ "${MPITHREADS:-0}" = 1 ] && extra="-mpi-threads"
    exec icoFoam -parallel $extra
    ;;
runsim)
    cd "$case_dir"
    exec icoFoam -parallel -world sim
    ;;
render)
    cd "$case_dir"
    exec anariVisRender -parallel -world render -mpi-threads ${RENDER_THREADS:+-threads $RENDER_THREADS}
    ;;
*)
    echo "usage: $0 prepare|config|run|runsim|render <case> ..." 1>&2; exit 1 ;;
esac
