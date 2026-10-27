#!/bin/bash
# Assemble the MP4s (H.264, 30 fps, CRF 18, yuv420p) and a 4-frame contact sheet (run on a compute node).
# Usage: [SUFFIX=_dt003] finish_movies.sh [looks...]   (default: combined wake vortex)
#   frames from <R>/<look><SUFFIX>/, outputs <R>/modelwindfarm_<look><SUFFIX>.mp4
source ${ENVDUMP:-/scratch/project/eu-25-121/milanjaros/openfoam/renders/modelwindfarm/env_cyclesphi_ffmpeg.sh}
R=/scratch/project/eu-25-121/milanjaros/openfoam/renders/modelwindfarm
LOOKS=${@:-combined wake vortex}
for l in $LOOKS; do
    ffmpeg -y -loglevel error -framerate 30 -pattern_type glob -i "$R/$l$SUFFIX/wf_??????.png" \
        -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart $R/modelwindfarm_$l$SUFFIX.mp4
    echo "$R/modelwindfarm_$l$SUFFIX.mp4 $(ls $R/$l$SUFFIX/wf_??????.png | wc -l) frames $(du -h $R/modelwindfarm_$l$SUFFIX.mp4 | cut -f1)"
done
# contact sheet: 4 combined frames (CONTACT_FRAMES, time indices), 2x2 at half size
f=(); for i in ${CONTACT_FRAMES:-002005 002500 003000 003500}; do f+=(-i $R/combined$SUFFIX/wf_$i.png); done
ffmpeg -y -loglevel error "${f[@]}" -filter_complex \
  "[0:v]scale=960:540[a];[1:v]scale=960:540[b];[2:v]scale=960:540[c];[3:v]scale=960:540[d];[a][b][c][d]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0" \
  $R/modelwindfarm_contact_sheet$SUFFIX.png && echo "$R/modelwindfarm_contact_sheet$SUFFIX.png"
