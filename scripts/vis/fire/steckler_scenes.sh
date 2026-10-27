#!/bin/bash
# Final look of the Steckler room-fire animation: writes one CyclesPhi XML per VDB frame.
# Usage: steckler_scenes.sh <scene_out_dir> <vdb files...>
# (camera: eased orbit az 22 -> 38 deg over the 250 frames, frame index from the file name)
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
OUT=$1; shift
python3 $P/data/cyclesphi/scenes/stecklerWithSpray/make_steckler_scene.py --outdir $OUT --vdb "$@" \
    --nframes ${NFRAMES:-250} ${FRAMEARGS:---frame-from-name} \
    --target0 1.45 2.2 0 --az0 22 --az1 38 --el0 7 --el1 9 --dist0 9.4 --dist1 9.0 --fov 33 \
    --smoke-range 3e-4 0.004 --smoke-gamma 0.9 --smoke-density 25 \
    --smoke-colors '0:0.10,0.10,0.11;0.5:0.11,0.10,0.09;1:0.14,0.10,0.07' \
    --flame-range 450 1400 --bb-range 1000 2300 --flame-emission 80 \
    --glow-range 400 700 --glow-emission 1.0 \
    --fill-pos 10 6 0.5 --fill-target 1.5 2 0 --fill-strength 1100 --fill-size 4 \
    --volume-bounces 1 --step-size 0.02 ${EXTRA:-}
