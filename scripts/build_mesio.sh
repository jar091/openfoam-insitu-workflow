#!/bin/bash
# Build the Mesio part of ESPRESO (src/espreso working tree, branch mjar/devel) as shared
# libraries with OpenVDB output, using foss/2025b. Requires scripts/build_openvdb.sh first.
#
# Run on a compute node, e.g.:
#   srun --jobid=5270670 --overlap -N1 -n1 -c 32 -w cn357 bash scripts/build_mesio.sh \
#        > build/logs/build_mesio.log 2>&1
#
# Environment:
#   MESIO_VARIANT  ""  (default) -> install/mesio,       build/espreso
#                  dev           -> install/mesio-dev,   build/espreso-dev
#                  next          -> install/mesio-next,  build/espreso-next  (any name works)
#   MODE           release (default) | devel | debug
#   CXXFLAGS_EXTRA extra compiler flags (e.g. "-fsanitize=address -fno-omit-frame-pointer";
#                  pass the same flags in LINKFLAGS)
#
# Results:
#   build/espreso[-<variant>]/          waf build directory (objects, libs, executables)
#   install/mesio[-<variant>]/lib64/    libnb*.so (mesio core libs) + libmesioapi.so
#   install/mesio[-<variant>]/bin/      mesio, test.mesio, ecfchecker
#   install/mesio[-<variant>]/include/  mesio.h, mesio_insitu.h (C APIs)
set -euo pipefail

PROJ=/mnt/proj2/eu-25-121/milanjaros/openfoam
source ${PROJ}/scripts/env_mesio.sh

NPROC=${NPROC:-32}
MODE=${MODE:-release}          # release | devel | debug
INTWIDTH=${INTWIDTH:-32}       # must match OpenFOAM label size (WM_LABEL_SIZE=32 by default)
CXXFLAGS_EXTRA=${CXXFLAGS_EXTRA:-}

cd ${ESPRESO_SRC}

# The repository is built as is (no patches): the in-situ API, OpenVDB writer and
# MPI fixes live in the espreso repository itself.
for f in include/mesio_insitu.h src/api/wrapper.mesio.insitu.cpp src/input/parsers/memory/memoryfvm.cpp; do
    [ -f "$f" ] || { echo "ERROR: ${ESPRESO_SRC}/$f missing (in-situ API not in the repository)" >&2; exit 1; }
done
grep -q "wrapper.mesio.insitu.cpp" wscript || { echo "ERROR: wscript does not build the in-situ API" >&2; exit 1; }
echo "== ${ESPRESO_SRC}: branch $(git rev-parse --abbrev-ref HEAD 2>/dev/null), HEAD $(git rev-parse --short HEAD 2>/dev/null)"
git status --short 2>/dev/null | sed 's/^/   /' || true

echo "== variant '${MESIO_VARIANT}': prefix ${MESIO_ROOT}, build ${ESPRESO_BUILD}, mode ${MODE}"

# waf keeps its lock file in the source dir; the build tree goes to ESPRESO_BUILD.
# Do not run two builds (variants) at the same time.
python3 waf configure \
    --out=${ESPRESO_BUILD} \
    --prefix=${MESIO_ROOT} \
    --mode=${MODE} \
    --intwidth=${INTWIDTH} \
    --cxx=g++ --mpicxx=mpic++ \
    --mpi-lib=openmpi \
    ${CXXFLAGS_EXTRA:+--cxxflags="${CXXFLAGS_EXTRA}"}

python3 waf build -j ${NPROC}
python3 waf install -j ${NPROC}

# The C API headers are not installed by waf.
mkdir -p ${MESIO_ROOT}/include
cp -f ${ESPRESO_SRC}/include/mesio.h ${ESPRESO_SRC}/include/mesio_insitu.h ${MESIO_ROOT}/include/

echo "== installed:"
ls -l ${MESIO_ROOT}/lib64 ${MESIO_ROOT}/bin ${MESIO_ROOT}/include
echo "== OpenVDB support:"
grep -E "HAVE_OPENVDB" ${ESPRESO_BUILD}/c4che/_cache.py || { echo "OpenVDB NOT detected" >&2; exit 1; }
