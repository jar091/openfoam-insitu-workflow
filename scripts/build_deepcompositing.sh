#!/bin/bash
# Build and install the CPU (host, C++/OpenMP + plain MPI) version of
# deepCompositing (src/deepCompositing, CMake option DC_CPU=ON) into
# install/deepcompositing:
#   lib64/libdeepCompositing.so         compositing library
#   lib64/libanari_library_ptc.so       'ptc' ANARI wrapper device (renders with a
#                                       wrapped ANARI library, composites over MPI)
#   include/deepCompositing/*.h         public headers (deepCompositing.h, dcConfig.h, ...)
#   lib64/cmake/deepCompositing         CMake package (target deepCompositing::deepCompositing)
#   bin/testDeepOffline, dcGenTestData, dcAnariDataParallel   tests/samples
#
# Run on a compute node, e.g.:
#   srun --jobid=<JOB> --overlap -N1 -n1 -w <node> \
#     bash scripts/build_deepcompositing.sh > build/logs/deepcompositing_build.log 2>&1
# Options (env): CLEAN=1 removes the build dir first; JOBS=<n> parallel jobs.
set -euo pipefail

source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_cyclesphi_anari.sh

JOBS=${JOBS:-32}
SRC=${PROJ_ROOT}/src/deepCompositing
BLD=${PROJ_ROOT}/build/deepcompositing

[ "${CLEAN:-0}" = "1" ] && rm -rf "${BLD}"

cmake -S "${SRC}" -B "${BLD}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${DEEPCOMP_ROOT}" \
  -DCMAKE_PREFIX_PATH="${ANARI_ROOT}" \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_INSTALL_RPATH="\$ORIGIN/../lib64;${ANARI_ROOT}/lib64" \
  -DDC_CPU=ON \
  -DDC_BUILD_SHARED=ON \
  -DDC_BUILD_ANARI=ON

cmake --build "${BLD}" -j "${JOBS}"
cmake --install "${BLD}"

echo "deepCompositing (CPU) installed into ${DEEPCOMP_ROOT}"
ls -l "${DEEPCOMP_ROOT}"/lib64 "${DEEPCOMP_ROOT}"/bin
