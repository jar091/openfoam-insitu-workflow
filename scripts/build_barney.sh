#!/bin/bash
# Build and install NVIDIA Barney (src/barney) as an ANARI device for CPU-only
# nodes, using the Embree CPU backend, with MPI (data-parallel) support.
#
# CPU rendering is enabled by:
#   -DBARNEY_BACKEND_CPU=ON     (Embree/CPU rtcore backend, "barney_cpu")
#   -DBARNEY_BACKEND_OPTIX=OFF  (default ON; would require CUDA + OptiX)
#   -DBARNEY_BACKEND_CUDA=OFF
#   -DBARNEY_MPI=ON             (adds the "mpi" ANARI device subtype,
#                                MPIContext/DistFB compositing)
# Embree 4.4 is built (static, namespace embree_for_barney) from the barney
# submodule (no Embree module exists for GCCcore-14.3.0). Only the SSE4.2 ISA
# is enabled: enabling AVX2 (-DEMBREE_ISA_AVX2=ON) builds, but the resulting
# library fails to load with 'undefined symbol embree::CurveNi<8>::Type::name'
# because barney forces EMBREE_GEOMETRY_CURVE=OFF (normal variable, cannot be
# overridden from the command line) while the 8-wide BVH factory still
# references curve primitives. Fixing that needs a source change in
# barney/rtcore/cpu/CMakeLists.txt (enable curves or patch embree).
#
# Produces in install/barney/lib64 (or ${BARNEY_PREFIX}/lib64):
#   libanari_library_barney_cpu.so   -> ANARI library name "barney_cpu"
#   libanari_library_barney.so       -> ANARI library name "barney" (multi-
#                                       backend loader; here only CPU inside)
#
# Run on a compute node, e.g.:
#   srun --jobid=<JOB> --overlap -N1 -n1 -w <node> bash scripts/build_barney.sh
set -euo pipefail

source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_anari.sh

REPO=${PROJ_ROOT}/src/barney
BLD=${BARNEY_BUILD_DIR:-${PROJ_ROOT}/build/barney_cpu}
# Install prefix (default install/barney from env_anari.sh). Use e.g.
#   BARNEY_PREFIX=${PROJ_ROOT}/install/barney-head \
#   BARNEY_BUILD_DIR=${PROJ_ROOT}/build/barney-head bash scripts/build_barney.sh
# to build/install side by side without touching install/barney.
PREFIX=${BARNEY_PREFIX:-${BARNEY_ROOT}}
NPROC=${NPROC:-64}

# Submodules needed for the CPU build (optix is not needed).
if [ ! -f "${REPO}/submodules/embree/CMakeLists.txt" ] || \
   [ ! -f "${REPO}/submodules/cuBQL/CMakeLists.txt" ] || \
   [ ! -d "${REPO}/submodules/owl/include" ]; then
  git -C "${REPO}" submodule update --init \
    submodules/cuBQL submodules/embree submodules/owl
fi

# Source selection.
# Default: the src/barney working tree. The HEAD of branch mjar/devel
# (7f46b52 "update volume") has committed merge-conflict markers; they are
# resolved in the working tree (uncommitted, 2026-10-26: barneyConfig.h.in,
# anari/Volume.{h,cpp}, native/volume/{PrincipledVolume.h,NanoVDB.dev.cu,
# MCAccelerator.h}), see docs/notes/anari_barney_build.md.
# BARNEY_COMMIT=<sha> builds a 'git archive' snapshot of that commit instead
# (build/src_snapshots/barney-<sha>; install/barney was built from 4d9b843
# this way). BARNEY_SRC=<dir> builds an arbitrary source tree.
BARNEY_COMMIT=${BARNEY_COMMIT:-worktree}
if [ -z "${BARNEY_SRC:-}" ]; then
  if [ "${BARNEY_COMMIT}" = "HEAD" ] || [ "${BARNEY_COMMIT}" = "worktree" ]; then
    SRC=${REPO}
  else
    SRC=${PROJ_ROOT}/build/src_snapshots/barney-${BARNEY_COMMIT}
    if [ ! -f "${SRC}/CMakeLists.txt" ]; then
      mkdir -p "${SRC}"
      git -C "${REPO}" archive "${BARNEY_COMMIT}" | tar -x -C "${SRC}"
      for m in cuBQL embree owl; do
        rm -rf "${SRC}/submodules/${m}"
        cp -a "${REPO}/submodules/${m}" "${SRC}/submodules/${m}"
        rm -rf "${SRC}/submodules/${m}/.git"
      done
    fi
  fi
else
  SRC=${BARNEY_SRC}
fi
if grep -rlq '^<<<<<<< ' "${SRC}/barney" 2>/dev/null; then
  echo "ERROR: ${SRC} contains merge-conflict markers:" >&2
  grep -rl '^<<<<<<< ' "${SRC}/barney" >&2
  exit 1
fi
echo "Building barney from ${SRC} (build dir ${BLD}, prefix ${PREFIX})"

cmake -S "${SRC}" -B "${BLD}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
  -DCMAKE_PREFIX_PATH="${ANARI_ROOT}" \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DMPI_C_COMPILER=mpicc -DMPI_CXX_COMPILER=mpicxx \
  -DBARNEY_BACKEND_CPU=ON \
  -DBARNEY_BACKEND_OPTIX=OFF \
  -DBARNEY_BACKEND_CUDA=OFF \
  -DBARNEY_BACKEND_HIP=OFF \
  -DBARNEY_BACKEND_HIPRT=OFF \
  -DBARNEY_MPI=ON \
  -DEMBREE_ISA_SSE42=ON \
  -DEMBREE_ISA_AVX2=OFF \
  -DEMBREE_ISA_AVX512=OFF \
  ${BARNEY_EXTRA_CMAKE_ARGS:-}

cmake --build "${BLD}" -j "${NPROC}"
cmake --install "${BLD}"
echo "Barney installed into ${PREFIX}"
