#!/bin/bash
# Robustness tests of the MESIO in-situ API (all runs trap FE_DIVBYZERO | FE_INVALID |
# FE_OVERFLOW like OpenFOAM's FOAM_SIGFPE, driver option --fpe):
#   - writer cases: every case runs with the single, distributed and parallel writer; each run
#     must pass the driver's verification and the three files of every step must be byte
#     identical except the random UUID (bytes 22..57): empty ranks, ranks without voxels,
#     degenerate boxes (smaller than a cell, one voxel, zero thickness, outside the mesh),
#     constant fields on a moving mesh, cell sampling, field metadata, two contexts,
#     ResetMesh (topology change), compression none, 256 ranks on two nodes with empty ranks;
#   - error cases: every error must be reported with the same code on all ranks and the
#     process must continue (a normal run follows in the same process).
# Usage (login node; the work runs inside the Slurm job):
#   MESIO_VARIANT=next JOB=5275975 NODES=cn317,cn318 bash data/mesio_tests/run_robustness_tests.sh
#   CASES_FILTER=<regex> selects cases; EXTRA_ARGS adds driver arguments; RUN_TIMEOUT (s).
#   REF_VARIANT=dev REF_DRIVER=<driver built against it>: the writer cases that the old API
#   supports also run with the reference library (distributed writer, without --fpe) and the
#   files must be byte identical to the distributed files of this variant (except the UUID).
#   ASAN=1: AddressSanitizer run (MESIO_VARIANT=asan-next, driver built with
#   DRIVER_FLAGS=-fsanitize=address; libasan preloaded, Open MPI ob1/vader/tcp without UCX and
#   without the UCX memory hooks, which conflict with ASan; the two-node case runs on one
#   node with 128 ranks); fails on any ASan report.
set -uo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
OUT=${OUT:-/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_fix/robustness}
JOB=${JOB:-5275975}; NODES=${NODES:-cn317,cn318}; NODE1=${NODES%%,*}
export MESIO_VARIANT=${MESIO_VARIANT:-next}
EXTRA_ARGS=${EXTRA_ARGS:-}
CASES_FILTER=${CASES_FILTER:-.}
RUN_TIMEOUT=${RUN_TIMEOUT:-1800}   # seconds per driver run (0: none); a hanging run counts as failed
DRIVER=${PROJ}/build/mesio_tests/insitu_driver-${MESIO_VARIANT}
REF_VARIANT=${REF_VARIANT:-}; REF_DRIVER=${REF_DRIVER:-${PROJ}/build/mesio_tests/insitu_driver-${REF_VARIANT}}
ENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; export MESIO_VARIANT=${MESIO_VARIANT}; source ${PROJ}/scripts/env_mesio.sh >/dev/null 2>&1"
if [ "${ASAN:-0}" = 1 ]; then
  # Open MPI without UCX (pml, osc) and without the UCX memory hooks: they conflict with the
  # ASan runtime (SIGILL at start-up); the libasan preload replaces the XALT preload
  ENV="${ENV}; export LD_PRELOAD=\$(gcc -print-file-name=libasan.so) XALT_EXECUTABLE_TRACKING=no OMPI_MCA_pml=ob1 OMPI_MCA_btl=self,vader,tcp OMPI_MCA_osc=^ucx OMPI_MCA_opal_common_ucx_opal_mem_hooks=0 UCX_MEM_EVENTS=no ASAN_OPTIONS=detect_leaks=0"
fi
mkdir -p ${OUT}
run() { # nodes ranks log args...
  local nn=$1 np=$2 log=$3; shift 3
  if [ "${ASAN:-0}" = 1 ] && [ ${nn} -gt 1 ]; then # TCP between nodes runs out of ports with 256 ASan ranks
    nn=1; np=128
  fi
  timeout ${RUN_TIMEOUT} srun --jobid=${JOB} --overlap -N${nn} -n${np} -w $( [ ${nn} = 1 ] && echo ${NODE1} || echo ${NODES} ) --mpi=pmix \
    bash -c "${ENV}; exec ${DRIVER} --fpe $* ${EXTRA_ARGS}" > ${log} 2>&1
}

