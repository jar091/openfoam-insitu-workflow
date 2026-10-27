#!/bin/bash
# Render CyclesPhi scene XMLs (from make_windfarm_scene.py) on the current compute node.
# Usage: render_scenes.sh <WxH> <spp> <out_dir> <scene.xml...>
#   OCIO_CFG=standard|agx|agx_punchy|filmic_mhc|pbrneutral (default filmic_mhc), THREADS, FORCE=1.
# Existing PNGs are skipped; per-frame logs in <out_dir>/log/, timings in <out_dir>/log/times.txt.
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
# Plain export dump of scripts/env_cyclesphi.sh + FFmpeg module (Lmod takes minutes on loaded nodes):
#   source env_cyclesphi.sh; module load FFmpeg/7.1.2-GCCcore-14.3.0; export -p > $ENVDUMP
ENVDUMP=${ENVDUMP:-/scratch/project/eu-25-121/milanjaros/openfoam/renders/modelwindfarm/env_cyclesphi_ffmpeg.sh}
source $ENVDUMP
CM=${OF_WS}/data/cyclesphi/colormanagement
case ${OCIO_CFG:-filmic_mhc} in
    standard) export OCIO=$CM/config_standard.ocio ;;
    agx) export OCIO=$CM/config.ocio ;;
    *) export OCIO=$CM/config_${OCIO_CFG:-filmic_mhc}.ocio ;;
esac
RES=$1; SPP=$2; OUT=$3; shift 3
mkdir -p $OUT/log
for x in "$@"; do
    b=$(basename ${x%.xml}); png=$OUT/$b.png
    [ -f $png ] && [ "${FORCE:-0}" != 1 ] && continue
    t0=$(date +%s.%N)
    $CYCLES_BIN --device CPU --threads ${THREADS:-$(nproc)} --samples $SPP --width ${RES%x*} --height ${RES#*x} \
        --output $png.tmp.png $x > $OUT/log/$b.log 2>&1 && mv $png.tmp.png $png
    echo "$b $(hostname -s) $(echo "$(date +%s.%N) - $t0" | bc) s" | tee -a $OUT/log/times.txt
    grep -E "Wrong number|Unknown|not found|rror|Too many" $OUT/log/$b.log | grep -v verts | sort -u | head -8
done
