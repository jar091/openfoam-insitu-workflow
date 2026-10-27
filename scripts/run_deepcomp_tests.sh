#!/bin/bash
# Data-parallel ANARI rendering + CPU deep compositing tests
# (install/deepcompositing/bin/dcAnariDataParallel, testDeepOffline).
# Output PNGs go to ${SCRATCH_ROOT}/renders/deepcomp_test.
#
# Single rank wrapper, used as the srun task, e.g. (1 node, 4 ranks):
#   srun --jobid=<JOB> --overlap --mpi=pmix -N1 -n4 -c32 -w cn629 \
#     bash scripts/run_deepcomp_tests.sh dcAnariDataParallel --lib helide -o x.png
# (2 nodes: -N2 -n4 --ntasks-per-node=2 -w cn629,cn630).
# All arguments are the command (and its arguments) to run in the output dir.
source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_cyclesphi_anari.sh >/dev/null 2>&1
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-${OMP_NUM_THREADS}}
OUT=${SCRATCH_ROOT}/renders/deepcomp_test
mkdir -p "${OUT}"
cd "${OUT}"
# drop the very verbose cycles debug/info output
exec "$@" 2> >(grep -v "DEBUG\|OpenColorIO\|RAWImageLoader\|metadata.transform\|^    \[" >&2)
