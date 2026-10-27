#!/bin/bash
# Environment for building and using Mesio (ESPRESO, branch sc22) with OpenVDB output.
# Toolchain: foss/2025b (GCC 14.3.0 + OpenMPI 5.0.8) - must match the OpenFOAM v2606 build.
#
# Usage:  source scripts/env_mesio.sh
#
# Never writes into $HOME: HOME and all caches are redirected to scratch.

PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
SCRATCH=/scratch/project/eu-25-121/milanjaros/openfoam

export HOME=${SCRATCH}/fakehome
export XDG_CACHE_HOME=${HOME}/.cache
export XDG_CONFIG_HOME=${HOME}/.config
export XDG_DATA_HOME=${HOME}/.local/share
export PIP_CACHE_DIR=${HOME}/.cache/pip
export PYTHONUSERBASE=${HOME}/.local
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "${XDG_CACHE_HOME}" "${XDG_CONFIG_HOME}" "${XDG_DATA_HOME}"

# --- modules ---------------------------------------------------------------
if ! type module >/dev/null 2>&1; then
    source /etc/profile.d/z00_lmod.sh 2>/dev/null || source ${MODULESHOME:-/apps/all/Lmod/8.7.37/lmod/lmod}/init/bash
fi
module purge >/dev/null 2>&1
module load foss/2025b \
            CMake/3.31.8-GCCcore-14.3.0 \
            Python/3.13.5-GCCcore-14.3.0 \
            Boost/1.88.0-GCC-14.3.0 \
            zlib/1.3.1-GCCcore-14.3.0

# --- install prefixes --------------------------------------------------------
# OpenVDB together with its self-built dependencies (oneTBB, c-blosc).
export OPENVDB_ROOT=${PROJ}/install/openvdb
# Mesio libraries, API header and the mesio executable.
# MESIO_VARIANT selects a separate install/build pair, so a development build never
# overwrites the production one:  ""  -> install/mesio,     build/espreso      (default)
#                                 dev -> install/mesio-dev, build/espreso-dev
#                                next -> install/mesio-next, build/espreso-next
#                           asan-next -> install/mesio-asan-next, ...       (any name works)
export MESIO_VARIANT=${MESIO_VARIANT:-}
export MESIO_ROOT=${PROJ}/install/mesio${MESIO_VARIANT:+-${MESIO_VARIANT}}
export ESPRESO_SRC=${PROJ}/src/espreso
export ESPRESO_BUILD=${PROJ}/build/espreso${MESIO_VARIANT:+-${MESIO_VARIANT}}

export CMAKE_PREFIX_PATH=${OPENVDB_ROOT}${CMAKE_PREFIX_PATH:+:${CMAKE_PREFIX_PATH}}
# waf checks for <openvdb/openvdb.h>, -lopenvdb and -ltbb via the default compiler search paths.
export CPATH=${OPENVDB_ROOT}/include${CPATH:+:${CPATH}}
export LIBRARY_PATH=${OPENVDB_ROOT}/lib64:${OPENVDB_ROOT}/lib${LIBRARY_PATH:+:${LIBRARY_PATH}}
export LD_LIBRARY_PATH=${MESIO_ROOT}/lib64:${OPENVDB_ROOT}/lib64:${OPENVDB_ROOT}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
export PATH=${MESIO_ROOT}/bin:${OPENVDB_ROOT}/bin:${PATH}

# ESPRESO compiler selection (wscript reads MPICXX / CXX)
export MPICXX=mpic++
export CXX=g++

# Threading (mesio uses OpenMP + one asynchronous output thread)
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
export MKL_NUM_THREADS=1
export SOLVER_NUM_THREADS=${OMP_NUM_THREADS}
export PAR_NUM_THREADS=${OMP_NUM_THREADS}
