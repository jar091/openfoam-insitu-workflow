#!/bin/bash
# MESIO in-situ API tests: in-memory decomposed hex FV mesh on 1 and N ranks.
#   - each run verifies fog-volume class, "time" metadata and world positions (driver),
#   - 1-rank vs N-rank outputs are compared voxel by voxel (vdb_diff),
#   - cases: default grid (voxel 0.01), sub-box with voxel 0.005, moving mesh.
# Usage (login node; work runs inside the Slurm job): bash data/mesio_tests/run_tests.sh
#   MESIO_VARIANT=next bash data/mesio_tests/run_tests.sh   (tests install/mesio-next)
# Environment:
#   JOB, NODES      Slurm job and nodes (comma separated; runs with > 128 ranks use two nodes)
#   NPS             rank counts compared with 1 rank (default "4")
#   EXTRA_ARGS      extra driver arguments, e.g. "--fpe" (trap FP exceptions as FOAM_SIGFPE)
#   OUT             output directory
set -euo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
OUT=${OUT:-/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_test/insitu}
JOB=${JOB:-5270670}; NODES=${NODES:-${NODE:-cn357}}; NODE1=${NODES%%,*}
NPS=${NPS:-4}
EXTRA_ARGS=${EXTRA_ARGS:-}
export MESIO_VARIANT=${MESIO_VARIANT:-}
DRIVER=${PROJ}/build/mesio_tests/insitu_driver${MESIO_VARIANT:+-${MESIO_VARIANT}}
ENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; export MESIO_VARIANT=${MESIO_VARIANT}; source ${PROJ}/scripts/env_mesio.sh >/dev/null 2>&1"
RUN1="srun --jobid=${JOB} --overlap -N1 -w ${NODE1}"
runN() { # ranks, command
  local n=$1; shift
  if [ "$n" -gt 128 ]; then
    srun --jobid=${JOB} --overlap -N2 -n${n} -w ${NODES} --mpi=pmix "$@"
  else
    srun --jobid=${JOB} --overlap -N1 -n${n} -w ${NODE1} --mpi=pmix "$@"
  fi
}
mkdir -p ${OUT}

${RUN1} -n1 bash ${PROJ}/data/mesio_tests/build.sh
${RUN1} -n1 bash -c "${ENV}; [ -x ${PROJ}/build/tools/vdb_diff ] || { mkdir -p ${PROJ}/build/tools; \
  g++ -std=c++17 -O2 ${PROJ}/scripts/tools/vdb_diff.cpp -I\$OPENVDB_ROOT/include -L\$OPENVDB_ROOT/lib \
  -Wl,-rpath,\$OPENVDB_ROOT/lib -lopenvdb -ltbb -o ${PROJ}/build/tools/vdb_diff; }"

declare -A ARGS=(
  [base]="--voxel 0.01 --steps 3"
  [box]="--voxel 0.005 --box 0.2 0.1 0.05 0.7 0.4 0.2 --steps 2"
  [move]="--voxel 0.01 --moving --steps 3"
)
status=0
for c in base box move; do
  for n in 1 ${NPS}; do
    echo "== case ${c}, ${n} rank(s)"
    runN ${n} bash -c "${ENV}; ${DRIVER} --out ${OUT}/${c}_np${n} ${ARGS[$c]} ${EXTRA_ARGS}" \
      > ${OUT}/${c}_np${n}.log 2>&1 || status=1
    grep -E "ranks|verify|TEST|SIGFPE" ${OUT}/${c}_np${n}.log || true
    grep -q "TEST PASSED" ${OUT}/${c}_np${n}.log || status=1
  done
  for n in ${NPS}; do
    echo "== case ${c}: 1 rank vs ${n} ranks"
    ${RUN1} -n1 bash -c "${ENV}; for f in ${OUT}/${c}_np1/*.vdb; do ${PROJ}/build/tools/vdb_diff \$f ${OUT}/${c}_np${n}/\$(basename \$f); done" || status=1
  done
done
NLAST=${NPS##* }
${RUN1} -n1 bash -c "${ENV}; vdb_print -l ${OUT}/box_np${NLAST}/step_0001.vdb | grep -A30 'Name: linear' | grep -E 'Name|class|time|voxel size|Bounding|index to world|\\]'"
echo "overall status: ${status}"
exit ${status}
