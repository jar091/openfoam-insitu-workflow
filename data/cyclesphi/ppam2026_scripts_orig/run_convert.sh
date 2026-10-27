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
ml CUDA/12.8.0
# ml CUDA/13.0.0
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

# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/nanovdb_multires_convert
# -- Installing: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/convert_vdb_to_nanovdb_derivates
# -- Installing: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/convert_vdb_to_nanovdb_derivates_vec4
# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/downsampled_vdb
# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/compare_vdb
# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/derivates_bin_to_dense_vdb
# -- Up-to-date: /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/hierarchical_compression_vdb
# /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/openvdb_to_nanovdb


# jaromila@uan03:/mnt/proj1/open-36-34/milanjaros/multires/PPAM/${DATASET}> ls
# psnr.020.f.vdb  psnr.030.f.vdb  psnr.040.f.vdb  psnr.050.f.vdb  psnr.060.f.vdb  psnr.070.f.vdb  psnr.080.f.vdb  psnr.100.f.vdb  psnr.120.f.vdb  psnr.140.f.vdb  psnr.160.f.vdb  psnr.180.f.vdb
# psnr.020.m.vdb  psnr.030.m.vdb  psnr.040.m.vdb  psnr.050.m.vdb  psnr.060.m.vdb  psnr.070.m.vdb  psnr.080.m.vdb  psnr.100.m.vdb  psnr.120.m.vdb  psnr.140.m.vdb  psnr.160.m.vdb  psnr.180.m.vdb

# export DATASET=$1

# #convert_vdb_to_nanovdb_derivates
# VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/${DATASET}/vdb
# OUT_NVDB_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/${DATASET}/nvdb_m_g1
# mkdir -p $OUT_NVDB_FOLDER
# for f in $VDB_FOLDER/*.m.vdb; do
#     echo "Processing $f"
#     output_file="${OUT_NVDB_FOLDER}/$(basename "${f%.m.vdb}.bin")"

#     if [ -f "$output_file" ]; then
#         echo "Output file $output_file already exists, skipping conversion."
#     else
#         echo "Converting $f to ${output_file}"
#         /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/convert_vdb_to_nanovdb_derivates "$f" "${output_file}" > "${output_file}.log" 2>&1
#     fi
# done

#convert_vdb_to_nanovdb_derivates_vec4
# VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/${DATASET}/vdb
# OUT_NVDB_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/${DATASET}/nvdb_m
# mkdir -p $OUT_NVDB_FOLDER
# for f in $VDB_FOLDER/*.m.vdb; do
#     echo "Processing $f"
#     output_file="${OUT_NVDB_FOLDER}/$(basename "${f%.m.vdb}.bin")"

#     if [ -f "$output_file" ]; then
#         echo "Output file $output_file already exists, skipping conversion."
#     else
#         echo "Converting $f to ${output_file}"
#         /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/convert_vdb_to_nanovdb_derivates_vec4 "$f" "${output_file}" > "${output_file}.log" 2>&1
#     fi
# done


# #convert_vdb_to_nanovdb_derivates
# VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/vdb_m
# OUT_NVDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/nanovdb_m
# mkdir -p $OUT_NVDB_FOLDER
# for f in $VDB_FOLDER/*.vdb; do
#     echo "Processing $f"
#     output_file="${OUT_NVDB_FOLDER}/$(basename "${f%.vdb}.bin")"

#     # if [ -f "$output_file" ]; then
#     #     echo "Output file $output_file already exists, skipping conversion."
#     # else
#         echo "Converting $f to ${output_file}"
#         /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/convert_vdb_to_nanovdb_derivates "$f" "${output_file}" > "${output_file}.log" 2>&1
#     # fi
# done

##################################################################################aircraft_512
VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/vdb_m
OUT_NVDB_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/aircraft_512_vec4/nanovdb_m

# rm -rf $OUT_NVDB_FOLDER
mkdir -p $OUT_NVDB_FOLDER

for f in $VDB_FOLDER/psnr.*.vdb; do
    echo "Processing $f"
    output_file="${OUT_NVDB_FOLDER}/$(basename "${f%.vdb}.bin")"

    # if [ -f "$output_file" ]; then
    #     echo "Output file $output_file already exists, skipping conversion."
    # else
        echo "Converting $f to ${output_file}"
        # /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/convert_vdb_to_nanovdb_derivates_vec4 "$f" "${output_file}" > "${output_file}.log" 2>&1
    # fi
done
##################################################################################galaxy_bfield_dense_512
VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/galaxy_bfield_dense_512/vdb_m
OUT_NVDB_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/galaxy_bfield_dense_512_vec4/nanovdb_m

# rm -rf $OUT_NVDB_FOLDER
mkdir -p $OUT_NVDB_FOLDER

