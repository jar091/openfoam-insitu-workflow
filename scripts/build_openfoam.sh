#!/bin/bash
# Build OpenFOAM v2606 (core, no ParaView reader plugins) on a Karolina compute node.
#
# Run inside the Slurm allocation, e.g.:
#   srun --jobid=5270670 --overlap -N1 -n1 -w cn356 \
#       bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/build_openfoam.sh
#
# Log: build/logs/openfoam_build.log (Allwmake also writes log.<arch> in the source tree)

OF_ROOT=/mnt/proj2/eu-25-121/milanjaros/openfoam
LOG_DIR="$OF_ROOT/build/logs"
LOG="$LOG_DIR/openfoam_build.log"
NPROCS="${NPROCS:-128}"
mkdir -p "$LOG_DIR"

# shellcheck disable=SC1091
source "$OF_ROOT/scripts/env_openfoam.sh" || { echo "env setup failed"; exit 1; }
export WM_NCOMPPROCS="$NPROCS"

cd "$WM_PROJECT_DIR" || exit 1

{
    echo "=== OpenFOAM build started $(date) on $(hostname)"
    echo "WM_PROJECT_DIR=$WM_PROJECT_DIR"
    echo "WM_OPTIONS=$WM_OPTIONS WM_MPLIB=$WM_MPLIB FOAM_MPI=$FOAM_MPI MPI_ARCH_PATH=$MPI_ARCH_PATH"
    echo "FOAM_EXTRA_CXXFLAGS=$FOAM_EXTRA_CXXFLAGS"
    module list 2>&1
    echo "--- third-party detection"
    for pkg in metis scotch kahip cgal boost fftw readline; do
        sh "wmake/scripts/have_$pkg" -test 2>&1 | sed "s/^/  [$pkg] /"
    done
    echo "--- Allwmake"
    time ./Allwmake -j "$NPROCS" -s -l "$@"
    rc=$?
    echo "=== Allwmake exit code: $rc ($(date))"
    echo "--- foamInstallationTest"
    foamInstallationTest
    exit $rc
} > "$LOG" 2>&1
