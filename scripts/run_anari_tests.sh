#!/bin/bash
# Build data/anari_tests and run headless renders with barney_cpu (and helide
# for reference), single process. MPI runs: see the commands at the end.
# Images go to $SCRATCH_ROOT/renders/anari_test/ (override: ANARI_TEST_OUT).
# BARNEY_PREFIX=<install dir> tests another barney install (e.g.
# install/barney-head) by putting its lib64 first on LD_LIBRARY_PATH.
#
# Run on a compute node, e.g.:
#   srun --jobid=<JOB> --overlap -N1 -n1 -w <node> bash scripts/run_anari_tests.sh
set -euo pipefail
source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_anari.sh
if [ -n "${BARNEY_PREFIX:-}" ]; then
  export LD_LIBRARY_PATH=${BARNEY_PREFIX}/lib64:${BARNEY_PREFIX}/lib:${LD_LIBRARY_PATH}
  echo "Using barney from ${BARNEY_PREFIX}"
fi

TSRC=${PROJ_ROOT}/data/anari_tests
TBLD=${PROJ_ROOT}/build/anari_tests
OUT=${ANARI_TEST_OUT:-${SCRATCH_ROOT}/renders/anari_test}
mkdir -p "${OUT}"

cmake -S "${TSRC}" -B "${TBLD}" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="${ANARI_ROOT}" -DCMAKE_CXX_COMPILER=g++
cmake --build "${TBLD}" -j 16
EXE=${TBLD}/anariBarneyTest

echo "=== helide (reference), single process ==="
"${EXE}" --lib helide --out "${OUT}/helide_mesh_volume.png" --spp 4 --frames 4 || true

echo "=== barney_cpu, single process: mesh only / volume only / both ==="
"${EXE}" --lib barney_cpu --no-volume --out "${OUT}/barney_cpu_mesh.png"
"${EXE}" --lib barney_cpu --no-mesh   --out "${OUT}/barney_cpu_volume.png"
"${EXE}" --lib barney_cpu             --out "${OUT}/barney_cpu_mesh_volume.png"

echo "=== barney (multi-backend loader), single process ==="
"${EXE}" --lib barney --out "${OUT}/barney_multi_mesh_volume.png" || true

# MPI data-parallel tests are launched with srun from the login node (one
# step per rank set; each rank owns one volume slab + one torus), e.g.:
#   srun --jobid=<JOB> --overlap -N1 -n2 -c 64 --cpu-bind=none -w cn627 --mpi=pmix \
#     bash -c 'source scripts/env_anari.sh; export BARNEY_MAX_CPU_THREADS=64;
#              build/anari_tests/anariBarneyTest --mpi --lib barney_cpu \
#              --out $SCRATCH_ROOT/renders/anari_test/barney_cpu_mpi2.png'
#   srun --jobid=<JOB> --overlap -N2 -n2 -c 32 --cpu-bind=none -w cn627,cn628 --mpi=pmix ...
