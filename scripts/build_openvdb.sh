#!/bin/bash
# Build oneTBB, c-blosc and OpenVDB (+ vdb_print) from source with foss/2025b.
# No foss/2025b-compatible TBB/Blosc/OpenVDB modules exist on the system
# (only OpenVDB/11.0.0-foss-2022b), Boost/1.88.0-GCC-14.3.0 is taken from modules.
#
# Run on a compute node, e.g.:
#   srun --jobid=5270670 --overlap -N1 -n1 -w cn357 bash scripts/build_openvdb.sh \
#        > build/logs/build_openvdb.log 2>&1
set -euo pipefail

PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
source ${PROJ}/scripts/env_mesio.sh

TBB_VERSION=2021.13.0
BLOSC_VERSION=1.21.6
OPENVDB_VERSION=12.0.1
NPROC=${NPROC:-32}

PREFIX=${OPENVDB_ROOT}
DL=${PROJ}/build/deps/download
SRC=${PROJ}/build/deps/src
BLD=${PROJ}/build/deps/build
mkdir -p ${DL} ${SRC} ${BLD} ${PREFIX}

fetch() { # url file
    [ -f "${DL}/$2" ] || curl -L --fail -o "${DL}/$2" "$1"
}
unpack() { # file dir
    if [ ! -d "${SRC}/$2" ]; then
        mkdir -p "${SRC}/$2"
        tar -xzf "${DL}/$1" -C "${SRC}/$2" --strip-components=1
    fi
}

fetch https://github.com/uxlfoundation/oneTBB/archive/refs/tags/v${TBB_VERSION}.tar.gz oneTBB-${TBB_VERSION}.tar.gz
fetch https://github.com/Blosc/c-blosc/archive/refs/tags/v${BLOSC_VERSION}.tar.gz c-blosc-${BLOSC_VERSION}.tar.gz
fetch https://github.com/AcademySoftwareFoundation/openvdb/archive/refs/tags/v${OPENVDB_VERSION}.tar.gz openvdb-${OPENVDB_VERSION}.tar.gz
unpack oneTBB-${TBB_VERSION}.tar.gz oneTBB-${TBB_VERSION}
unpack c-blosc-${BLOSC_VERSION}.tar.gz c-blosc-${BLOSC_VERSION}
unpack openvdb-${OPENVDB_VERSION}.tar.gz openvdb-${OPENVDB_VERSION}

# --- oneTBB -------------------------------------------------------------------
cmake -S ${SRC}/oneTBB-${TBB_VERSION} -B ${BLD}/oneTBB -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=${PREFIX} -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
    -DTBB_TEST=OFF -DTBB_EXAMPLES=OFF -DTBB_STRICT=OFF -DTBBMALLOC_BUILD=ON
cmake --build ${BLD}/oneTBB -j ${NPROC}
cmake --install ${BLD}/oneTBB

# --- c-blosc ------------------------------------------------------------------
cmake -S ${SRC}/c-blosc-${BLOSC_VERSION} -B ${BLD}/c-blosc -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=${PREFIX} -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_C_COMPILER=gcc \
    -DBUILD_TESTS=OFF -DBUILD_BENCHMARKS=OFF -DBUILD_FUZZERS=OFF \
    -DBUILD_SHARED=ON -DBUILD_STATIC=OFF -DPREFER_EXTERNAL_ZLIB=ON
cmake --build ${BLD}/c-blosc -j ${NPROC}
cmake --install ${BLD}/c-blosc

# --- OpenVDB ------------------------------------------------------------------
cmake -S ${SRC}/openvdb-${OPENVDB_VERSION} -B ${BLD}/openvdb -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=${PREFIX} -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
    -DCMAKE_PREFIX_PATH=${PREFIX} \
    -DTBB_ROOT=${PREFIX} -DBlosc_ROOT=${PREFIX} -DBOOST_ROOT=${EBROOTBOOST} \
    -DOPENVDB_BUILD_CORE=ON -DOPENVDB_CORE_SHARED=ON -DOPENVDB_CORE_STATIC=OFF \
    -DOPENVDB_BUILD_BINARIES=ON -DOPENVDB_BUILD_VDB_PRINT=ON -DOPENVDB_BUILD_VDB_LOD=OFF \
    -DOPENVDB_BUILD_VDB_RENDER=OFF -DOPENVDB_BUILD_VDB_VIEW=OFF -DOPENVDB_BUILD_VDB_TOOL=OFF \
    -DOPENVDB_BUILD_PYTHON_MODULE=OFF -DOPENVDB_BUILD_UNITTESTS=OFF -DOPENVDB_BUILD_DOCS=OFF \
    -DOPENVDB_BUILD_NANOVDB=OFF -DOPENVDB_BUILD_AX=OFF \
    -DUSE_BLOSC=ON -DUSE_ZLIB=ON -DUSE_IMATH_HALF=OFF -DUSE_EXR=OFF -DUSE_PNG=OFF \
    -DOPENVDB_USE_DELAYED_LOADING=OFF -DUSE_EXPLICIT_INSTANTIATION=ON
cmake --build ${BLD}/openvdb -j ${NPROC}
cmake --install ${BLD}/openvdb

echo "OpenVDB ${OPENVDB_VERSION} installed into ${PREFIX}"
ls -l ${PREFIX}/lib ${PREFIX}/bin
