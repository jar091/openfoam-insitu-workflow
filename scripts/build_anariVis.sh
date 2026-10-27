#!/bin/bash
# Build the anariVis OpenFOAM module (function object library + anariVisRender)
# with wmake on a compute node:
#   srun --jobid=5270670 --overlap -N1 -n1 -c 32 -w <node> \
#       bash scripts/build_anariVis.sh > build/logs/anariVis_build.log 2>&1
set -e
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_anari_openfoam.sh
cd /mnt/proj2/eu-25-121/milanjaros/openfoam/src/openfoam-insitu-modules/anariVis
./Allwmake -j 16
ls -l "$ANARIVIS_LIBBIN/libanariVis.so" "$ANARIVIS_BINDIR/anariVisRender"
