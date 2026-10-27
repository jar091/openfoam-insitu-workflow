#!/bin/bash
#SBATCH -A OPEN-28-64
#SBATCH -p qgpu
#SBATCH -N 1
#SBATCH -n 8
#SBATCH --gpus 8
#SBATCH -t 04:00:00

cd /mnt/proj1/open-36-34/milanjaros/projects/blender

ROOT_DIR=${PWD}

ml tbb/2021.11.0-GCCcore-12.3.0
ml Mesa/24.1.3-GCCcore-13.3.0

ml CMake/3.31.3-GCCcore-14.2.0
ml OpenMPI/5.0.5-NVHPC-24.3-CUDA-12.3.0
# ml CUDA/12.8.0
ml CUDA/13.0.0
# ml GCC/12.2.0
#ml OpenMPI/4.1.6-NVHPC-25.3-CUDA-12.8.0
ml GCC/14.2.0

export CC=gcc
export CXX=g++
##################################################

lib_dir=${ROOT_DIR}/install
output=${ROOT_DIR}/install/cyclesphi_kar_tools
src=${ROOT_DIR}/src


export LD_LIBRARY_PATH=${src}/cyclesphi/lib/linux_x64/openvdb/lib:${src}/cyclesphi/lib/linux_x64/tbb/lib:$LD_LIBRARY_PATH

export LD_LIBRARY_PATH=/mnt/proj1/open-36-34/milanjaros/projects/blender/install/zfp_kar/lib64:$LD_LIBRARY_PATH
export OCIO=/mnt/proj1/open-36-34/milanjaros/multires/final_data/scenes/colormanagement/config.ocio

# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/nanovdb_multires_convert
# -- Installing: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/nanovdb_derivates_convert
# -- Installing: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/nanovdb_derivates_convert_vec4
# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/downsampled_vdb
# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/compare_vdb
# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/derivates_bin_to_dense_vdb
# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/hierarchical_compression_vdb
# /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/openvdb_to_nanovdb


# jaromila@uan03:/mnt/proj1/open-36-34/milanjaros/multires/PPAM/${DATASET}> ls
# psnr.020.f.vdb  psnr.030.f.vdb  psnr.040.f.vdb  psnr.050.f.vdb  psnr.060.f.vdb  psnr.070.f.vdb  psnr.080.f.vdb  psnr.100.f.vdb  psnr.120.f.vdb  psnr.140.f.vdb  psnr.160.f.vdb  psnr.180.f.vdb
# psnr.020.m.vdb  psnr.030.m.vdb  psnr.040.m.vdb  psnr.050.m.vdb  psnr.060.m.vdb  psnr.070.m.vdb  psnr.080.m.vdb  psnr.100.m.vdb  psnr.120.m.vdb  psnr.140.m.vdb  psnr.160.m.vdb  psnr.180.m.vdb

# export DATASET=$1
# export GRID=$2

# #nanovdb_derivates_convert
# VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/${DATASET}/vdb
# OUT_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/${DATASET}/png
# OUT_NVDB_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/${DATASET}/nvdb_m_g1
# mkdir -p $OUT_FOLDER
# for f in $VDB_FOLDER/*.m.vdb; do
#     output_file="${OUT_FOLDER}/$(basename "${f%.m.vdb}.png")"
#     input_file="${OUT_NVDB_FOLDER}/$(basename "${f%.m.vdb}.bin")"

#     VDB=${input_file}
#     echo "Rendering ... $VDB"

#     sed -e "s|{GRID_NAME}|$GRID|g" \
#         -e "s|{VDB_DATA}|$VDB|g" \
#         ${VDB_FOLDER}/../scene/template > ${VDB_FOLDER}/../scene/scene.xml

#     /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cycles --device CPU  --samples 128 --threads 128 --output ${output_file} ${VDB_FOLDER}/../scene/scene.xml #> ${output_file}.log 2>&1   
# done

# VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/vdb_m
# OUT_NVDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/nanovdb_m

########################################################################################################################
# DATASET=aircraft_512
# GRID=Q_in_nodes

# VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/${DATASET}/vdb
# OUT_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/${DATASET}/vdb_png

# #origin.vdb
# output_file="${OUT_FOLDER}/origin_v4.png"
# #input_file="${OUT_NVDB_FOLDER}/$(basename "${f%.vdb}.bin")"

# # VDB=${input_file}
# VDB=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/origin.vdb
# echo "Rendering ... $VDB"

# sed -e "s|{GRID_NAME}|$GRID|g" \
#     -e "s|{VDB_DATA}|$VDB|g" \
#     ${VDB_FOLDER}/../scene/template > ${VDB_FOLDER}/../scene/scene.xml

# # /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cycles --device CPU  --samples 128 --threads 128 --output ${output_file} ${VDB_FOLDER}/../scene/scene.xml > ${output_file}.log 2>&1   

