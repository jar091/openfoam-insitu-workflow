#!/bin/bash
# mesioVDB with topology changes: 3D lid-driven cavity, pimpleFoam with
# dynamicRefineFvMesh (refinement on p). Every refinement triggers
# updateMesh() -> the Mesio context is destroyed and re-created at the next
# export. Serial and 4 ranks.
#   bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/tests/test_mesioVDB_refine.sh
set -euo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
RUNS=${RUNS:-/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_fo/refineCavity}
JOB=${JOB:-5270670}; NODE=${NODE:-cn628}
RUN="srun --jobid=${JOB} --overlap -N1 -w ${NODE}"
ENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; source ${PROJ}/scripts/env_mesio_openfoam.sh >/dev/null 2>&1"
HDR='FoamFile { version 2.0; format ascii; class dictionary; object'

make_case() {
d=$1; mkdir -p $d/system $d/constant $d/0
cat > $d/system/blockMeshDict <<EOD
$HDR blockMeshDict; }
scale 0.1;
vertices ((0 0 0) (1 0 0) (1 1 0) (0 1 0) (0 0 1) (1 0 1) (1 1 1) (0 1 1));
blocks (hex (0 1 2 3 4 5 6 7) (16 16 16) simpleGrading (1 1 1));
boundary
(
    movingWall { type wall; faces ((3 7 6 2)); }
    fixedWalls { type wall; faces ((0 4 7 3) (2 6 5 1) (1 5 4 0) (0 3 2 1) (4 5 6 7)); }
);
EOD
cat > $d/system/controlDict <<EOD
$HDR controlDict; }
application     pimpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         0.2;
deltaT          0.005;
writeControl    timeStep;
writeInterval   100000;
writeFormat     binary;
runTimeModifiable false;
functions
{
    Q1
    {
        type Q; libs (fieldFunctionObjects); field U; result Q;
        executeControl timeStep; executeInterval 10; writeControl none;
    }
    mesioVDB1
    {
        type            mesioVDB;
        libs            (mesioFoam);
        writeControl    timeStep;
        writeInterval   10;
        fields          (U p Q);
        density         128;
        outputDir       "VDB";
        filePattern     "refine_%TIMEINDEX%.vdb";
        staleField      error;
        outputPolicy    vdbOnly;
    }
}
EOD
cat > $d/system/fvSchemes <<EOD
$HDR fvSchemes; }
ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) Gauss linear; div((nuEff*dev2(T(grad(U))))) Gauss linear; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
EOD
cat > $d/system/fvSolution <<EOD
$HDR fvSolution; }
solvers
{
    "pcorr.*" { solver PCG; preconditioner DIC; tolerance 1e-6; relTol 0; }
    p { solver PCG; preconditioner DIC; tolerance 1e-6; relTol 0.05; }
    pFinal { \$p; relTol 0; }
    "U.*" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-6; relTol 0; }
}
PIMPLE { nOuterCorrectors 1; nCorrectors 2; nNonOrthogonalCorrectors 0; pRefCell 0; pRefValue 0; correctPhi yes; }
EOD
cat > $d/constant/transportProperties <<EOD
$HDR transportProperties; }
transportModel Newtonian;
nu 0.001;
EOD
cat > $d/constant/turbulenceProperties <<EOD
$HDR turbulenceProperties; }
simulationType laminar;
EOD
cat > $d/constant/dynamicMeshDict <<EOD
$HDR dynamicMeshDict; }
dynamicFvMesh   dynamicRefineFvMesh;
refineInterval  7;
field           p;
lowerRefineLevel 0.02;
upperRefineLevel 1e6;
unrefineLevel   0.01;
nBufferLayers   1;
maxRefinement   2;
maxCells        1000000;
correctFluxes   ((phi none) (phi_0 none));
dumpLevel       false;
EOD
cat > $d/0/U <<EOD
$HDR U; class volVectorField; }
dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField { movingWall { type fixedValue; value uniform (1 0 0); } fixedWalls { type noSlip; } }
EOD
cat > $d/0/p <<EOD
$HDR p; class volScalarField; }
dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;
boundaryField { ".*" { type zeroGradient; } }
EOD
}

for n in 1 4; do
    d=$RUNS/np$n
    rm -rf "$d"; make_case "$d"
    ${RUN} -n1 bash -c "${ENV}; cd $d && blockMesh > log.blockMesh 2>&1"
    if [ "$n" -gt 1 ]; then
        printf '%s decomposeParDict; }\nnumberOfSubdomains %d;\nmethod scotch;\n' "$HDR" "$n" > "$d/system/decomposeParDict"
        ${RUN} -n1 bash -c "${ENV}; cd $d && decomposePar > log.decomposePar 2>&1"
        ${RUN} -n$n --mpi=pmix bash -c "${ENV}; cd $d && exec pimpleFoam -parallel" > "$d/log.pimpleFoam" 2>&1 || true
    else
        ${RUN} -n1 --mpi=pmix bash -c "${ENV}; cd $d && pimpleFoam" > "$d/log.pimpleFoam" 2>&1 || true
    fi
    echo "== np$n: $(grep -m1 -E '^End|FATAL' $d/log.pimpleFoam)"
    grep -E "Refined from|Unrefined from|re-creating|context created|mesioVDB1 write|voxels [0-9]|FATAL|stale" "$d/log.pimpleFoam" | head -60 || true
done
echo "== np1 vs np4 (NOTE: refined meshes differ between decompositions: pRefCell is rank-local, p level and thus the refined region differ)"
${RUN} -n1 bash -c "${ENV}; for f in $RUNS/np1/VDB/*.vdb; do echo \$(basename \$f); $PROJ/build/tools/vdb_diff \$f $RUNS/np4/VDB/\$(basename \$f) || true; done"
