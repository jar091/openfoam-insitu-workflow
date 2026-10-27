#!/bin/bash
# Assemble the v3 MP4s (H.264, 30 fps, CRF 18, yuv420p) and contact sheets. Run on a compute node.
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; R=/scratch/project/eu-25-121/milanjaros/openfoam/renders/pitzDaily3D/v3
for s in flame vortex combined; do
    bash $P/scripts/vis/make_mp4.sh $R/$s $R/pitz_v3_$s.mp4 30 'pitz_*.png'
done
SCALE=960:540 bash $P/scripts/vis/v2/tile.sh $R/pitz_v3_contact_combined.png 2 $(for k in 193050 198000 203000 208000; do echo $R/combined/pitz_$k.png; done)
SCALE=640:360 bash $P/scripts/vis/v2/tile.sh $R/pitz_v3_contact_shots.png 3 \
    $(for k in 193050 200500 208000; do for s in flame vortex combined; do echo $R/$s/pitz_$k.png; done; done)
