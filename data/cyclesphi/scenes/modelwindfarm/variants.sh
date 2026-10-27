#!/bin/bash
# Look-development helper: build scene variants for one VDB and render them at low resolution
# on one compute node, then tile them into a labelled contact sheet.
# Tiles are in argument order, row-major, 3 per row (ffmpeg has no drawtext here).
# Usage (inside srun on a compute node): variants.sh <vdb> <out_dir> <WxH> <spp> "<label>|<args>" ...
D=/mnt/proj2/eu-25-121/milanjaros/openfoam/data/cyclesphi/scenes/modelwindfarm
VDB=$1; OUT=$2; RES=$3; SPP=$4; shift 4
mkdir -p $OUT
labels=()
for v in "$@"; do
    lab=${v%%|*}; args=${v#*|}
    python3 $D/make_windfarm_scene.py --outdir $OUT/scene_$lab --vdb $VDB --nframes 1 $args > /dev/null || exit 1
    x=$OUT/scene_$lab/$(basename ${VDB%.vdb}).xml
    FORCE=1 bash $D/render_scenes.sh $RES $SPP $OUT/r_$lab $x
    cp $OUT/r_$lab/$(basename ${VDB%.vdb}).png $OUT/$lab.png
    labels+=($lab)
done
source ${ENVDUMP:-/scratch/project/eu-25-121/milanjaros/openfoam/renders/modelwindfarm/env_cyclesphi_ffmpeg.sh}
n=${#labels[@]}; cols=$(( n < 3 ? n : 3 ))
ins=""; fil=""; i=0
for l in "${labels[@]}"; do
    ins="$ins -i $OUT/$l.png"
    fil="$fil[$i:v]null[v$i];"
    i=$((i+1))
done
lay=""; for ((k=0;k<n;k++)); do c=$((k%cols)); r=$((k/cols)); lay="$lay|$( [ $c = 0 ] && echo 0 || echo "$(for ((q=0;q<c;q++)); do printf 'w0+'; done | sed 's/+$//')" )_$( [ $r = 0 ] && echo 0 || echo "$(for ((q=0;q<r;q++)); do printf 'h0+'; done | sed 's/+$//')" )"; done
st=""; for ((k=0;k<n;k++)); do st="$st[v$k]"; done
ffmpeg -y -loglevel error $ins -filter_complex "$fil${st}xstack=inputs=$n:layout=${lay#|}:fill=black" $OUT/contact.png && echo "contact sheet $OUT/contact.png"
