#!/bin/bash
# Diagnostics of mesioVDB (serial icoFoam cavity, endTime 0.2):
# stale field (error / warn), vdbOnly policy violation, missing field,
# unsupported field type, two instances (supported since Mesio in-situ API 2),
# Mesio errors with onError warn / error.
#   MESIO_VARIANT=next bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/tests/test_mesioVDB_errors.sh
# (MESIO_VARIANT and FOAM_SIGFPE are passed to the runs through the environment)
set -uo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
RUNS=${RUNS:-/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_fo/errors}
JOB=${JOB:-5270670}; NODE=${NODE:-cn628}
RUN="srun --jobid=${JOB} --overlap -N1 -w ${NODE}"
ENV="export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; source ${PROJ}/scripts/env_mesio_openfoam.sh >/dev/null 2>&1"

mkdir -p "$RUNS"
${RUN} -n1 bash -c "${ENV}; rm -rf $RUNS/base && cp -r \$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity $RUNS/base && cd $RUNS/base && \
    foamDictionary -entry writeInterval -set 1000 system/controlDict >/dev/null && \
    foamDictionary -entry endTime -set 0.2 system/controlDict >/dev/null && blockMesh > log.blockMesh 2>&1"

q() {  # $1 = executeInterval, $2 = writeControl line
    echo "Q1 { type Q; libs (fieldFunctionObjects); field U; result Q; executeControl timeStep; executeInterval $1; $2 }"
}
m() {  # $1 = name, $2 = fields, $3 = extra
    echo "$1 { type mesioVDB; libs (mesioFoam); writeControl timeStep; writeInterval 20; fields ($2); density 50; outputPolicy vdbOnly; $3 }"
}

declare -A FUNCS EXPECT
FUNCS[stale_error]="$(q 20 'writeControl none; timeEnd 0.15;') $(m mesio1 'U Q' 'staleField error;')"
EXPECT[stale_error]="was not updated in the current time step"
FUNCS[stale_warn]="$(q 20 'writeControl none; timeEnd 0.15;') $(m mesio1 'U Q' 'staleField warn;')"
EXPECT[stale_warn]="stale data exported"
FUNCS[policy]="$(q 20 '') $(m mesio1 'U Q' '')"
EXPECT[policy]="outputPolicy vdbOnly violated"
FUNCS[missing]="$(m mesio1 'U Qx' '')"
EXPECT[missing]="field Qx not found"
FUNCS[missing_skip]="$(m mesio1 'U Qx' 'missingField skip;')"
EXPECT[missing_skip]="^End"
FUNCS[unsupported]="$(m mesio1 'U phi' '')"
EXPECT[unsupported]="has unsupported type surfaceScalarField"
FUNCS[two_instances]="$(m mesio1 'U' '') $(m mesio2 'p' 'density 20; sampling cell; outputDir VDB2;')"
EXPECT[two_instances]="^End"
FUNCS[onerror_warn]="$(m mesio1 'U' 'outputDir "/proc/mesio_no_such_dir"; onError warn;')"
EXPECT[onerror_warn]="skipped \(onError warn\)"
FUNCS[onerror_error]="$(m mesio1 'U' 'outputDir "/proc/mesio_no_such_dir";')"
EXPECT[onerror_error]="Use 'onError warn'"

status=0
for t in stale_error stale_warn policy missing missing_skip unsupported two_instances onerror_warn onerror_error; do
    d=$RUNS/$t
    rm -rf "$d"; cp -r "$RUNS/base" "$d"
    printf '\nfunctions\n{\n    %s\n}\n' "${FUNCS[$t]}" >> "$d/system/controlDict"
    ${RUN} -n1 --mpi=pmix bash -c "${ENV}; cd $d && icoFoam" > "$d/log.icoFoam" 2>&1
    if grep -q -E "${EXPECT[$t]}" "$d/log.icoFoam"; then
        printf '%-14s PASS  (%s)\n' "$t" "$(grep -m1 -E "${EXPECT[$t]}" "$d/log.icoFoam" | sed 's/^ *//' | cut -c1-110)"
    else
        printf '%-14s FAIL\n' "$t"; status=1
    fi
done
# two instances: both outputs exist; onError warn: the run reaches End
ls $RUNS/two_instances/VDB/*.vdb $RUNS/two_instances/VDB2/*.vdb >/dev/null 2>&1 \
    && echo "two_instances  PASS  (VDB and VDB2 written)" || { echo "two_instances  FAIL  (missing output)"; status=1; }
grep -q "^End" $RUNS/onerror_warn/log.icoFoam \
    && echo "onerror_warn   PASS  (run reached End)" || { echo "onerror_warn   FAIL  (no End)"; status=1; }
exit $status
