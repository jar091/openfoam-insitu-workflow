#!/bin/bash
# Render CyclesPhi scene XMLs (from make_pitz_scene.py) to PNGs on the current compute node.
# Usage: render_xml.sh <ocio: standard|agx|agx_punchy|filmic_mhc|pbrneutral> <WxH> <spp> <out_dir> <scene.xml...>
# Existing outputs are skipped unless FORCE=1. OUTEXT=exr writes EXR (use ocio "raw" for linear data). Per-frame log in <out_dir>/log/.
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_cyclesphi.sh >/dev/null 2>&1
CM=${OF_WS}/data/cyclesphi/colormanagement
case $1 in
    standard) export OCIO=$CM/config_standard.ocio ;;
    agx) export OCIO=$CM/config.ocio ;;
    *) export OCIO=$CM/config_$1.ocio ;;
esac
RES=$2; SPP=$3; OUT=$4; shift 4
mkdir -p $OUT/log
for x in "$@"; do
    b=$(basename ${x%.xml}); E=${OUTEXT:-png}; png=$OUT/$b.$E
    [ -f $png ] && [ "${FORCE:-0}" != 1 ] && continue
    t0=$(date +%s.%N)
    $CYCLES_BIN --device CPU --threads ${THREADS:-$(nproc)} --samples $SPP --width ${RES%x*} --height ${RES#*x} \
        --output $png.tmp.$E $x > $OUT/log/$b.log 2>&1 && mv $png.tmp.$E $png
    echo "$b $(hostname -s) $(echo "$(date +%s.%N) - $t0" | bc) s" | tee -a $OUT/log/times.txt
    grep -E "Wrong number|Unknown socket|not found|rror" $OUT/log/$b.log | grep -v verts | sort -u | head -5
done
