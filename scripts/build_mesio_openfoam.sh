#!/bin/bash
# Build libmesioFoam.so (mesioVDB function object).
#   MESIO_VARIANT=""   (default) against install/mesio     -> $FOAM_USER_LIBBIN (production)
#   MESIO_VARIANT=dev            against install/mesio-dev -> install/openfoam-modules-mesio-dev/lib
#   MESIO_VARIANT=next           against install/mesio-next -> install/openfoam-modules-mesio-next/lib
#                                (the current sources need the in-situ API version 2, i.e.
#                                 a Mesio install built from the current src/espreso tree)
#                                (built from a copy of the sources in
#                                 build/openfoam-modules-mesio-dev/mesioFoam, so the production
#                                 objects in src/.../Make/<WM_OPTIONS> are not touched)
# Run on a compute node, e.g.
#   srun --jobid=5270670 --overlap -N1 -n1 -c 16 -w cn356 \
#       bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/build_mesio_openfoam.sh \
#       > /mnt/proj2/eu-25-121/milanjaros/openfoam/build/logs/mesio_openfoam_build.log 2>&1
set -e
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
# shellcheck disable=SC1091
source "$PROJ/scripts/env_mesio_openfoam.sh" >/dev/null 2>&1
echo "MESIO_VARIANT='$MESIO_VARIANT' MESIO_ROOT=$MESIO_ROOT"
SRC="$PROJ/src/openfoam-insitu-modules/mesioFoam"
if [ -n "$MESIO_VARIANT" ]
then
    mkdir -p "$MESIO_FOAM_LIBBIN"
    # Make/files: LIB = $(FOAM_USER_LIBBIN)/libmesioFoam
    export FOAM_USER_LIBBIN="$MESIO_FOAM_LIBBIN"
    # wmake keeps objects in <source>/Make/<WM_OPTIONS> for modules outside WM_PROJECT_DIR
    BUILDSRC="$PROJ/build/openfoam-modules-mesio-$MESIO_VARIANT/mesioFoam"
    mkdir -p "$BUILDSRC"
    rsync -a --delete --exclude "Make/$WM_OPTIONS" --exclude lnInclude "$SRC/" "$BUILDSRC/"
    SRC="$BUILDSRC"
fi
echo "FOAM_USER_LIBBIN=$FOAM_USER_LIBBIN, sources $SRC"
"$SRC/Allwmake" "$@"
ls -l "$FOAM_USER_LIBBIN/libmesioFoam.so"
ldd "$FOAM_USER_LIBBIN/libmesioFoam.so" | grep -E "mesio|openvdb|mpi|not found" || true
