#!/bin/bash
# CPU adaptation of ppam2026/run_render.sh (aircraft / OpenFOAM "ofstore" case):
# renders one VDB with the original ppam2026 XML scene (+ .xml.bin) using the
# workspace CyclesPhi build. Input VDB is read in place (read-only), output to scratch.
#
# Usage: run_render_ppam_cpu.sh [vdb] [grid] [scene_template] [WxH] [samples]
set -euo pipefail
source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_cyclesphi.sh

VDB=${1:-/mnt/proj1/open-36-34/milanjaros/multires/PPAM/aircraft_512/origin.vdb}
GRID=${2:-Q_in_nodes}
TEMPLATE=${3:-${OF_WS}/data/cyclesphi/scenes_ppam2026/openfoam_ofstore.512.xml}
RES=${4:-640x360}
SAMPLES=${5:-16}
OUT_DIR=${OUT_DIR:-${OF_SCRATCH}/renders/cyclesphi_test}
# OCIO config from ppam2026 (AgX view, as in the original renders)
export OCIO=${OF_WS}/data/cyclesphi/colormanagement/config.ocio

mkdir -p "${OUT_DIR}/scene"
name=$(basename "${TEMPLATE%.xml}")
XML=${OUT_DIR}/scene/${name}.xml
sed -e "s|{GRID_NAME}|${GRID}|g" -e "s|{VDB_DATA}|${VDB}|g" "${TEMPLATE}" > "${XML}"
ln -sf "${TEMPLATE}.bin" "${XML}.bin"

PNG=${OUT_DIR}/${name}.$(basename "${VDB%.vdb}").cpu.png
echo "Rendering ${VDB} (${GRID}) -> ${PNG}"
time "${CYCLES_BIN}" --device CPU --threads "$(nproc)" --samples "${SAMPLES}" \
    --width "${RES%x*}" --height "${RES#*x}" --log-level info \
    --output "${PNG}" "${XML}"
