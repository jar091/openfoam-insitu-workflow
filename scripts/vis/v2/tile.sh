#!/bin/bash
# Tile equally sized PNGs into a grid (ffmpeg xstack), run on a compute node.
# Usage: tile.sh <out.png> <cols> <img...>   (optional SCALE=w:h per tile)
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
source /etc/profile.d/z00_lmod.sh 2>/dev/null || true
module load FFmpeg/7.1.2-GCCcore-14.3.0 >/dev/null 2>&1
OUT=$1; COLS=$2; shift 2; N=$#
in=(); f=""; lay=""
for i in $(seq 0 $((N-1))); do
    in+=(-i "${@:$((i+1)):1}")
    f+="[$i:v]scale=${SCALE:-960:540}[s$i];"
    c=$((i % COLS)); r=$((i / COLS))
    x=0; for k in $(seq 1 $c); do x="$x+w0"; done
    y=0; for k in $(seq 1 $r); do y="$y+h0"; done
    lay+="${x#0+}_${y#0+}|"
done
st=""; for i in $(seq 0 $((N-1))); do st+="[s$i]"; done
ffmpeg -y -loglevel error "${in[@]}" -filter_complex "${f}${st}xstack=inputs=$N:layout=${lay%|}:fill=white" "$OUT"
echo "wrote $OUT"
