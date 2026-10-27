#!/bin/bash
# Run one OpenFOAM command inside a case directory with the v2606 environment.
# Usage (one MPI rank per srun task):
#   srun --jobid=5270670 --overlap -N<n> -w <nodes> --ntasks-per-node=128 --mpi=pmix \
#        bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/cases/ofexec.sh <caseDir> <app> [args...]
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_openfoam.sh >/dev/null 2>&1
cd "$1" || exit 1
shift
exec "$@"
