#!/bin/bash
# Validation of the mesioVDB function object on the icoFoam cavity tutorial.
#
#   np1  : serial,  outputPolicy vdbOnly (file-tree audit)
#   np4  : 4 ranks, outputPolicy vdbOnly (file-tree audit), compared with np1
#   ref  : serial,  outputPolicy standard, Q/U/p also written by OpenFOAM at
#          the last time -> reference for the VDB sampling check
#
# Run from the login node (all work runs inside the job on NODE):
#   bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/tests/test_mesioVDB_cavity.sh
#   SAMPLING=cell MESIO_VARIANT=next ...  (mesioVDB 'sampling' entry, Mesio in-situ API 2)
set -euo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
RUNS=${RUNS:-/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_fo/cavity}
JOB=${JOB:-5270670}; NODE=${NODE:-cn628}
RUN="srun --jobid=${JOB} --overlap -N1 -w ${NODE}"
ENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; source ${PROJ}/scripts/env_mesio_openfoam.sh >/dev/null 2>&1"

functions_block() {   # $1 = outputPolicy, $2 = writeControl of the producers
cat <<EOD

functions
{
    // Derived fields: computed in memory by standard OpenFOAM function
    // objects listed BEFORE the exporter, same cadence, no disk output.
    Q1
    {
        type            Q;
        libs            (fieldFunctionObjects);
        field           U;
        result          Q;
        executeControl  timeStep;
        executeInterval 20;
        writeControl    $2;
    }
    vorticity1
    {
        type            vorticity;
        libs            (fieldFunctionObjects);
        field           U;
        executeControl  timeStep;
        executeInterval 20;
        writeControl    $2;
    }
    magU1
    {
        type            mag;
        libs            (fieldFunctionObjects);
        field           U;
        executeControl  timeStep;
        executeInterval 20;
        writeControl    $2;
    }

    mesioVDB1
    {
        type            mesioVDB;
        libs            (mesioFoam);
        writeControl    timeStep;
        writeInterval   20;
        fields          (U p Q vorticity mag(U));
        vectorComponents (mag x y);
        density         200;
        outputDir       "VDB";
        filePattern     "cavity_%TIMEINDEX%.vdb";
        missingField    error;
        staleField      error;
        outputPolicy    $1;${SAMPLING:+
        sampling        $SAMPLING;}
    }
}
EOD
}

setup_case() {   # $1 = dir, $2 = nProcs, $3 = policy, $4 = producer writeControl, $5 = solver writeInterval
    local d=$1
    rm -rf "$d"; mkdir -p "$(dirname "$d")"
    ${RUN} -n1 bash -c "${ENV}; cp -r \$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity $d && cd $d && \
        foamDictionary -entry writeInterval -set $5 system/controlDict >/dev/null && \
        blockMesh > log.blockMesh 2>&1"
    functions_block "$3" "$4" >> "$d/system/controlDict"
    if [ "$2" -gt 1 ]; then
        cat > "$d/system/decomposeParDict" <<EOD
FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }
numberOfSubdomains $2;
method          scotch;
EOD
        ${RUN} -n1 bash -c "${ENV}; cd $d && decomposePar > log.decomposePar 2>&1"
    fi
}

snapshot() { (cd "$1" && find . -type f ! -name 'log.*' ! -name '.snap_*' -printf '%p %s %T@\n' | sort); }

audit() {   # $1 = dir; files created/modified during the solver run, minus VDB
    diff <(cat "$1/.snap_before") <(snapshot "$1") | grep '^>' | grep -v '^> ./VDB/.*\.vdb ' || true
}

# ---------------------------------------------------------------------------
setup_case "$RUNS/np1" 1 vdbOnly none 1000
setup_case "$RUNS/np4" 4 vdbOnly none 1000
setup_case "$RUNS/ref" 1 standard writeTime 100

for c in np1 ref; do
    snapshot "$RUNS/$c" > "$RUNS/$c/.snap_before"
    ${RUN} -n1 --mpi=pmix bash -c "${ENV}; cd $RUNS/$c && icoFoam" > "$RUNS/$c/log.icoFoam" 2>&1
done
snapshot "$RUNS/np4" > "$RUNS/np4/.snap_before"
${RUN} -n4 --mpi=pmix bash -c "${ENV}; cd $RUNS/np4 && exec icoFoam -parallel" > "$RUNS/np4/log.icoFoam" 2>&1

status=0
for c in np1 np4 ref; do
    echo "== $c: $(grep -c '^mesioVDB mesioVDB1 write' "$RUNS/$c/log.icoFoam") exports, $(grep -m1 -E '^End|FOAM FATAL' "$RUNS/$c/log.icoFoam")"
    ls "$RUNS/$c/VDB"
    echo "   new/modified files besides VDB (audit):"
    audit "$RUNS/$c" | sed 's/^/     /'
done
if [ -n "$(audit "$RUNS/np1")$(audit "$RUNS/np4")" ]; then
    echo "AUDIT FAILED: vdbOnly runs produced other files"; status=1
else
    echo "AUDIT OK: vdbOnly runs produced only .vdb files"
fi

echo "== np1 vs np4 (voxel by voxel)"
${RUN} -n1 bash -c "${ENV}; for f in $RUNS/np1/VDB/*.vdb; do echo \$(basename \$f); \
    $PROJ/build/tools/vdb_diff \$f $RUNS/np4/VDB/\$(basename \$f) || true; done"
echo "== VDB (trilinear at cell centres) vs OpenFOAM fields written by the ref run, t = 0.5"
L=${PROJ}/install/cyclesphi_libs/linux_x64
PY="env LD_LIBRARY_PATH=$L/openvdb/lib:$L/tbb/lib PYTHONPATH=$L/python/lib/python3.13/site-packages $L/python/bin/python3.13 -I ${PROJ}/scripts/tests/compare_vdb_foam.py"
${RUN} -n1 bash -c "${ENV}; cd $RUNS/ref && postProcess -func writeCellCentres -time 0.5 > log.writeCellCentres 2>&1; \
    for g in Q p 'mag(U)'; do $PY field VDB/cavity_000100.vdb \$g 0.5/\$g 0.5/C; done; \
    $PY offset $RUNS/np1/VDB/cavity_000100.vdb $RUNS/np4/VDB/cavity_000100.vdb p; \
    $PY offset $RUNS/np1/VDB/cavity_000100.vdb $RUNS/ref/VDB/cavity_000100.vdb Q"
echo "== vdb_print (np4, last)"
${RUN} -n1 bash -c "${ENV}; vdb_print -l \$(ls $RUNS/np4/VDB/*.vdb | tail -1) | grep -E 'Name|class|time|voxel size|bbox|Bounding|\\]' | head -40"
exit $status
