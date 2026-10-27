#!/bin/bash
# Assemble a PNG frame series into an H.264 MP4 (FFmpeg module, run on a compute node).
# Usage: make_mp4.sh <png_dir> <out.mp4> [fps=24] [pattern='*.png']
# Example: srun --jobid=5270670 --overlap -N1 -n1 -c 16 -w cn358 \
#            bash scripts/vis/make_mp4.sh renders/pitz/T renders/pitz/T.mp4 24
set -euo pipefail
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
source /etc/profile.d/z00_lmod.sh 2>/dev/null || true
module load FFmpeg/7.1.2-GCCcore-14.3.0 >/dev/null 2>&1
DIR=$1; OUT=$2; FPS=${3:-24}; PAT=${4:-*.png}
ffmpeg -y -loglevel error -framerate "$FPS" -pattern_type glob -i "$DIR/$PAT" \
    -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
    -movflags +faststart "$OUT"
n=$(ls -1 $DIR/$PAT | wc -l)
echo "wrote $OUT ($n frames, $FPS fps, $(du -h "$OUT" | cut -f1))"
