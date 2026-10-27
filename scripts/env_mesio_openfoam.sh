# Environment for building and running the mesioVDB OpenFOAM function object
# (libmesioFoam, src/openfoam-insitu-modules/mesioFoam).
#
# Usage (bash, on a compute node):
#     source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_mesio_openfoam.sh
#
# = env_openfoam.sh (foss/2025b, OpenFOAM v2606, HOME redirected to scratch)
# + MESIO_ROOT / OPENVDB_ROOT (Mesio in-situ API and OpenVDB 12, same
#   toolchain) + OMP_NUM_THREADS=1 (Mesio uses OpenMP inside every MPI rank).
# The library itself carries RPATHs to Mesio and OpenVDB; the
# LD_LIBRARY_PATH/PATH additions are for vdb_print and other tools.

_MOF_ROOT=/mnt/proj2/eu-25-121/milanjaros/openfoam

# shellcheck disable=SC1091
. "$_MOF_ROOT/scripts/env_openfoam.sh" || return 1 2>/dev/null || exit 1

# MESIO_VARIANT selects the Mesio build and the matching libmesioFoam:
#   ""  (default) -> install/mesio,     libmesioFoam in $FOAM_USER_LIBBIN (production)
#   dev           -> install/mesio-dev, libmesioFoam in install/openfoam-modules-mesio-dev/lib
#   next          -> install/mesio-next, libmesioFoam in install/openfoam-modules-mesio-next/lib
# (any other name works the same way). The variant's function-object directory is put
# first in LD_LIBRARY_PATH, so 'libs (mesioFoam);' loads the matching library.
export MESIO_VARIANT="${MESIO_VARIANT:-}"
export MESIO_ROOT="$_MOF_ROOT/install/mesio${MESIO_VARIANT:+-$MESIO_VARIANT}"
export OPENVDB_ROOT="$_MOF_ROOT/install/openvdb"
export LD_LIBRARY_PATH="$MESIO_ROOT/lib64:$OPENVDB_ROOT/lib:$LD_LIBRARY_PATH"
if [ -n "$MESIO_VARIANT" ]
then
    export MESIO_FOAM_LIBBIN="$_MOF_ROOT/install/openfoam-modules-mesio-$MESIO_VARIANT/lib"
    export LD_LIBRARY_PATH="$MESIO_FOAM_LIBBIN:$LD_LIBRARY_PATH"
else
    export MESIO_FOAM_LIBBIN="$FOAM_USER_LIBBIN"
fi
export PATH="$OPENVDB_ROOT/bin:$PATH"

# One OpenMP thread per MPI rank inside Mesio (unless set explicitly)
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

unset _MOF_ROOT
