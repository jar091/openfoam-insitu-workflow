#!/bin/bash
# Environment for building and running the cyclesphi-anari ANARI device
# ("cycles" library, CPU only) and the CPU build of deepCompositing
# (libdeepCompositing + the "ptc" compositing ANARI wrapper device).
#
# Usage (inside a Slurm job on a compute node):
#   source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_cyclesphi_anari.sh
#
# Toolchain: foss/2025b (GCC 14.3.0 + OpenMPI 5.0.8). ANARI-SDK is taken from
# install/anari (built by scripts/build_anari.sh). Cycles' third-party
# libraries (OIIO, OCIO, TBB, Embree, OIDN, OpenVDB, ...) come from Blender's
# precompiled Linux library bundle in install/cyclesphi_libs/linux_x64.
# Never writes into the real $HOME: HOME and the XDG dirs point to scratch.

export PROJ_ROOT=/mnt/proj2/eu-25-121/milanjaros/openfoam
export SCRATCH_ROOT=/scratch/project/eu-25-121/milanjaros/openfoam

# --- keep $HOME clean -------------------------------------------------------
export HOME=${SCRATCH_ROOT}/fakehome
export XDG_CACHE_HOME=${HOME}/.cache
export XDG_CONFIG_HOME=${HOME}/.config
export XDG_DATA_HOME=${HOME}/.local/share
export XDG_STATE_HOME=${HOME}/.local/state
mkdir -p "${XDG_CACHE_HOME}" "${XDG_CONFIG_HOME}" "${XDG_DATA_HOME}" "${XDG_STATE_HOME}"

# --- modules -----------------------------------------------------------------
if ! type module >/dev/null 2>&1; then
  source /etc/profile >/dev/null 2>&1
fi
module load foss/2025b
module load CMake/3.31.8-GCCcore-14.3.0
module load Python/3.13.5-GCCcore-14.3.0
export CC=gcc
export CXX=g++

# --- install prefixes --------------------------------------------------------
export ANARI_ROOT=${PROJ_ROOT}/install/anari
export CYCLES_ANARI_ROOT=${PROJ_ROOT}/install/cyclesphi-anari
export DEEPCOMP_ROOT=${PROJ_ROOT}/install/deepcompositing
export CYCLESPHI_LIBS=${PROJ_ROOT}/install/cyclesphi_libs/linux_x64
# Barney (CPU) from scripts/build_barney.sh, optional per-rank renderer
export BARNEY_ROOT=${PROJ_ROOT}/install/barney

export CMAKE_PREFIX_PATH=${DEEPCOMP_ROOT}:${ANARI_ROOT}${CMAKE_PREFIX_PATH:+:${CMAKE_PREFIX_PATH}}
export PATH=${DEEPCOMP_ROOT}/bin:${CYCLES_ANARI_ROOT}/bin:${ANARI_ROOT}/bin${PATH:+:${PATH}}

# libanari_library_cycles.so / libanari_library_ptc.so must be found by
# anariLoadLibrary() (dlopen), plus the Blender bundle libraries the cycles
# device links against (also baked into its RPATH, this is a fallback).
_cyc_libs=""
for _d in tbb openimageio opencolorio openexr imath openvdb embree openimagedenoise \
          osl pugixml jpeg png zlib zstd webp openjph openjpeg; do
  [ -d "${CYCLESPHI_LIBS}/${_d}/lib" ] && _cyc_libs="${_cyc_libs}:${CYCLESPHI_LIBS}/${_d}/lib"
done
export LD_LIBRARY_PATH=${DEEPCOMP_ROOT}/lib64:${DEEPCOMP_ROOT}/lib:${CYCLES_ANARI_ROOT}/lib64:${CYCLES_ANARI_ROOT}/lib:${BARNEY_ROOT}/lib64:${ANARI_ROOT}/lib64:${ANARI_ROOT}/lib${_cyc_libs}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
unset _cyc_libs _d

# --- runtime defaults --------------------------------------------------------
# anariLoadLibrary("cycles") -> CyclesPhi path tracer (CPU)
# anariLoadLibrary("barney_cpu") -> Barney CPU (see scripts/env_anari.sh)
# anariLoadLibrary("ptc")    -> deepCompositing wrapper; the wrapped library is
#                               chosen with PTC_ANARI_LIBRARY (helide, cycles, ...)
export PTC_ANARI_LIBRARY=${PTC_ANARI_LIBRARY:-helide}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-$(nproc)}