# name      ranks nodes driver arguments
WRITER_CASES=(
  "empty8     8   1 --voxel 0.01 --steps 2 --empty 3"
  "emptybox64 64  1 --voxel 0.002 --box 0.40 0.10 0.05 0.50 0.20 0.10 --steps 2 --empty 8"
  "tinybox    4   1 --voxel 0.002 --box 0.501 0.251 0.101 0.509 0.259 0.109 --steps 2"
  "onevoxel   4   1 --voxel 0.05 --box 0.3 0.2 0.1 0.3 0.2 0.1 --steps 2"
  "slice      16  1 --voxel 0.005 --box 0.1 0.1 0.125 0.9 0.4 0.125 --steps 2"
  "outside    4   1 --voxel 0.01 --box 2 2 2 2.5 2.5 2.5 --steps 2"
  "constmove  16  1 --voxel 0.01 --constant --moving --steps 3"
  "cell       16  1 --voxel 0.005 --box 0.2 0.1 0.05 0.7 0.4 0.2 --sampling cell --steps 2"
  "cellmove   4   1 --voxel 0.01 --sampling cell --moving --steps 3"
  "meta       4   1 --voxel 0.01 --metadata --memory --steps 2"
  "contexts   16  1 --voxel 0.005 --box 0.2 0.1 0.05 0.7 0.4 0.2 --contexts 2 --steps 2"
  "reset      4   1 --voxel 0.01 --resetmesh --steps 3"
  "none64     64  1 --voxel 0.004 --compression none --empty 4 --steps 2"
  "big256     256 2 --cells 200 100 50 --density 400 --extra 1 --steps 2 --empty 16 --memory"
)
ERROR_CASES=(grid zerobox settings mesh field file moving)

status=0
for c in "${WRITER_CASES[@]}"; do
  read -r name np nn args <<< "$c"
  [[ "${name}" =~ ${CASES_FILTER} ]] || continue
  for w in single distributed parallel; do
    run ${nn} ${np} ${OUT}/${name}_${w}.log --out ${OUT}/${name}_${w} --writer ${w} ${args} || { echo "FAILED run ${name} ${w}"; status=1; }
    grep -q "TEST PASSED" ${OUT}/${name}_${w}.log || { echo "FAILED verification ${name} ${w}"; status=1; }
    grep -q "SIGFPE" ${OUT}/${name}_${w}.log && { echo "SIGFPE ${name} ${w}"; status=1; }
    grep -q "AddressSanitizer" ${OUT}/${name}_${w}.log && { echo "ASAN REPORT ${name} ${w}"; status=1; }
  done
  for w in distributed parallel; do
    for f in $(cd ${OUT}/${name}_single && find . -name "*.vdb" | sort); do
      g=${OUT}/${name}_${w}/${f}
      nd=$(cmp -l ${OUT}/${name}_single/${f} ${g} 2>&1 | awk '$1 < 22 || $1 > 57' | wc -l)
      printf "%-10s %-12s %-22s %10d bytes, differing bytes outside the UUID: %d\n" ${name} ${w} ${f#./} $(stat -c %s ${OUT}/${name}_single/${f}) ${nd}
      [ "${nd}" = 0 ] || status=1
    done
  done
  grep -h "memory" ${OUT}/${name}_*.log | tail -3
  if [ -n "${REF_VARIANT}" ] && ! [[ "${args}" =~ --(empty|sampling|contexts|resetmesh|metadata|memory) ]]; then
    REFENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; export MESIO_VARIANT=${REF_VARIANT}; source ${PROJ}/scripts/env_mesio.sh >/dev/null 2>&1"
    srun --jobid=${JOB} --overlap -N${nn} -n${np} -w $( [ ${nn} = 1 ] && echo ${NODE1} || echo ${NODES} ) --mpi=pmix \
      bash -c "${REFENV}; exec ${REF_DRIVER} --out ${OUT}/${name}_ref --writer distributed ${args}" > ${OUT}/${name}_ref.log 2>&1 || { echo "FAILED reference run ${name}"; status=1; }
    for f in $(cd ${OUT}/${name}_distributed && find . -name "*.vdb" | sort); do
      nd=$(cmp -l ${OUT}/${name}_ref/${f} ${OUT}/${name}_distributed/${f} 2>&1 | awk '$1 < 22 || $1 > 57' | wc -l)
      printf "%-10s %-12s %-22s differing bytes outside the UUID: %d\n" ${name} "vs ${REF_VARIANT}" ${f#./} ${nd}
      [ "${nd}" = 0 ] || status=1
    done
  fi
done
for e in "${ERROR_CASES[@]}"; do
  [[ "error_${e}" =~ ${CASES_FILTER} ]] || continue
  for np in 1 4 16; do
    [ "${e}" = settings ] && [ ${np} = 1 ] && continue # needs ranks with different settings
    run 1 ${np} ${OUT}/error_${e}_np${np}.log --out ${OUT}/error_${e}_np${np} --error ${e} || { echo "FAILED run error ${e} np${np}"; status=1; }
    grep -q "TEST PASSED" ${OUT}/error_${e}_np${np}.log || { echo "FAILED error ${e} np${np}"; status=1; }
    grep -q "AddressSanitizer" ${OUT}/error_${e}_np${np}.log && { echo "ASAN REPORT error ${e} np${np}"; status=1; }
    echo "error ${e} np${np}: $(grep -m1 'error test' ${OUT}/error_${e}_np${np}.log)"
  done
done
echo "overall status: ${status}"
exit ${status}
