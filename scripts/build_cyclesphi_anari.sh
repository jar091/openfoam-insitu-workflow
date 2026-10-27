#!/bin/bash
# Build and install the cyclesphi-anari ANARI device (libanari_library_cycles.so,
# CPU only: no CUDA/OptiX/HIP) into install/cyclesphi-anari.
#
# The 'cyclesphi' git submodule of src/cyclesphi-anari is not checked out; the
# pinned commit (07cda529e) is the same as src/cyclesphi, so the build uses an
# overlay source tree in build/cyclesphi-anari/src (symlinks to
# src/cyclesphi-anari/* plus cyclesphi -> src/cyclesphi). Neither source tree
# is modified, and src/cyclesphi's own build dir (build/cyclesphi_cpu) is not
# touched.
#
# Run on a compute node, e.g.:
#   srun --jobid=<JOB> --overlap -N1 -n1 -w <node> \
#     bash scripts/build_cyclesphi_anari.sh > build/logs/cyclesphi_anari_build.log 2>&1
# Options (env): CLEAN=1 removes the build dir first; JOBS=<n> parallel jobs.
set -euo pipefail

source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_cyclesphi_anari.sh

JOBS=${JOBS:-64}
SRC=${PROJ_ROOT}/src/cyclesphi-anari
CYCLESPHI_SRC=${PROJ_ROOT}/src/cyclesphi
TOP=${PROJ_ROOT}/build/cyclesphi-anari
OVERLAY=${TOP}/src
BLD=${TOP}/build

[ "${CLEAN:-0}" = "1" ] && rm -rf "${TOP}"
mkdir -p "${OVERLAY}" "${BLD}"

# 1) Overlay source tree.
for f in "${SRC}"/* "${SRC}"/.clang-format; do
  name=$(basename "${f}")
  [ "${name}" = "cyclesphi" ] && continue
  ln -sfn "${f}" "${OVERLAY}/${name}"
done
ln -sfn "${CYCLESPHI_SRC}" "${OVERLAY}/cyclesphi"

if [ ! -d "${CYCLESPHI_LIBS}/openvdb" ]; then
  echo "ERROR: Blender precompiled libs missing in ${CYCLESPHI_LIBS} (see scripts/build_cyclesphi.sh)" >&2
  exit 1
fi

# 2) Configure. Embree + OIDN + OpenVDB/NanoVDB from the Blender lib bundle.
cmake -S "${OVERLAY}" -B "${BLD}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="${CYCLES_ANARI_ROOT}" \
  -DCMAKE_PREFIX_PATH="${ANARI_ROOT}" \
  -DCMAKE_INSTALL_RPATH_USE_LINK_PATH=ON \
  -DWITH_LIBS_PRECOMPILED=ON \
  -DCYCLES_LIB_DIR="${CYCLESPHI_LIBS}" \
  -DANARI_CYCLES_USE_OPTIX=OFF \
  -DANARI_CYCLES_USE_OIDN=ON \
  -DOPENIMAGEDENOISE_ROOT_DIR="${CYCLESPHI_LIBS}/openimagedenoise" \
  -DWITH_CYCLES_EMBREE=ON \
  -DWITH_CYCLES_OPENVDB=ON \
  -DWITH_CYCLES_NANOVDB=ON \
  -DWITH_CYCLES_DEVICE_HIP=OFF \
  -DWITH_CYCLES_DEVICE_ONEAPI=OFF \
  -DWITH_CYCLES_OSL=OFF \
  -DWITH_CYCLES_USD=OFF \
  -DWITH_CYCLES_ALEMBIC=OFF \
  -DWITH_CYCLES_HYDRA_RENDER_DELEGATE=OFF \
  -DWITH_CYCLESPHI=OFF \
  -DWITH_SPACE_CONVERTER=OFF \
  -DWITH_CLIENT_GPUJPEG=OFF \
  -DWITH_ZFP_LOADER=OFF \
  -DWITH_CYCLES_STANDALONE_GUI=OFF \
  -DANARI_CYCLES_BUILD_TEST=ON

# 3) Build + install.
cmake --build "${BLD}" -j "${JOBS}"
cmake --install "${BLD}"
mkdir -p "${CYCLES_ANARI_ROOT}/bin"
cp -f "${BLD}/anari_cycles_test" "${CYCLES_ANARI_ROOT}/bin/"

echo "cyclesphi-anari installed into ${CYCLES_ANARI_ROOT}"
"${ANARI_ROOT}/bin/anariInfo" -l cycles 2>&1 | head -40 || true
