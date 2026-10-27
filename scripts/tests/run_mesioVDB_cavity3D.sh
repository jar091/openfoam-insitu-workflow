#!/bin/bash
# cavity3D 1M (OpenFOAM HPC TC, icoFoam fixedIter) with mesioVDB export,
# 128 MPI ranks on one node. Baseline (no export) and export runs share the
# decomposed case.
#
#   bash run_mesioVDB_cavity3D.sh prepare
#   bash run_mesioVDB_cavity3D.sh run <label> <density|none> [exportInterval]
#
# Env: NODE (cn628; comma list for multi-node), NP (128), STEPS (300),
#      BASE (run directory), JOB (5270670)
set -euo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
BASE=${BASE:-/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_fo/cavity3D_1M}
CASE=$BASE/case
JOB=${JOB:-5270670}; NODE=${NODE:-cn628}; NP=${NP:-128}; STEPS=${STEPS:-300}
NNODES=$(echo "$NODE" | awk -F, '{print NF}')
RUN="srun --jobid=${JOB} --overlap -N${NNODES} -w ${NODE}"
RUN1="srun --jobid=${JOB} --overlap -N1 -w ${NODE%%,*}"
ENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; source ${PROJ}/scripts/env_mesio_openfoam.sh >/dev/null 2>&1"

case "$1" in
prepare)
    rm -rf "$CASE"; mkdir -p "$BASE"
    cp -r "$PROJ/src/hpc/incompressible/icoFoam/cavity3D/1M/fixedIter" "$CASE"
    sed -i "s/^numberOfSubdomains .*/numberOfSubdomains $NP;/" "$CASE/system/decomposeParDict"
    ${RUN1} -n1 -c 8 bash -c "${ENV}; cd $CASE && blockMesh > log.blockMesh 2>&1 && decomposePar > log.decomposePar 2>&1"
    ${RUN} --ntasks-per-node=$((NP / NNODES)) -n$NP --mpi=pmix bash -c "${ENV}; cd $CASE && exec renumberMesh -overwrite -parallel" > "$CASE/log.renumberMesh" 2>&1
    cp "$CASE/system/controlDict" "$CASE/system/controlDict.orig"
    ;;
run)
    label=$2; density=$3; interval=${4:-30}
    cp "$CASE/system/controlDict.orig" "$CASE/system/controlDict"
    sed -i "s/^endTime .*/endTime         $(awk "BEGIN{print $STEPS*0.001}");/; s/^runTimeModifiable .*/runTimeModifiable false;/" "$CASE/system/controlDict"
    if [ "$density" != none ]; then
        cat >> "$CASE/system/controlDict" <<EOD

functions
{
    Q1
    {
        type            Q;
        libs            (fieldFunctionObjects);
        field           U;
        result          Q;
        executeControl  timeStep;
        executeInterval $interval;
        writeControl    none;
    }

    mesioVDB1
    {
        type            mesioVDB;
        libs            (mesioFoam);
        writeControl    timeStep;
        writeInterval   $interval;
        fields          (U p Q);
        density         $density;
        outputDir       "$BASE/VDB_$label";
        filePattern     "cavity3D_%TIMEINDEX%.vdb";
        staleField      error;
        outputPolicy    vdbOnly;
    }
}
EOD
    fi
    rm -rf "$BASE/VDB_$label"
    ${RUN} --ntasks-per-node=$((NP / NNODES)) -n$NP --mpi=pmix bash -c "${ENV}; cd $CASE && exec icoFoam -parallel" > "$BASE/log.icoFoam.$label" 2>&1
    log=$BASE/log.icoFoam.$label
    echo "== $label: $(grep -m1 -E '^End|FATAL' "$log")"
    python3 - "$log" "$interval" <<'PY'
import re, sys
log, interval = sys.argv[1], int(sys.argv[2])
txt = open(log).read()
clock = [float(x) for x in re.findall(r"^ExecutionTime = \S+ s  ClockTime = (\S+) s", txt, re.M)]
exe = [float(x) for x in re.findall(r"^ExecutionTime = (\S+) s", txt, re.M)]
exports = [float(x) for x in re.findall(r"^    time \[s\] (\S+)", txt, re.M)]
setup = re.findall(r"setup time : (\S+) s", txt)
print(f"steps {len(exe)}, ExecutionTime total {exe[-1]:.2f} s, ClockTime total {clock[-1]:.0f} s")
d = [b - a for a, b in zip(exe, exe[1:])]
if d:
    d_sorted = sorted(d)
    print(f"per-step ExecutionTime: median {d_sorted[len(d)//2]:.4f} s, min {d_sorted[0]:.4f} s, max {d_sorted[-1]:.4f} s")
if exports:
    print(f"exports {len(exports)}: mean {sum(exports)/len(exports):.3f} s, min {min(exports):.3f} s, max {max(exports):.3f} s; setup {setup}")
PY
    grep -A3 "Mesio context created" "$log" | head -4 || true
    grep -B1 -A2 "mesioVDB1 write" "$log" | tail -3 || true
    grep "mesioVDB1 end" "$log" || true
    ls -la "$BASE/VDB_$label" 2>/dev/null | tail -3 || true
    ;;
esac
