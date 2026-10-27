#!/bin/bash
# Run mesio (OpenFOAM case -> OpenVDB) on NP ranks inside the Slurm job and inspect the .vdb files.
# Usage: bash scripts/run_mesio_test.sh <nranks>
set -euo pipefail
NP=${1:-1}
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
RUN=/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_test
OUT=${RUN}/np${NP}
mkdir -p ${OUT}
cp -f ${PROJ}/scripts/mesio_test.ecf ${RUN}/mesio.ecf   # [ARG0] = output directory
srun --jobid=${JOB:-5270670} --overlap -N1 -n ${NP} -w ${NODE:-cn357} --mpi=pmix bash -c "
  source ${PROJ}/scripts/env_mesio.sh >/dev/null 2>&1
  cd ${OUT}
  mesio -c ${RUN}/mesio.ecf ${OUT}" > ${OUT}/mesio.log 2>&1
srun --jobid=${JOB:-5270670} --overlap -N1 -n1 -w ${NODE:-cn357} bash -c "
  source ${PROJ}/scripts/env_mesio.sh >/dev/null 2>&1
  for f in \$(ls ${OUT}/last/PREPOSTDATA/*.vdb); do echo \"== \$f\"; vdb_print -m \$f; done" > ${OUT}/vdb_print.log 2>&1
cat ${OUT}/vdb_print.log
