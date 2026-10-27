#!/bin/bash
# Same as ofexec_vis.sh (OpenFOAM v2606 + mesioVDB + anariVis environment from the
# runs/of_env_v2606_vis.sh dump), but with the development Mesio build:
#   install/mesio-dev/lib64                       (libmesioapi.so, libnb*.so)
#   install/openfoam-modules-mesio-dev/lib        (libmesioFoam.so built against mesio-dev)
# are put first in LD_LIBRARY_PATH, so 'libs (mesioFoam);' loads the dev function object
# and the dev Mesio libraries (the production libraries have RUNPATH, not RPATH, so the
# LD_LIBRARY_PATH order wins).
#
# Usage: srun ... bash ofexec_vis_mesiodev.sh <caseDir> <app> [args...]
#   MESIO_DEV_ROOT / MESIO_DEV_FOLIB override the two directories.
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
DUMP=/scratch/project/eu-25-121/milanjaros/openfoam/runs/of_env_v2606_vis.sh
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam

source $DUMP
[ "${RENDER_RANK:-0}" = 1 ] && unset OMP_NUM_THREADS
export MESIO_ROOT=${MESIO_DEV_ROOT:-$PROJ/install/mesio-dev}
MESIO_DEV_FOLIB=${MESIO_DEV_FOLIB:-$PROJ/install/openfoam-modules-mesio-dev/lib}
export LD_LIBRARY_PATH=$MESIO_DEV_FOLIB:$MESIO_ROOT/lib64:$LD_LIBRARY_PATH
cd "$1" || exit 1
shift
exec "$@"
