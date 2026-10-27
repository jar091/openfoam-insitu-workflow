#!/bin/bash
# Create a small decomposed 3D OpenFOAM case (lid-driven cube cavity, icoFoam,
# 24^3 hex cells, 4 subdomains, 5 written time steps) used to test mesio -> OpenVDB.
# The existing module OpenFOAM/v2506-foss-2025b is used only to generate test data
# (same foss/2025b toolchain as the project OpenFOAM v2606 build).
#
# Usage (from the login node; all work runs inside the Slurm job):
#   bash scripts/make_mesio_testcase.sh
set -euo pipefail

PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
SCRATCH=/scratch/project/eu-25-121/milanjaros/openfoam
CASE=${CASE:-${SCRATCH}/runs/mesio_test/cavity3d}
JOB=${JOB:-5270670}
NODE=${NODE:-cn357}

PRE='export HOME='${SCRATCH}'/fakehome; mkdir -p $HOME; export XDG_CACHE_HOME=$HOME/.cache;
module purge >/dev/null 2>&1; module load OpenFOAM/v2506-foss-2025b >/dev/null 2>&1;
set +u; source $FOAM_BASH; set -u'

mkdir -p "$(dirname ${CASE})"
rm -rf "${CASE}"

srun --jobid=${JOB} --overlap -N1 -n1 -w ${NODE} bash -c "set -eu; ${PRE}
T=\$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity
cp -r \$T ${CASE}
cd ${CASE}
# 3D cube: z extent 1 (x scale 0.1), 24^3 cells, front/back become walls
sed -i 's/(0 0 0.1)/(0 0 1)/; s/(1 0 0.1)/(1 0 1)/; s/(1 1 0.1)/(1 1 1)/; s/(0 1 0.1)/(0 1 1)/' system/blockMeshDict
sed -i 's/(20 20 1)/(24 24 24)/' system/blockMeshDict
sed -i '/frontAndBack/,/}/ s/type empty;/type wall;/' system/blockMeshDict
sed -i '/frontAndBack/,/}/ s/type            empty;/type            noSlip;/' 0/U
sed -i '/frontAndBack/,/}/ s/type            empty;/type            zeroGradient;/' 0/p
sed -i 's/^endTime .*/endTime         0.02;/; s/^deltaT .*/deltaT          0.002;/; s/^writeInterval .*/writeInterval   2;/' system/controlDict
cat > system/decomposeParDict <<'EOF'
FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }
numberOfSubdomains 4;
method          simple;
coeffs { n (2 2 1); }
EOF
blockMesh > log.blockMesh 2>&1
checkMesh > log.checkMesh 2>&1
decomposePar > log.decomposePar 2>&1
"

srun --jobid=${JOB} --overlap -N1 -n4 -w ${NODE} --mpi=pmix bash -c "set -eu; ${PRE}
cd ${CASE}; icoFoam -parallel > log.icoFoam.\${SLURM_PROCID} 2>&1"

ls ${CASE} ${CASE}/processor0
grep -E "cells:|points:|faces:" ${CASE}/log.checkMesh | head