# #multires
# #OUT_NVDB_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/${DATASET}/nanovdb_m
# mkdir -p $OUT_FOLDER
# for f in $VDB_FOLDER/psnr.050.vdb; do
#     output_file="${OUT_FOLDER}/$(basename "${f%.vdb}.fine.closest.png")"
#     #input_file="${OUT_NVDB_FOLDER}/$(basename "${f%.vdb}.bin")"

#     # VDB=${input_file}
#     VDB=${f}
#     echo "Rendering ... $VDB"

#     sed -e "s|{GRID_NAME}|$GRID|g" \
#         -e "s|{VDB_DATA}|$VDB|g" \
#         ${VDB_FOLDER}/../scene/template > ${VDB_FOLDER}/../scene/scene.xml

#     export CUDA_VISIBLE_DEVICES=0
#     # /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cycles --device CUDA  --samples 128 --threads 128 --output ${output_file} ${VDB_FOLDER}/../scene/scene.xml > ${output_file}.log 2>&1   
#     # /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cyclesphi --device CUDA  --scene ${VDB_FOLDER}/../scene/scene.xml --port 7000
# done

# VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/nanovdb_m
# mkdir -p $OUT_FOLDER
# for f in $VDB_FOLDER/psnr.050.bin; do
#     output_file="${OUT_FOLDER}/$(basename "${f%.bin}.png")"
#     #input_file="${OUT_NVDB_FOLDER}/$(basename "${f%.vdb}.bin")"

#     # VDB=${input_file}
#     VDB=${f}
#     echo "Rendering ... $VDB"

#     sed -e "s|{GRID_NAME}|$GRID|g" \
#         -e "s|{VDB_DATA}|$VDB|g" \
#         /mnt/proj1/open-36-34/milanjaros/multires/final_data/scenes/openfoam_ofstore.512_multires.xml > ${VDB_FOLDER}/../scene/scene.xml

#     /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cycles --device CUDA --samples 128 --threads 128 --log-level info --output ${output_file} ${VDB_FOLDER}/../scene/scene.xml #> ${output_file}.log 2>&1

#     # export CUDA_VISIBLE_DEVICES=0
#     # /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cyclesphi --device CUDA  --scene ${VDB_FOLDER}/../scene/scene.xml --port 7000
# done

########################################################################################################################
export CUDA_VISIBLE_DEVICES=0
DATASET=aircraft_512
GRID=Q_in_nodes

OUT_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/${DATASET}/nanovdb_var_png

# VDB_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/aircraft_512/nanovdb_var
# mkdir -p $OUT_FOLDER
# for f in $VDB_FOLDER/*.bin; do   
#     VDB=${f}
#     echo "Rendering ... $VDB"

#     sed -e "s|{GRID_NAME}|$GRID|g" \
#         -e "s|{VDB_DATA}|$VDB|g" \
#         /mnt/proj1/open-36-34/milanjaros/multires/final_data/scenes/openfoam_ofstore.512_multires.xml > ${VDB_FOLDER}/../scene/scene.xml

#     output_file="${OUT_FOLDER}/$(basename "${f%.bin}.cpu.png")"
#     /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cycles --device CPU --samples 128 --threads 128 --log-level info --output ${output_file} ${VDB_FOLDER}/../scene/scene.xml > ${output_file}.cpu.log 2>&1

#     output_file="${OUT_FOLDER}/$(basename "${f%.bin}.cuda.png")"
#     /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cycles --device CUDA --samples 128 --threads 128 --log-level info --output ${output_file} ${VDB_FOLDER}/../scene/scene.xml > ${output_file}.cuda.log 2>&1
# done

VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/nanovdb_m
mkdir -p $OUT_FOLDER
for f in $VDB_FOLDER/psnr.050.bin; do
    output_file="${OUT_FOLDER}/$(basename "${f%.bin}.png")"
    #input_file="${OUT_NVDB_FOLDER}/$(basename "${f%.vdb}.bin")"

    # VDB=${input_file}
    VDB=${f}
    echo "Rendering ... $VDB"

    sed -e "s|{GRID_NAME}|$GRID|g" \
        -e "s|{VDB_DATA}|$VDB|g" \
        /mnt/proj1/open-36-34/milanjaros/multires/final_data/scenes/openfoam_ofstore.512_multires.xml > ${VDB_FOLDER}/../scene/scene.xml

    /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cycles --device CUDA --samples 128 --log-level info --output ${output_file} ${VDB_FOLDER}/../scene/scene.xml #> ${output_file}.log 2>&1

    # export CUDA_VISIBLE_DEVICES=0
    # /mnt/proj1/open-36-34/milanjaros/multires/compare/install/cyclesphi_kar/cyclesphi --device CUDA  --scene ${VDB_FOLDER}/../scene/scene.xml --port 7000
done