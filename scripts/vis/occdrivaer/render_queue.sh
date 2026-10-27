#!/bin/bash
# Frame-parallel CyclesPhi rendering with a shared work queue (one worker per node).
# Every worker walks the XML list in order and renders an item when the atomic claim
# directory <out>/claims/<name> can be created and the PNG does not exist yet; resumable.
# Usage (one srun step per node, same arguments):
#   render_queue.sh <ocio: standard|agx|agx_punchy|filmic_mhc|pbrneutral> <WxH> <spp> <out_dir> <scene.xml...>
# Env: THREADS (default nproc), FORCE=1 re-renders, OUTEXT=png|exr.
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_cyclesphi.sh >/dev/null 2>&1
CM=${OF_WS}/data/cyclesphi/colormanagement
case $1 in
    standard) export OCIO=$CM/config_standard.ocio ;;
    agx) export OCIO=$CM/config.ocio ;;
    *) export OCIO=$CM/config_$1.ocio ;;
esac
RES=$2; SPP=$3; OUT=$4; shift 4
E=${OUTEXT:-png}
mkdir -p $OUT/log $OUT/claims
for x in "$@"; do
    b=$(basename ${x%.xml}); png=$OUT/$b.$E
    [ -f $png ] && [ "${FORCE:-0}" != 1 ] && continue
    mkdir $OUT/claims/$b 2>/dev/null || continue
    t0=$(date +%s.%N)
    $CYCLES_BIN --device CPU --threads ${THREADS:-$(nproc)} --samples $SPP --width ${RES%x*} --height ${RES#*x} \
        --output $png.tmp.$E $x > $OUT/log/$b.log 2>&1 && mv $png.tmp.$E $png
    echo "$b $(hostname -s) $(echo "$(date +%s.%N) - $t0" | bc) s" >> $OUT/log/times.txt
    grep -E "Wrong number|Unknown socket|Unknown node|not found|rror" $OUT/log/$b.log | grep -v verts | sort -u | head -5
done
