#!/bin/bash
# Build the MESIO in-situ test driver (run on a compute node).
#   MESIO_VARIANT=dev  -> links install/mesio-dev, binary build/mesio_tests/insitu_driver-dev
#   DRIVER_FLAGS       extra compiler/linker flags (e.g. -fsanitize=address for the asan variant)
set -euo pipefail
PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
source ${PROJ}/scripts/env_mesio.sh >/dev/null 2>&1
mkdir -p ${PROJ}/build/mesio_tests
OUT=${PROJ}/build/mesio_tests/insitu_driver${MESIO_VARIANT:+-${MESIO_VARIANT}}
mpicxx -std=c++17 -O2 -g -Wall ${DRIVER_FLAGS:-} ${PROJ}/data/mesio_tests/insitu_driver.cpp \
    -I${MESIO_ROOT}/include -DMESIO_INT_WIDTH=32 -I${OPENVDB_ROOT}/include \
    -L${MESIO_ROOT}/lib64 -Wl,-rpath,${MESIO_ROOT}/lib64 -lmesioapi \
    -L${OPENVDB_ROOT}/lib -Wl,-rpath,${OPENVDB_ROOT}/lib -lopenvdb -ltbb \
    -o ${OUT}
echo "built ${OUT}"
