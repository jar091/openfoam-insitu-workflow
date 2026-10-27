#!/bin/bash
# Fast launcher for visualization runs: OpenFOAM v2606 + mesioVDB (Mesio/OpenVDB)
# + anariVis (ANARI/Barney) in one environment, without Lmod in every rank.
# Sources a plain `export -p` dump (runs/of_env_v2606_vis.sh), created once on a
# compute node with
#   srun --jobid=5270670 --overlap -N1 -n1 -w <node> bash \
#        /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/cases/ofexec_vis.sh --mkenv
# (= env_anari_openfoam.sh + MESIO_ROOT/OPENVDB_ROOT as in env_mesio_openfoam.sh).
#
# Usage: srun ... bash ofexec_vis.sh <caseDir> <app> [args...]
#   RENDER_RANK=1 -> unset OMP_NUM_THREADS (in-transit render ranks use all cores)
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
DUMP=/scratch/project/eu-25-121/milanjaros/openfoam/runs/of_env_v2606_vis.sh
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam

if [ "$1" = --mkenv ]; then
    source $PROJ/scripts/env_anari_openfoam.sh >/dev/null 2>&1 || exit 1
    export MESIO_ROOT=$PROJ/install/mesio
    export OPENVDB_ROOT=$PROJ/install/openvdb
    export LD_LIBRARY_PATH=$MESIO_ROOT/lib64:$OPENVDB_ROOT/lib:$LD_LIBRARY_PATH
    export PATH=$OPENVDB_ROOT/bin:$PATH
    export OMP_NUM_THREADS=1
    export -p | grep -vE "^declare -x (SLURM_|SLURMD_|PMIX_|PMI_|OMPI_MCA_orte|SRUN|TMPDIR|HOSTNAME=|PWD=|OLDPWD=|SHLVL=|_=)" > $DUMP
    echo "wrote $DUMP"
    exit 0
fi

source $DUMP
[ "${RENDER_RANK:-0}" = 1 ] && unset OMP_NUM_THREADS
cd "$1" || exit 1
shift
exec "$@"
