#!/bin/bash
# Assemble the v2 MP4s (H.264, 30 fps, CRF 18, yuv420p) and a contact sheet of 4 key frames.
# Run on a compute node.
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; R=/scratch/project/eu-25-121/milanjaros/openfoam/renders/pitzDaily3D/v2
for s in flame vortex combined; do
    bash $P/scripts/vis/make_mp4.sh $R/$s $R/pitz_v2_$s.mp4 30 'pitz_*.png'
done
K="193010 193870 194740 195600"
SCALE=960:540 bash $P/scripts/vis/v2/tile.sh $R/pitz_v2_contact_combined.png 2 $(for k in $K; do echo $R/combined/pitz_$k.png; done)
SCALE=640:360 bash $P/scripts/vis/v2/tile.sh $R/pitz_v2_contact_shots.png 3 \
    $(for k in 193010 194300 195600; do for s in flame vortex combined; do echo $R/$s/pitz_$k.png; done; done)
