#!/bin/bash
# Render a series of OpenVDB files (one file per time step) with CyclesPhi on CPU.
#
# Usage:
#   render_vdb_series.sh <vdb_dir|glob> <grid_name> <out_dir> [WxH=1280x720] [samples=64]
#
# Examples (run on a compute node):
#   render_vdb_series.sh /scratch/.../case/vdb U_mag /scratch/.../renders/U_mag 1920x1080 128
#   render_vdb_series.sh '/scratch/.../case/vdb/Q_*.vdb' Q /scratch/.../renders/Q
#
# Environment knobs:
#   TEMPLATE=<xml>   use an existing XML template ({VDB_DATA}/{GRID_NAME} placeholders,
#                    with <xml>.bin next to it) instead of generating one
#   SCENE_ARGS="..." extra args for make_vdb_scene.py when generating the template, e.g.
#                    "--range 0 2.5 --colormap inferno --density 8 --azimuth 60 --up z"
#                    (without --range the value range of the FIRST file is used for all
#                    frames, so colours stay comparable across the series)
#   THREADS=<n>      render threads (default: all cores)
#   OCIO_VIEW=standard|agx  standard (default): colormap colours reproduced as given;
#                    agx: Blender AgX look (as in the ppam2026 renders)
#   FORCE=1          re-render frames whose PNG already exists
#   EXTRA_ARGS="..." extra args for the cycles binary (e.g. "--log-level info")
set -euo pipefail

if [ $# -lt 3 ]; then
    sed -n '2,25p' "$0"; exit 1
fi
VDB_IN=$1
GRID=$2
OUT_DIR=$3
RES=${4:-1280x720}
SAMPLES=${5:-64}
WIDTH=${RES%x*}
HEIGHT=${RES#*x}

source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_cyclesphi.sh
HERE=${OF_WS}/data/cyclesphi
THREADS=${THREADS:-$(nproc)}
if [ "${OCIO_VIEW:-standard}" = "standard" ]; then
    export OCIO=${HERE}/colormanagement/config_standard.ocio
else
    export OCIO=${HERE}/colormanagement/config.ocio
fi

# Collect input files (sorted).
if [ -d "${VDB_IN}" ]; then
    mapfile -t FILES < <(ls -1 "${VDB_IN}"/*.vdb | sort -V)
else
    mapfile -t FILES < <(ls -1 ${VDB_IN} | sort -V)
fi
[ ${#FILES[@]} -gt 0 ] || { echo "No .vdb files found for ${VDB_IN}"; exit 1; }
echo "Found ${#FILES[@]} VDB files, grid '${GRID}', output ${OUT_DIR} (${WIDTH}x${HEIGHT}, ${SAMPLES} spp)"

SCENE_DIR=${OUT_DIR}/scene
mkdir -p "${OUT_DIR}" "${SCENE_DIR}" "${OUT_DIR}/log"

# Template: given or generated from the first file.
if [ -z "${TEMPLATE:-}" ]; then
    TEMPLATE=${SCENE_DIR}/template.xml
    PYLIBS=${CYCLESPHI_LIBS}
    LD_LIBRARY_PATH=${PYLIBS}/openvdb/lib:${PYLIBS}/tbb/lib:${LD_LIBRARY_PATH} \
    PYTHONPATH=${PYLIBS}/python/lib/python3.13/site-packages \
        ${PYLIBS}/python/bin/python3.13 -I "${HERE}/make_vdb_scene.py" \
            --vdb "${FILES[0]}" --grid "${GRID}" --out "${TEMPLATE}" ${SCENE_ARGS:-}
fi
[ -f "${TEMPLATE}.bin" ] || { echo "Missing ${TEMPLATE}.bin"; exit 1; }

for f in "${FILES[@]}"; do
    base=$(basename "${f%.vdb}")
    png=${OUT_DIR}/${base}.png
    if [ -f "${png}" ] && [ "${FORCE:-0}" != "1" ]; then
        echo "skip ${png}"; continue
    fi
    xml=${SCENE_DIR}/${base}.xml
    sed -e "s|{GRID_NAME}|${GRID}|g" -e "s|{VDB_DATA}|${f}|g" "${TEMPLATE}" > "${xml}"
    ln -sf "$(readlink -f "${TEMPLATE}.bin")" "${xml}.bin"
    echo "Rendering ${f} -> ${png}"
    t0=$(date +%s)
    "${CYCLES_BIN}" --device CPU --threads "${THREADS}" --samples "${SAMPLES}" \
        --width "${WIDTH}" --height "${HEIGHT}" ${EXTRA_ARGS:-} \
        --output "${png}" "${xml}" > "${OUT_DIR}/log/${base}.log" 2>&1 \
        || { echo "FAILED: see ${OUT_DIR}/log/${base}.log"; continue; }
    echo "  done in $(( $(date +%s) - t0 )) s"
    grep -E "Wrong number|Unknown socket|not found|Error" "${OUT_DIR}/log/${base}.log" | sort -u | sed 's/^/  XML WARNING: /' || true
done
