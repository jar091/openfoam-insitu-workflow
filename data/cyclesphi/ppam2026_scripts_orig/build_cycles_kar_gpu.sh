#!/bin/bash

ml purge

cd /mnt/proj1/open-36-34/milanjaros/multires/compare

ROOT_DIR=${PWD}

ml CUDA/13.0.0

ml tbb/2021.11.0-GCCcore-12.3.0
ml Mesa/24.1.3-GCCcore-13.3.0

ml CMake/3.31.3-GCCcore-14.2.0
ml GCC/14.2.0

export CC=gcc
export CXX=g++
##################################################

lib_dir=${ROOT_DIR}/install
output=${ROOT_DIR}/install/cyclesphi_kar
src=${ROOT_DIR}/src

# rm -rf ${ROOT_DIR}/build/cyclesphi_kar
# rm -rf ${ROOT_DIR}/install/cyclesphi_kar

#-----------blender_client--------------
mkdir ${ROOT_DIR}/build/cyclesphi_kar
cd ${ROOT_DIR}/build/cyclesphi_kar

make_d="${src}/cyclesphi"

make_d="${make_d} -DCMAKE_BUILD_TYPE=RelWithDebInfo"
#make_d="${make_d} -DCMAKE_BUILD_TYPE=Release"
#make_d="${make_d} -DCMAKE_BUILD_TYPE=Debug"

make_d="${make_d} -DCMAKE_INSTALL_PREFIX=${output}"

make_d="${make_d} -DWITH_CYCLES_HYDRA_RENDER_DELEGATE=OFF"
make_d="${make_d} -DWITH_CYCLES_USD=OFF"

make_d="${make_d} -Danari_DIR=/mnt/proj3/open-28-64/blender/salomon/projects/ingo/install/anari-sdk_kar_gpu/lib64/cmake/anari-0.16.0"
make_d="${make_d} -Dbraas_hpc_renderengine_DIR=/mnt/proj3/open-28-64/blender/salomon/projects/blender/install/braas-hpc-renderengine_kar/lib/cmake/braas_hpc_renderengine"

# make_d="${make_d} -DOPTIX_ROOT_DIR=$OptiX_INSTALL_DIR"
make_d="${make_d} -DCMAKE_CUDA_ARCHITECTURES=80"
make_d="${make_d} -DWITH_CYCLES_CUDA_BINARIES=ON"
make_d="${make_d} -DCYCLES_CUDA_BINARIES_ARCH=sm_80"
# #make_d="${make_d} -DCUDA_BINARIES_ARCH:STRING=sm_80"
# make_d="${make_d} -DWITH_CUDA_DYNLOAD=OFF"
make_d="${make_d} -DWITH_CYCLES_DEVICE_OPTIX=OFF"

make_d="${make_d} -DWITH_ZFP=ON"
make_d="${make_d} -DWITH_ZFP_LOADER=ON"
make_d="${make_d} -Dzfp_DIR=/mnt/proj1/open-36-34/milanjaros/projects/blender/install/zfp_kar/lib64/cmake/zfp"

make_d="${make_d} -DWITH_CLIENT_GPUJPEG=OFF"

cmake ${make_d}
#make clean
make -j 64 install

