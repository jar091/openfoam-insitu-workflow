#!/bin/bash
# Build and install ANARI-SDK (src/ANARI-SDK) into install/anari with foss/2025b.
# Builds: libanari, helium, helide (Embree CPU reference device), debug/sink
# devices, the simple examples (anariTutorial*, anariInfo, and the MPI
# anariDistributedTutorial). No GUI viewer.
#
# Run on a compute node, e.g.:
#   srun --jobid=<JOB> --overlap -N1 -n1 -w <node> bash scripts/build_anari.sh
set -euo pipefail

source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_anari.sh

SRC=${PROJ_ROOT}/src/ANARI-SDK
BLD=${PROJ_ROOT}/build/anari
NPROC=${NPROC:-64}

cmake -S "${SRC}" -B "${BLD}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${ANARI_ROOT}" \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DBUILD_SHARED_LIBS=ON \
  -DBUILD_TESTING=OFF \
  -DBUILD_EXAMPLES=ON \
  -DBUILD_VIEWER=OFF \
  -DBUILD_HELIDE_DEVICE=ON \
  -DBUILD_HELIDE_GPU_DEVICE=OFF \
  -DBUILD_REMOTE_DEVICE=OFF \
  -DBUILD_CTS=OFF \
  -DBUILD_CAT=OFF \
  -DUSE_MPI=ON \
  -DINSTALL_VIEWER_LIBRARY=OFF

cmake --build "${BLD}" -j "${NPROC}"
cmake --install "${BLD}"

# The simple examples are not all installed by the SDK; copy the useful ones.
mkdir -p "${ANARI_ROOT}/bin"
for exe in anariTutorial anariTutorialCpp anariDistributedTutorial anariInfo; do
  f=$(find "${BLD}" -type f -name "${exe}" -perm -u+x | head -1)
  [ -n "${f}" ] && cp -f "${f}" "${ANARI_ROOT}/bin/"
done
echo "ANARI-SDK installed into ${ANARI_ROOT}"
