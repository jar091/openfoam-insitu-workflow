#!/bin/bash
# Tile PNGs (same size) into a contact sheet, row-major. Usage: contact.sh <out.png> <cols> <png...>
source ${ENVDUMP:-/scratch/project/eu-25-121/milanjaros/openfoam/renders/modelwindfarm/env_cyclesphi_ffmpeg.sh}
OUT=$1; COLS=$2; shift 2; n=$#
ins_list=""; st=""; lay=""
i=0; for f in "$@"; do ins_list+=" -i $f"; st="$st[$i:v]"; c=$((i%COLS)); r=$((i/COLS))
    xs=0; [ $c -gt 0 ] && xs=$(printf 'w0+%.0s' $(seq $c) | sed 's/+$//')
    ys=0; [ $r -gt 0 ] && ys=$(printf 'h0+%.0s' $(seq $r) | sed 's/+$//')
    lay="$lay|${xs}_${ys}"; i=$((i+1)); done
ffmpeg -y -loglevel error $ins_list -filter_complex "${st}xstack=inputs=$n:layout=${lay#|}:fill=black" "$OUT" && echo "wrote $OUT"
