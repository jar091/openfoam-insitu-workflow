#!/bin/bash
# Render look/camera variants of one VDB for the DLRCJH scene (run on a compute node).
# Usage: variants.sh <variants_file> <vdb> <out_dir> [WxH=960x540] [spp=32]
#   variants_file: one variant per line "<name> <make_dlrcjh_scene.py args...>"
#   (lines starting with # ignored). Scenes in <out_dir>/<name>/, images <out_dir>/<name>.png.
#   COMMON="..." args added to every variant; OCIO_CFG=standard|agx|... (default standard).
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
VF=$1; VDB=$2; OUT=$3; RES=${4:-960x540}; SPP=${5:-32}
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
ulimit -c 0
source $P/scripts/env_cyclesphi.sh >/dev/null 2>&1
CM=$P/data/cyclesphi/colormanagement
case ${OCIO_CFG:-standard} in standard) export OCIO=$CM/config_standard.ocio ;; agx) export OCIO=$CM/config.ocio ;; *) export OCIO=$CM/config_${OCIO_CFG}.ocio ;; esac
mkdir -p $OUT
while read -r name args; do
    [ -z "$name" ] || [ "${name:0:1}" = "#" ] && continue
    [ -f $OUT/$name.png ] && [ "${FORCE:-0}" != 1 ] && continue
    eval bash $P/scripts/vis/pyvdb.sh $P/data/cyclesphi/scenes/DLRCJH/make_dlrcjh_scene.py --vdb $VDB --outdir $OUT/$name ${COMMON:-} $args > /dev/null || { echo "$name: generator failed"; continue; }
    x=$(ls $OUT/$name/*.xml | head -1)
    t0=$(date +%s.%N)
    $CYCLES_BIN --device CPU --threads $(nproc) --samples $SPP --width ${RES%x*} --height ${RES#*x} \
        --output $OUT/$name.png $x > $OUT/$name/render.log 2>&1
    rc=$?
    echo "$name rc=$rc $(echo "$(date +%s.%N) - $t0" | bc | cut -c1-6) s"
    tr '\r' '\n' < $OUT/$name/render.log | grep -E "Wrong number|Unknown|not found|rror|not read" | sort -u | head -5
done < $VF
