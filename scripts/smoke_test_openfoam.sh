#!/bin/bash
# Smoke test for the OpenFOAM v2606 build: serial cavity + 4-rank parallel cavity.
#
# Run inside the Slurm allocation (single task step, uses mpirun for 4 ranks):
#   srun --jobid=5270670 --overlap -N1 -n1 -c 8 -w cn356 \
#       bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/smoke_test_openfoam.sh
#
# Run directory: /scratch/project/eu-25-121/milanjaros/openfoam/runs/smoke_cavity

set -e
OF_ROOT=/mnt/proj2/eu-25-121/milanjaros/openfoam
RUN_ROOT=/scratch/project/eu-25-121/milanjaros/openfoam/runs/smoke_cavity

# shellcheck disable=SC1091
source "$OF_ROOT/scripts/env_openfoam.sh"

echo "=== foamInstallationTest"
foamInstallationTest || true
echo "=== required binaries"
for app in icoFoam pimpleFoam simpleFoam blockMesh decomposePar reconstructPar snappyHexMesh; do
    printf '  %-16s %s\n' "$app" "$(command -v "$app" || echo MISSING)"
done

rm -rf "$RUN_ROOT"
mkdir -p "$RUN_ROOT"

# --- Serial run -------------------------------------------------------------
SERIAL="$RUN_ROOT/serial"
cp -r "$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity" "$SERIAL"
cd "$SERIAL"
blockMesh > log.blockMesh 2>&1
icoFoam   > log.icoFoam   2>&1
echo "=== serial: $(grep -c '^Time =' log.icoFoam) time steps, last: $(grep '^End' log.icoFoam || echo 'NO END')"
ls -d [0-9]* | tr '\n' ' '; echo

# --- Parallel run (4 ranks) ---------------------------------------------------
PAR="$RUN_ROOT/parallel4"
cp -r "$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity" "$PAR"
cd "$PAR"
cat > system/decomposeParDict <<'EOF'
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      decomposeParDict;
}
numberOfSubdomains 4;
method          scotch;
EOF
blockMesh    > log.blockMesh    2>&1
decomposePar > log.decomposePar 2>&1
# Inside a Slurm step, OpenMPI 5 (PRRTE) would try to start its daemons with
# srun and fail ("srun returned non-zero exit status ... per-node daemon").
# Disable the Slurm launcher/allocator so all ranks run on this node.
mpirun --prtemca plm ^slurm --prtemca ras ^slurm -np 4 --bind-to core \
    icoFoam -parallel > log.icoFoam 2>&1
reconstructPar -latestTime > log.reconstructPar 2>&1
echo "=== parallel: nProcs=$(grep -m1 '^nProcs' log.icoFoam), last: $(grep '^End' log.icoFoam || echo 'NO END')"

# --- Case prepared for a direct srun --mpi=pmix launch (run from outside) ----
SRUN="$RUN_ROOT/parallel4_srun"
cp -r "$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity" "$SRUN"
cp "$PAR/system/decomposeParDict" "$SRUN/system/"
( cd "$SRUN" && blockMesh > log.blockMesh 2>&1 && decomposePar > log.decomposePar 2>&1 )
echo "=== prepared $SRUN for: srun -n4 --mpi=pmix ... icoFoam -parallel"

# Compare final velocity field serial vs parallel (should agree to solver tolerance)
echo "=== serial vs parallel 0.5/U (first differing lines, if any)"
diff <(sed -n '/^internalField/,/^)/p' "$SERIAL/0.5/U" | head -50) \
     <(sed -n '/^internalField/,/^)/p' "$PAR/0.5/U" | head -50) | head -10 || true
echo "=== smoke test done"
