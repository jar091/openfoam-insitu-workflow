#!/bin/bash
# Environment for building and running ANARI-SDK + Barney (CPU/Embree backend)
# with the project toolchain foss/2025b (GCC 14.3.0 + OpenMPI 5.0.8).
#
# Usage (inside a Slurm job on a compute node):
#   source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_anari.sh
#
# Never writes into the real $HOME: HOME and the XDG dirs point to scratch.

export PROJ_ROOT=/mnt/proj2/eu-25-121/milanjaros/openfoam
export SCRATCH_ROOT=/scratch/project/eu-25-121/milanjaros/openfoam

# --- keep $HOME clean -------------------------------------------------------
export HOME=${SCRATCH_ROOT}/fakehome
export XDG_CACHE_HOME=${HOME}/.cache
export XDG_CONFIG_HOME=${HOME}/.config
export XDG_DATA_HOME=${HOME}/.local/share
export XDG_STATE_HOME=${HOME}/.local/state
export PIP_CACHE_DIR=${XDG_CACHE_HOME}/pip
export PYTHONUSERBASE=${HOME}/.local
mkdir -p "${XDG_CACHE_HOME}" "${XDG_CONFIG_HOME}" "${XDG_DATA_HOME}" "${XDG_STATE_HOME}"

# --- modules -----------------------------------------------------------------
if ! type module >/dev/null 2>&1; then
  source /etc/profile >/dev/null 2>&1
fi
module load foss/2025b
module load CMake/3.31.8-GCCcore-14.3.0
module load Python/3.13.5-GCCcore-14.3.0
module load git/2.50.1-GCCcore-14.3.0 2>/dev/null || true

# --- install prefixes --------------------------------------------------------
export ANARI_ROOT=${PROJ_ROOT}/install/anari
export BARNEY_ROOT=${PROJ_ROOT}/install/barney

export CMAKE_PREFIX_PATH=${BARNEY_ROOT}:${ANARI_ROOT}${CMAKE_PREFIX_PATH:+:${CMAKE_PREFIX_PATH}}
export PATH=${ANARI_ROOT}/bin:${BARNEY_ROOT}/bin${PATH:+:${PATH}}
export LD_LIBRARY_PATH=${BARNEY_ROOT}/lib64:${BARNEY_ROOT}/lib:${ANARI_ROOT}/lib64:${ANARI_ROOT}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

# --- runtime defaults --------------------------------------------------------
# ANARI library to load for apps using anariLoadLibrary("environment"):
#   barney_cpu  -> Barney Embree/CPU backend only (recommended on CPU nodes)
#   barney      -> Barney multi-backend loader (picks first available backend)
#   helide      -> ANARI-SDK reference CPU device
export ANARI_LIBRARY=${ANARI_LIBRARY:-barney_cpu}
# Optional: cap the Embree/Barney CPU worker threads per process, e.g.
#   export BARNEY_MAX_CPU_THREADS=64
