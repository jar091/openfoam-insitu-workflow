#!/bin/bash
# Look-development variants (contact sheet) for the occDrivAer scene.
# Usage: variants.sh <vdb> <out_dir> [tag]   -> <out_dir>/xml/V*_<view>.xml
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
G="python3 -I $P/data/cyclesphi/scenes/occDrivAer/make_drivaer_scene.py"
VDB=$1; OUT=$2
REAR="--az 35 35 --el 20 20 --dist 11 11 --target0 3.2 0 0.2"
FRONT="--az 205 205 --el 14 14 --dist 8.5 8.5 --target0 1.8 0 0.25"
declare -A V
V[V1]="--look combined --paint graphite --wake-colors wake_ice --vortex-colors vort_ember"
V[V2]="--look combined --paint silver --wake-colors wake_teal --vortex-colors vort_ice"
V[V3]="--look combined --paint midnight --wake-colors wake_white --vortex-colors vort_plasma"
V[V4]="--look vortex --paint graphite --vortex-colors vort_turbo --vortex-emission 15"
V[V5]="--look wake --paint white --wake-colors wake_ice --wake-density 10"
V[V6]="--look combined --paint clay --wake-colors wake_ice --vortex-colors vort_turbo"
V[V7]="--look combined --paint red --wake-colors wake_white --vortex-colors vort_ice"
V[V8]="--look combined --paint graphite --wake-colors wake_ice --vortex-colors vort_ember --loss 0.3 1.2 --wake-gamma 2 --qrange 1e4 3e5"
for k in V1 V2 V3 V4 V5 V6 V7 V8; do
    $G --outdir $OUT/xml --vdb $VDB --name ${k}_rear ${V[$k]} $REAR $EXTRA > /dev/null
    $G --outdir $OUT/xml --vdb $VDB --name ${k}_front ${V[$k]} $FRONT $EXTRA > /dev/null
done
ls $OUT/xml/*.xml | wc -l
