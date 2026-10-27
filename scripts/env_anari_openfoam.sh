#!/bin/bash
# Environment for building and running the anariVis OpenFOAM function object
# (src/openfoam-insitu-modules/anariVis) and the in-transit renderer anariVisRender.
#
# Usage (bash, on a compute node inside the job):
#   source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_anari_openfoam.sh
#
# = OpenFOAM v2606 environment (scripts/env_openfoam.sh, foss/2025b)
# + ANARI-SDK, Barney (CPU), deepCompositing (CPU, ptc device) and
#   cyclesphi-anari libraries on LD_LIBRARY_PATH for anariLoadLibrary().
# Never writes into the real $HOME (HOME -> scratch fakehome).

_AV_PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam

# shellcheck disable=SC1091
source "$_AV_PROJ/scripts/env_openfoam.sh" >/dev/null 2>&1 || {
    echo "env_anari_openfoam.sh: sourcing env_openfoam.sh failed" 1>&2
    return 1 2>/dev/null || exit 1
}

export ANARI_ROOT=$_AV_PROJ/install/anari
export BARNEY_ROOT=$_AV_PROJ/install/barney
export DEEPCOMP_ROOT=$_AV_PROJ/install/deepcompositing
export CYCLES_ANARI_ROOT=$_AV_PROJ/install/cyclesphi-anari

# Build output of the module (wmake, see src/openfoam-insitu-modules/anariVis/Allwmake)
export ANARIVIS_ROOT=$_AV_PROJ/install/openfoam-modules/$WM_OPTIONS
export ANARIVIS_LIBBIN=$ANARIVIS_ROOT/lib
export ANARIVIS_BINDIR=$ANARIVIS_ROOT/bin

# ANARI device libraries are dlopen()ed by name (libanari_library_<name>.so).
# The cycles device finds its Blender bundle libraries through its RPATH.
export LD_LIBRARY_PATH=$ANARIVIS_LIBBIN:$ANARI_ROOT/lib64:$BARNEY_ROOT/lib64:$DEEPCOMP_ROOT/lib64:$CYCLES_ANARI_ROOT/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PATH=$ANARIVIS_BINDIR${PATH:+:$PATH}

# Blender library bundle of the cycles device: most libraries are found via
# its RPATH, a few transitive ones (e.g. libopenjph) only through
# LD_LIBRARY_PATH. Appended at the END so they do not shadow the system
# libraries OpenFOAM uses.
_AV_CYC=$_AV_PROJ/install/cyclesphi_libs/linux_x64
for _d in tbb openimageio opencolorio openexr imath openvdb embree openimagedenoise \
          osl pugixml jpeg png zlib zstd webp openjph openjpeg; do
    [ -d "$_AV_CYC/$_d/lib" ] && LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$_AV_CYC/$_d/lib
done
export LD_LIBRARY_PATH
unset _AV_CYC _d

# ptc (deepCompositing wrapper) default wrapped library
export PTC_ANARI_LIBRARY=${PTC_ANARI_LIBRARY:-helide}

unset _AV_PROJ
