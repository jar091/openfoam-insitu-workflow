#!/bin/bash
# mesioVDB with a moving (deforming) mesh: pimpleFoam movingCone tutorial,
# serial and 4 ranks; the VDB grid is re-voxelized at every export.
#   bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/tests/test_mesioVDB_movingCone.sh
set -euo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
RUNS=${RUNS:-/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_fo/movingCone}
JOB=${JOB:-5270670}; NODE=${NODE:-cn628}
RUN="srun --jobid=${JOB} --overlap -N1 -w ${NODE}"
ENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; source ${PROJ}/scripts/env_mesio_openfoam.sh >/dev/null 2>&1"

for n in 1 4; do
    d=$RUNS/np$n
    rm -rf "$d"; mkdir -p "$RUNS"
    ${RUN} -n1 bash -c "${ENV}; cp -r \$FOAM_TUTORIALS/incompressible/pimpleFoam/laminar/movingCone $d && cd $d && \
        foamDictionary -entry functions -remove system/controlDict >/dev/null && \
        rm -f system/cuttingPlane system/vtkWrite && \
        foamDictionary -entry endTime -set 0.0015 system/controlDict >/dev/null && \
        foamDictionary -entry writeInterval -set 100000 system/controlDict >/dev/null && \
        blockMesh > log.blockMesh 2>&1"
    cat >> "$d/system/controlDict" <<'EOD'

functions
{
    mesioVDB1
    {
        type            mesioVDB;
        libs            (mesioFoam);
        writeControl    timeStep;
        writeInterval   50;
        fields          (U p);
        density         400;
        outputDir       "VDB";
        filePattern     "cone_%TIMEINDEX%.vdb";
        outputPolicy    vdbOnly;
    }
}
EOD
    if [ "$n" -gt 1 ]; then
        printf 'FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }\nnumberOfSubdomains %d;\nmethod scotch;\n' "$n" > "$d/system/decomposeParDict"
        ${RUN} -n1 bash -c "${ENV}; cd $d && decomposePar > log.decomposePar 2>&1"
        ${RUN} -n$n --mpi=pmix bash -c "${ENV}; cd $d && exec pimpleFoam -parallel" > "$d/log.pimpleFoam" 2>&1
    else
        ${RUN} -n1 --mpi=pmix bash -c "${ENV}; cd $d && pimpleFoam" > "$d/log.pimpleFoam" 2>&1
    fi
    echo "== np$n: $(grep -m1 -E '^End|FATAL' $d/log.pimpleFoam)"
    grep -E "moving mesh|mesioVDB1 write|voxels [0-9]|time \[s\]" "$d/log.pimpleFoam" | head -40
done
echo "== np1 vs np4"
${RUN} -n1 bash -c "${ENV}; for f in $RUNS/np1/VDB/*.vdb; do echo \$(basename \$f); $PROJ/build/tools/vdb_diff \$f $RUNS/np4/VDB/\$(basename \$f) || true; done"
