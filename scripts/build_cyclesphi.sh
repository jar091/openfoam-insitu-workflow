#!/bin/bash
# Build CyclesPhi standalone renderer ("cycles" binary, XML+BIN scene reader) for CPU.
# Run on a compute node, e.g.:
#   srun --jobid=<JOB> --overlap -N1 -n1 -w <node> bash scripts/build_cyclesphi.sh \
#        > build/logs/cyclesphi_build.log 2>&1
# Options (env): CLEAN=1 removes the build dir first; JOBS=<n> parallel jobs.
set -euo pipefail

source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_cyclesphi.sh

JOBS=${JOBS:-64}
LIBS_COMMIT=30d9f881c4b62c52323fd11637eeea56d460e35c   # pinned lib/linux_x64 submodule
LIBS_COPY_SRC=/mnt/proj1/open-36-34/milanjaros/projects/blender/src/cyclesphi/lib/linux_x64

# 1) Precompiled Blender libraries (OpenVDB/NanoVDB, OIIO, TBB, Embree, ...).
if [ ! -d "${CYCLESPHI_LIBS}/openvdb" ]; then
    mkdir -p "$(dirname "${CYCLESPHI_LIBS}")"
    if [ -d "${LIBS_COPY_SRC}/openvdb" ]; then
        echo "Copying precompiled libs from ${LIBS_COPY_SRC} (read-only source)"
        rsync -a --exclude=.git "${LIBS_COPY_SRC}/" "${CYCLESPHI_LIBS}/"
    else
        echo "Cloning precompiled libs (git-lfs needed) at ${LIBS_COMMIT}"
        export PATH=/home/milanjaros/git-lfs/bin:${PATH}
        git lfs install --skip-repo
        git clone --no-checkout https://projects.blender.org/blender/lib-linux_x64.git "${CYCLESPHI_LIBS}"
        git -C "${CYCLESPHI_LIBS}" checkout ${LIBS_COMMIT}
    fi
fi

# 2) Configure.
[ "${CLEAN:-0}" = "1" ] && rm -rf "${CYCLESPHI_BUILD}"
mkdir -p "${CYCLESPHI_BUILD}"
cd "${CYCLESPHI_BUILD}"

cmake "${CYCLESPHI_SRC}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${CYCLESPHI_INSTALL}" \
    -DCYCLES_LIB_DIR="${CYCLESPHI_LIBS}" \
    -DWITH_LIBS_PRECOMPILED=ON \
    -DWITH_CYCLESPHI=OFF \
    -DWITH_SPACE_CONVERTER=OFF \
    -DWITH_CLIENT_GPUJPEG=OFF \
    -DWITH_ZFP_LOADER=OFF \
    -DWITH_CYCLES_HYDRA_RENDER_DELEGATE=OFF \
    -DWITH_CYCLES_USD=OFF \
    -DWITH_CYCLES_OSL=OFF \
    -DWITH_CYCLES_ALEMBIC=OFF \
    -DWITH_CYCLES_DEVICE_CUDA=OFF \
    -DWITH_CYCLES_DEVICE_OPTIX=OFF \
    -DWITH_CYCLES_DEVICE_HIP=OFF \
    -DWITH_CYCLES_DEVICE_ONEAPI=OFF \
    -DWITH_CYCLES_OPENVDB=ON \
    -DWITH_CYCLES_NANOVDB=ON \
    -DWITH_CYCLES_EMBREE=ON \
    -DWITH_CYCLES_OPENIMAGEDENOISE=ON \
    -DWITH_CYCLES_PUGIXML=ON \
    -DWITH_CYCLES_STANDALONE_GUI=OFF

# 3) Build + install.
cmake --build . -j "${JOBS}" --target install

echo "Built: ${CYCLES_BIN}"
"${CYCLES_BIN}" --help | head -40 || true
