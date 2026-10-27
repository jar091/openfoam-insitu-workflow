#!/bin/bash

cd /mnt/proj1/open-36-34/milanjaros/multires/compare

ROOT_DIR=${PWD}

ml tbb/2021.11.0-GCCcore-12.3.0
ml Mesa/24.1.3-GCCcore-13.3.0

ml CMake/3.31.3-GCCcore-14.2.0
ml GCC/14.2.0

export CC=gcc
export CXX=g++

lib_dir=${ROOT_DIR}/install
output=${ROOT_DIR}/install/cyclesphi_kar #cyclesphi_kar
src=${ROOT_DIR}/src

results_dir=${ROOT_DIR}/results/${USER}
mkdir -p ${results_dir}

export LD_LIBRARY_PATH=/mnt/proj3/open-28-64/blender/salomon/projects/blender/install/braas-hpc-renderengine_kar/lib:$LD_LIBRARY_PATH
export OCIO=/mnt/proj1/open-36-34/milanjaros/multires/final_data/scenes/colormanagement/config.ocio

#export CUDA_VISIBLE_DEVICES=1
#${output}/cyclesphi --scene /mnt/proj1/open-36-34/milanjaros/multires/final_data/scenes/GADGET_grid_origin_1761431669.124614.xml --device CPU --port 8007

SCENES=/mnt/proj1/open-36-34/milanjaros/multires/final_data/scenes
VDBS=/mnt/proj1/open-36-34/milanjaros/multires/final_data
#<attribute name="{GRID_NAME}" std="ATTR_STD_VOLUME_DENSITY" type="float" element="ATTR_ELEMENT_VOXEL" flags="0" buffer="{VDB_DATA}" volume_type="openvdb"/>


GRID=density
for NAME in "wdas_cloud" "GADGET_grid_origin_1761431669.124614" "GADGET_PICCOLO_DM_Halos_Velocities" "JHTDB_iso1024fine_pressure_float1" "JHTDB_isotropic1024fine_velocity_full" "CHANGA_galaxy3000"
do
    VDB=${VDBS}/${NAME}.vdb
    echo "Rendering ... $VDB"

    sed -e "s|{GRID_NAME}|$GRID|g" \
        -e "s|{VDB_DATA}|$VDB|g" \
        ${SCENES}/${NAME}.xml > ${results_dir}/$NAME.xml

    cp ${SCENES}/${NAME}.xml.bin ${results_dir}/$NAME.xml.bin

    ${output}/cycles --device CPU  --samples 128 --threads 128 --output ${results_dir}/${NAME}.png ${results_dir}/$NAME.xml
done

GRID=Q_in_nodes
for NAME in "openfoam_ofstore.4000"
do
    VDB=${VDBS}/${NAME}.vdb
    echo "Rendering ... $VDB"

    sed -e "s|{GRID_NAME}|$GRID|g" \
        -e "s|{VDB_DATA}|$VDB|g" \
        ${SCENES}/${NAME}.xml > ${results_dir}/$NAME.xml

    cp ${SCENES}/${NAME}.xml.bin ${results_dir}/$NAME.xml.bin

    ${output}/cycles --device CPU  --samples 128 --threads 128 --output ${results_dir}/${NAME}.png ${results_dir}/$NAME.xml
done

########################################################################################################################################
#openfoam_ofstore.4000
# ${output}/cycles --device CPU  --samples 128 --threads 128 --output ${results_dir}/openfoam_ofstore.4000.png ${SCENES}/openfoam_ofstore.4000.xml

#GADGET_grid_origin_1761431669.124614
#${output}/cycles --device CPU  --samples 128 --threads 128 --output ${results_dir}/GADGET_grid_origin_1761431669.124614.png ${SCENES}/GADGET_grid_origin_1761431669.124614.xml

#CHANGA_galaxy3000
#${output}/cycles --device CPU  --samples 128 --threads 128 --output ${results_dir}/CHANGA_galaxy3000.png ${SCENES}/CHANGA_galaxy3000.xml

#GADGET_PICCOLO_DM_Halos_Velocities
# ${output}/cycles --device CPU  --samples 128 --threads 128 --output ${results_dir}/GADGET_PICCOLO_DM_Halos_Velocities.png ${SCENES}/GADGET_PICCOLO_DM_Halos_Velocities.xml

#JHTDB_iso1024fine_pressure_float1
# ${output}/cycles --device CPU  --samples 128 --threads 128 --output ${results_dir}/JHTDB_iso1024fine_pressure_float1.png ${SCENES}/JHTDB_iso1024fine_pressure_float1.xml

#JHTDB_isotropic1024fine_velocity_full
# ${output}/cycles --device CPU  --samples 128 --threads 128 --output ${results_dir}/JHTDB_isotropic1024fine_velocity_full.png ${SCENES}/JHTDB_isotropic1024fine_velocity_full.xml

