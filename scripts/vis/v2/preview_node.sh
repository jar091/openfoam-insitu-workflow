#!/bin/bash
# Low-res flicker preview: render items k, k+N, ... of (frame, shot) for the first NF frames.
# Usage: preview_node.sh <k> <N> <NF> <WxH> <spp>
R=/scratch/project/eu-25-121/milanjaros/openfoam/renders/pitzDaily3D/v2
K=$1; N=$2; NF=$3; RES=$4; SPP=$5; j=0
for i in $(seq 193010 10 $((193010 + 10 * (NF - 1)))); do for s in flame vortex combined; do
    [ $((j % N)) = $K ] && THREADS=128 bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/vis/v2/render_xml.sh filmic_mhc $RES $SPP $R/tests/preview_$s $R/$s/scene/pitz_$i.xml > /dev/null
    j=$((j + 1))
done; done