for f in $VDB_FOLDER/psnr.*.vdb; do
    echo "Processing $f"
    output_file="${OUT_NVDB_FOLDER}/$(basename "${f%.vdb}.bin")"

    # if [ -f "$output_file" ]; then
    #     echo "Output file $output_file already exists, skipping conversion."
    # else
        echo "Converting $f to ${output_file}"
        # /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/convert_vdb_to_nanovdb_derivates_vec4 "$f" "${output_file}" > "${output_file}.log" 2>&1
    # fi
done
##################################################################################gadget_grid
VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/gadget_grid/vdb_m
OUT_NVDB_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/gadget_grid_vec4/nanovdb_m

# rm -rf $OUT_NVDB_FOLDER
mkdir -p $OUT_NVDB_FOLDER

for f in $VDB_FOLDER/psnr.*.vdb; do
    echo "Processing $f"
    output_file="${OUT_NVDB_FOLDER}/$(basename "${f%.vdb}.bin")"

    # if [ -f "$output_file" ]; then
    #     echo "Output file $output_file already exists, skipping conversion."
    # else
        echo "Converting $f to ${output_file}"
        # /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/convert_vdb_to_nanovdb_derivates_vec4 "$f" "${output_file}" > "${output_file}.log" 2>&1
    # fi
done
##################################################################################aircraft
VDB_FOLDER=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft/vdb_m
OUT_NVDB_FOLDER=/scratch/project/open-36-34/milanjaros/multires/PPAM/aircraft_vec4/nanovdb_m

# rm -rf $OUT_NVDB_FOLDER
mkdir -p $OUT_NVDB_FOLDER

for f in $VDB_FOLDER/psnr.*.vdb; do
    echo "Processing $f"
    output_file="${OUT_NVDB_FOLDER}/$(basename "${f%.vdb}.bin")"

    # if [ -f "$output_file" ]; then
    #     echo "Output file $output_file already exists, skipping conversion."
    # else
        echo "Converting $f to ${output_file}"
        # /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/convert_vdb_to_nanovdb_derivates_vec4 "$f" "${output_file}" > "${output_file}.log" 2>&1
    # fi
done

# ORIGIN_VDB=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/origin.vdb
# ORIGIN_NVDB=/scratch/project/open-36-34/milanjaros/multires/PPAM/aircraft_512_vec4/nanovdb_m/origin.nvdb
# echo "Converting $ORIGIN_VDB to ${ORIGIN_NVDB}"
# /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/openvdb_to_nanovdb ${ORIGIN_VDB} ${ORIGIN_NVDB} > ${ORIGIN_NVDB}.log 2>&1

# ORIGIN_VDB=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/galaxy_bfield_dense_512/origin.vdb
# ORIGIN_NVDB=/scratch/project/open-36-34/milanjaros/multires/PPAM/galaxy_bfield_dense_512_vec4/nanovdb_m/origin.nvdb
# echo "Converting $ORIGIN_VDB to ${ORIGIN_NVDB}"
# /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/openvdb_to_nanovdb ${ORIGIN_VDB} ${ORIGIN_NVDB} > ${ORIGIN_NVDB}.log 2>&1

# ORIGIN_VDB=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/gadget_grid/origin.vdb
# ORIGIN_NVDB=/scratch/project/open-36-34/milanjaros/multires/PPAM/gadget_grid_vec4/nanovdb_m/origin.nvdb
# echo "Converting $ORIGIN_VDB to ${ORIGIN_NVDB}"
# /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/openvdb_to_nanovdb ${ORIGIN_VDB} ${ORIGIN_NVDB} > ${ORIGIN_NVDB}.log 2>&1

# ORIGIN_VDB=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft/origin.vdb
# ORIGIN_NVDB=/scratch/project/open-36-34/milanjaros/multires/PPAM/aircraft_vec4/nanovdb_m/origin.nvdb
# echo "Converting $ORIGIN_VDB to ${ORIGIN_NVDB}"
# /mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/openvdb_to_nanovdb ${ORIGIN_VDB} ${ORIGIN_NVDB} > ${ORIGIN_NVDB}.log 2>&1


ORIGIN_VDB=/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/origin4k_v2.vdb
ORIGIN_NVDB=/scratch/project/open-36-34/milanjaros/multires/PPAM/aircraft_vec4/nanovdb_m/origin4k_v2.nvdb
echo "Converting $ORIGIN_VDB to ${ORIGIN_NVDB}"
/mnt/proj1/open-36-34/milanjaros/projects/blender/install/cyclesphi_kar_tools/bin/openvdb_to_nanovdb ${ORIGIN_VDB} ${ORIGIN_NVDB} > ${ORIGIN_NVDB}.log 2>&1


