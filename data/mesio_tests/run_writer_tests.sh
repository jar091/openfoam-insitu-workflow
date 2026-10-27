#!/bin/bash
# Distributed and parallel vs single (legacy) VDB writer of the MESIO in-situ API.
# Every case runs the driver three times (--writer single / distributed / parallel) with the
# same input and requires byte-identical files except the random 36-character UUID in the
# file header (bytes 22..57), plus the driver's own verification.
# Usage (login node; the work runs inside the Slurm job):
#   MESIO_VARIANT=dev bash data/mesio_tests/run_writer_tests.sh
# Environment: JOB, NODES (two nodes for the 256-rank case), EXTRA_ARGS (e.g. "--fpe"),
#   CASES_FILTER (regular expression on the case names), OUT
set -uo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
OUT=${OUT:-/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_dev/writer_tests}
JOB=${JOB:-5270670}; NODES=${NODES:-cn356,cn357}; NODE1=${NODES%%,*}
export MESIO_VARIANT=${MESIO_VARIANT:-dev}
DRIVER=${PROJ}/build/mesio_tests/insitu_driver-${MESIO_VARIANT}
EXTRA_ARGS=${EXTRA_ARGS:-}
CASES_FILTER=${CASES_FILTER:-.}
ENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; export MESIO_VARIANT=${MESIO_VARIANT}; source ${PROJ}/scripts/env_mesio.sh >/dev/null 2>&1"
mkdir -p ${OUT}

# name  ranks  nodes  driver arguments
CASES=(
  "base1    1   1 --voxel 0.01 --steps 2"
  "box4     4   1 --voxel 0.005 --box 0.2 0.1 0.05 0.7 0.4 0.2 --steps 2"
  "move4    4   1 --voxel 0.01 --moving --steps 3"
  "empty64  64  1 --voxel 0.002 --box 0.40 0.10 0.05 0.50 0.20 0.10 --steps 2"
  "none64   64  1 --voxel 0.004 --compression none --steps 2"
  "big256   256 2 --cells 200 100 50 --density 400 --extra 1 --steps 2 --setups 2 --noverify"
)

status=0
for c in "${CASES[@]}"; do
  read -r name np nn args <<< "$c"
  [[ "${name}" =~ ${CASES_FILTER} ]] || continue
  for w in single distributed parallel; do
    srun --jobid=${JOB} --overlap -N${nn} -n${np} -w $( [ ${nn} = 1 ] && echo ${NODE1} || echo ${NODES} ) --mpi=pmix \
      bash -c "${ENV}; exec ${DRIVER} --out ${OUT}/${name}_${w} --writer ${w} ${args} ${EXTRA_ARGS}" > ${OUT}/${name}_${w}.log 2>&1 || { echo "FAILED run ${name} ${w}"; status=1; }
    grep -q "TEST PASSED" ${OUT}/${name}_${w}.log || { echo "FAILED verification ${name} ${w}"; status=1; }
  done
  for w in distributed parallel; do
    for f in ${OUT}/${name}_single/*.vdb; do
      g=${OUT}/${name}_${w}/$(basename $f)
      nd=$(cmp -l $f $g 2>&1 | awk '$1 < 22 || $1 > 57' | wc -l)
      printf "%-8s %-12s %-14s %12d bytes, differing bytes outside the UUID: %d\n" ${name} ${w} $(basename $f) $(stat -c %s $f) ${nd}
      [ "${nd}" = 0 ] || status=1
    done
    grep -h "timings" ${OUT}/${name}_${w}.log | tail -1
  done
done
echo "overall status: ${status}"
exit ${status}
