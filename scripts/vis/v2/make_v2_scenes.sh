#!/bin/bash
# Production scenes of the v2 animations (pitzDaily3D 62M, VDB_v2, 260 frames 193010..195600).
# Writes <shot>/scene/pitz_<idx>.xml (+ shared .bin) for the expected file names, so the
# follow-mode render can start as soon as each VDB appears. Camera: slow eased orbit
# from a wide 3/4 view (az 100, el 22, 0.30 m) to a close 3/4 view (az 135, el 33, 0.245 m).
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
# v3: VER=v3 FIRST=193050 STEP=50 NF=300 bash make_v2_scenes.sh
VER=${VER:-v2}; FIRST=${FIRST:-193010}; STEP=${STEP:-10}; NF=${NF:-260}
R=$S/renders/pitzDaily3D/$VER; V=$S/runs/pitzDaily3D/62M/VDB_$VER
FILES=$(for i in $(seq $FIRST $STEP $((FIRST + STEP * (NF - 1)))); do echo $V/pitz_$i.vdb; done)
CAM="--frame-from-name --first $FIRST --step $STEP --nframes $NF --exposure 2.83
     --az0 100 --az1 135 --el0 22 --el1 33 --dist0 0.30 --dist1 0.245
     --target0 0.145 -0.004 0 --target1 0.15 -0.004 0"
# flame: blackbody flame front w = (4 b (1-b))^25, Tv = 1000..3000 K from w, products glow (look BB1)
FL="--flame-model blackbody --bb-power 25 --bb-tlo 1000 --bb-thi 3000 --flame-emission 40 --flame-density 1.0 --glow-emission 0.15"
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py $CAM --sun-dir -0.3 -1 -0.5"
$G --look flame    --outdir $R/flame/scene    $FL --vdb $FILES
# vortex: Q tubes coloured by |U|, key + rim sun (look R2)
$G --look vortex   --outdir $R/vortex/scene   --vortex-density 400 --vortex-emission 5 --sun-strength 5 --rim-strength 25 --vdb $FILES
# combined: BB1 flame + semi-transparent vortices (look CC3)
$G --look combined --outdir $R/combined/scene $FL --vortex-density 200 --vortex-emission 25 --sun-strength 3 --rim-strength 15 --vdb $FILES
