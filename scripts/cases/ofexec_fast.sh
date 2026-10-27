#!/bin/bash
# Fast variant of ofexec.sh for many-rank launches.
# Sourcing env_openfoam.sh (module purge + Lmod loads) in every rank takes minutes
# for 128+ ranks per node (Lmod over NFS). Instead this sources a plain dump of
# the exported environment (no Lmod), created once on a compute node with:
#   srun --jobid=5270670 --overlap -N1 -n1 -w <node> bash -c '
#     export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
#     source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_openfoam.sh >/dev/null 2>&1
#     export -p | grep -vE "^declare -x (SLURM_|SLURMD_|PMIX_|PMI_|OMPI_MCA_orte|HOSTNAME=|PWD=|OLDPWD=|SHLVL=|_=)" \
#       > /scratch/project/eu-25-121/milanjaros/openfoam/runs/of_env_v2606.sh'
# Usage: srun ... bash ofexec_fast.sh <caseDir> <app> [args...]
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
source /scratch/project/eu-25-121/milanjaros/openfoam/runs/of_env_v2606.sh
cd "$1" || exit 1
shift
exec "$@"
