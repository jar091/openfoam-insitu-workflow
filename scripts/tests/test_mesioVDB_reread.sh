#!/bin/bash
# Run-time re-read of the mesioVDB settings (runTimeModifiable): icoFoam cavity on NP ranks,
# mesioVDB with a box (~60 s run, 20 exports); 25 s after the start system/controlDict is
# edited while the solver runs (OpenFOAM detects the change by the file time stamp,
# fileModificationSkew 5 s). Cases (one run each):
#   touch    controlDict only touched (same settings: no re-creation)
#   box      box changed            (context re-created at the next export on all ranks)
#   voxel    voxelSize changed      (re-created)
#   fields   fields changed         (re-created with the new grid list)
#   sampling sampling changed       (applied without re-creation)
#   invalid  box invalid (min > max) (rejected with a warning, old settings kept)
# Every run must reach End on all ranks, the log must show the expected message and the
# exports after the edit must exist.
# Run the script itself on a compute node (it starts the solver with srun from there): the
# login node's view of scratch can lag (or fail) while the solver writes.
#   srun --jobid=5275975 --overlap -N1 -n1 -c4 -w cn318 bash -c 'unset SLURM_NTASKS SLURM_NPROCS \
#       SLURM_CPUS_PER_TASK SLURM_TASKS_PER_NODE SLURM_STEP_NUM_TASKS SLURM_STEP_TASKS_PER_NODE; \
#       MESIO_VARIANT=next bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/tests/test_mesioVDB_reread.sh'
set -uo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
RUNS=${RUNS:-/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_fix/reread}
JOB=${JOB:-5275975}; NODE=${NODE:-cn318}; NP=${NP:-4}
CASES=${CASES:-touch box voxel fields sampling invalid}
RUN="srun --jobid=${JOB} --overlap -N1 -w ${NODE}"
ENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; source ${PROJ}/scripts/env_mesio_openfoam.sh >/dev/null 2>&1"

mkdir -p "$RUNS"
${RUN} -n1 bash -c "${ENV}; rm -rf $RUNS/base && cp -r \$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity $RUNS/base && cd $RUNS/base && \
    foamDictionary -entry writeInterval -set 100000 system/controlDict >/dev/null && \
    foamDictionary -entry endTime -set 300 system/controlDict >/dev/null && \
    foamDictionary -entry runTimeModifiable -set yes system/controlDict >/dev/null && \
    blockMesh > log.blockMesh 2>&1 && \
    printf 'FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }\nnumberOfSubdomains $NP;\nmethod scotch;\n' > system/decomposeParDict && \
    decomposePar > log.decomposePar 2>&1"

functions() { # $1 = box, $2 = voxelSize, $3 = fields, $4 = sampling
cat <<EOD
functions
{
    mesioVDB1
    {
        type            mesioVDB;
        libs            (mesioFoam);
        writeControl    timeStep;
        writeInterval   3000;
        fields          ($3);
        box             $1;
        voxelSize       $2;
        sampling        $4;
        outputDir       "VDB";
        filePattern     "cavity_%TIMEINDEX%.vdb";
        outputPolicy    vdbOnly;
    }
}
EOD
}
BOX="(0.01 0.01 0) (0.09 0.09 0.01)"

declare -A NEW EXPECT
NEW[touch]="$(functions "$BOX" 0.0005 "U p" cellPoint)"
EXPECT[touch]="Re-reading object controlDict"
NEW[box]="$(functions "(0.02 0.02 0) (0.08 0.08 0.01)" 0.0005 "U p" cellPoint)"
EXPECT[box]="settings changed, Mesio context is re-created"
NEW[voxel]="$(functions "$BOX" 0.001 "U p" cellPoint)"
EXPECT[voxel]="settings changed, Mesio context is re-created"
NEW[fields]="$(functions "$BOX" 0.0005 "U" cellPoint)"
EXPECT[fields]="settings changed, Mesio context is re-created"
NEW[sampling]="$(functions "$BOX" 0.0005 "U p" cell)"
EXPECT[sampling]="sampling cell applied"
NEW[invalid]="$(functions "(0.09 0.09 0.01) (0.01 0.01 0)" 0.0005 "U p" cellPoint)"
EXPECT[invalid]="settings not changed"

status=0
for t in $CASES; do
    d=$RUNS/$t
    rm -rf "$d"; cp -r "$RUNS/base" "$d"
    functions "$BOX" 0.0005 "U p" cellPoint >> "$d/system/controlDict"
    cp "$d/system/controlDict" "$d/system/controlDict.orig"
    ${RUN} -n${NP} --mpi=pmix bash -c "${ENV}; cd $d && exec icoFoam -parallel" > "$d/log.icoFoam" 2>&1 &
    pid=$!
    # wait for the first export, then edit the settings
    # edit 25 s after the start (the run takes ~60 s; the log and the VDB directory are not
    # reliably visible on the login node while the solver runs). Time-stamp checking: the new
    # mtime must exceed the old one by more than fileModificationSkew (5 s).
    sleep 25
    sed -n '1,/^functions/p' "$d/system/controlDict.orig" | head -n -1 > "$d/system/controlDict.new"
    printf '%s\n' "${NEW[$t]}" >> "$d/system/controlDict.new"
    mv "$d/system/controlDict.new" "$d/system/controlDict"
    [ "$t" = touch ] && touch "$d/system/controlDict"
    wait $pid; rc=$?
    exports=$(grep -c "^mesioVDB mesioVDB1 write" "$d/log.icoFoam")
    if [ $rc = 0 ] && grep -q "^End" "$d/log.icoFoam" && grep -q -E "${EXPECT[$t]}" "$d/log.icoFoam" && [ "$exports" -ge 15 ]; then
        printf '%-9s PASS  (rc %d, %d exports, %s)\n' "$t" $rc "$exports" "$(grep -m1 -E "${EXPECT[$t]}" "$d/log.icoFoam" | sed 's/^ *//' | cut -c1-90)"
    else
        printf '%-9s FAIL  (rc %d, %d exports)\n' "$t" $rc "$exports"; status=1
        grep -m5 -E "FOAM FATAL|Error|error" "$d/log.icoFoam"
    fi
done
exit $status
