#!/bin/bash
# Environment for building and running CyclesPhi (standalone "cycles" XML renderer, CPU)
# on Karolina CPU nodes. Source it:  source scripts/env_cyclesphi.sh
#
# Toolchain: foss/2025b (GCC 14.3). Third-party libraries (OpenVDB/NanoVDB, OpenImageIO,
# OpenEXR, TBB, Embree, OIDN, OCIO, ...) come from Blender's precompiled Linux library
# bundle (lib-linux_x64, commit pinned by the cyclesphi submodule), copied to
# ${CYCLESPHI_LIBS}.

export OF_WS=/mnt/proj2/eu-25-121/milanjaros/openfoam
export OF_SCRATCH=/scratch/project/eu-25-121/milanjaros/openfoam

# Never write into the real $HOME.
export HOME=${OF_SCRATCH}/fakehome
export XDG_CACHE_HOME=${HOME}/.cache
export XDG_CONFIG_HOME=${HOME}/.config
export XDG_DATA_HOME=${HOME}/.local/share
mkdir -p "${HOME}" "${XDG_CACHE_HOME}" "${XDG_CONFIG_HOME}" "${XDG_DATA_HOME}"

module purge >/dev/null 2>&1
module load foss/2025b
module load CMake/3.31.8-GCCcore-14.3.0
module load Python/3.13.5-GCCcore-14.3.0
export CC=gcc
export CXX=g++

export CYCLESPHI_SRC=${OF_WS}/src/cyclesphi
export CYCLESPHI_BUILD=${OF_WS}/build/cyclesphi_cpu
export CYCLESPHI_INSTALL=${OF_WS}/install/cyclesphi_cpu
export CYCLESPHI_LIBS=${OF_WS}/install/cyclesphi_libs/linux_x64
export CYCLES_BIN=${CYCLESPHI_INSTALL}/cycles

# Runtime libraries (the install step copies most of them into ${CYCLESPHI_INSTALL}/lib,
# the bundle paths are a fallback).
export LD_LIBRARY_PATH=${CYCLESPHI_INSTALL}/lib:${CYCLESPHI_LIBS}/openvdb/lib:${CYCLESPHI_LIBS}/tbb/lib:${CYCLESPHI_LIBS}/openimageio/lib:${LD_LIBRARY_PATH}

# OpenColorIO config (copied from the ppam2026 workflow; "Linear Rec.709" etc.).
export OCIO=${OF_WS}/data/cyclesphi/colormanagement/config.ocio

export OMP_NUM_THREADS=${OMP_NUM_THREADS:-$(nproc)}
