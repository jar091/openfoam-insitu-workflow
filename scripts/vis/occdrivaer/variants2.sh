#!/bin/bash
# Look-development round 2 (after round 1: near-wall Q mask, softer wake, rim/fill not in glossy).
# Usage: variants2.sh <vdb> <out_dir>
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
G="python3 -I $P/data/cyclesphi/scenes/occDrivAer/make_drivaer_scene.py"
VDB=$1; OUT=$2
REAR="--az 35 35 --el 20 20 --dist 11 11 --target0 3.2 0 0.2"
FRONT="--az 205 205 --el 14 14 --dist 8.5 8.5 --target0 1.8 0 0.25"
W="--loss 0.25 1.3 --wake-gamma 1.5 --wake-density 3"
declare -A V
V[W1]="--look combined --paint graphite $W --wake-colors wake_ice --vortex-colors vort_ember"
V[W2]="--look combined --paint graphite $W --wake-colors wake_teal --vortex-colors vort_ice"
V[W3]="--look combined --paint graphite --loss 0.15 1.0 --wake-gamma 2.0 --wake-density 4 --wake-emission 0.3 --vortex-colors vort_ember --qrange 2e3 6e4"
V[W4]="--look combined --paint white $W --wake-colors wake_ice --vortex-colors vort_plasma"
V[W5]="--look vortex --paint graphite --vortex-umask 15 25 --vortex-colors vort_ember --vortex-emission 12"
V[W6]="--look combined --paint midnight --loss 0.3 1.3 --wake-density 2 --wake-colors wake_white --vortex-colors vort_ember"
for k in W1 W2 W3 W4 W5 W6; do
    $G --outdir $OUT/xml --vdb $VDB --name ${k}_rear ${V[$k]} $REAR $EXTRA > /dev/null
    $G --outdir $OUT/xml --vdb $VDB --name ${k}_front ${V[$k]} $FRONT $EXTRA > /dev/null
done
ls $OUT/xml/*.xml | wc -l
