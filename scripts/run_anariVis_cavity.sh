#!/bin/bash
# In-situ anariVis test on the icoFoam cavity (64x64x1).
#
#   prepare <case> <nProcs>              (1 task)  copy tutorial, mesh, decompose
#   config  <case> <library> <compositing> [renderRanksPerNode]   (1 task)
#   run     <case>                       (1 task serial, or n tasks with
#                                         srun --mpi=pmix for a decomposed case)
#   env: MPITHREADS=1 -> icoFoam -mpi-threads (MPI_THREAD_MULTIPLE)
#
# Case directory: /scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis/<case>
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

RUNS=/scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis
DATA=/mnt/proj2/eu-25-121/milanjaros/openfoam/data/openfoam/anariVis_cavity
action=$1; name=$2
case_dir=$RUNS/$name

case "$action" in
mkenv)
    mkdir -p "$(dirname "$ENV_CACHE")"
    export -p | grep -v -E ' (SLURM|PMIX|PMI|OMPI|PRTE|HOSTNAME|SRUN|TMPDIR)' > "$ENV_CACHE"
    echo "wrote $ENV_CACHE"
    ;;
prepare)
    np=${3:-1}
    rm -rf "$case_dir"; mkdir -p "$RUNS"
    cp -r "$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity" "$case_dir"
    cd "$case_dir"
    sed -i 's/(20 20 1)/(64 64 1)/' system/blockMeshDict
    cp "$DATA/controlDict" "$DATA/anariVisDict" system/
    blockMesh > log.blockMesh 2>&1
    if [ "$np" -gt 1 ]; then
        cat > system/decomposeParDict <<EOF
FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }
numberOfSubdomains $np;
method scotch;
EOF
        decomposePar -force > log.decomposePar 2>&1
    fi
    echo "prepared $case_dir"
    ;;
config)
    lib=${3:-barney_cpu}; comp=${4:-auto}; rpn=${5:-1}
    cd "$case_dir"
    sed -i "s/^\(    library *\).*;/\1$lib;/; s/^\(    compositing *\).*;/\1$comp;/; s/^\(    renderRanksPerNode *\).*;/\1$rpn;/" system/anariVisDict
    sed -i "s|^\(    outputDir *\).*;|\1\"<case>/images_${lib}_${comp}_rpn${rpn}${TAG:-}\";|" system/anariVisDict
    grep -E "^    (library|compositing|renderRanksPerNode|outputDir)" system/anariVisDict
    ;;
run)
    cd "$case_dir"
    extra=""
    [ "${MPITHREADS:-0}" = 1 ] && extra="-mpi-threads"
    if [ -d processor0 ]; then
        exec icoFoam -parallel $extra
    else
        exec icoFoam $extra
    fi
    ;;
*)
    echo "usage: $0 prepare|config|run <case> ..." 1>&2; exit 1 ;;
esac
