#!/bin/bash
# Same as ofexec_vis.sh (OpenFOAM v2606 + mesioVDB + anariVis environment from the
# runs/of_env_v2606_vis.sh dump), but with the 'next' Mesio build (FPE fix, error codes,
# several mesioVDB instances, cell sampling, units metadata):
#   install/mesio-next/lib64                       (libmesioapi.so, libnb*.so)
#   install/openfoam-modules-mesio-next/lib        (libmesioFoam.so built against mesio-next)
# are put first in LD_LIBRARY_PATH, so 'libs (mesioFoam);' loads the next function object
# and the next Mesio libraries (the production libraries have RUNPATH, not RPATH, so the
# LD_LIBRARY_PATH order wins).
#
# Usage: srun ... bash ofexec_vis_mesionext.sh <caseDir> <app> [args...]
#   MESIO_NEXT_ROOT / MESIO_NEXT_FOLIB override the two directories.
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
DUMP=/scratch/project/eu-25-121/milanjaros/openfoam/runs/of_env_v2606_vis.sh
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam

source $DUMP
[ "${RENDER_RANK:-0}" = 1 ] && unset OMP_NUM_THREADS
export MESIO_ROOT=${MESIO_NEXT_ROOT:-$PROJ/install/mesio-next}
MESIO_NEXT_FOLIB=${MESIO_NEXT_FOLIB:-$PROJ/install/openfoam-modules-mesio-next/lib}
export LD_LIBRARY_PATH=$MESIO_NEXT_FOLIB:$MESIO_ROOT/lib64:$LD_LIBRARY_PATH
cd "$1" || exit 1
shift
exec "$@"
