#!/bin/bash
# Final look of the DLR jet-in-hot-coflow animation: writes one CyclesPhi XML per VDB frame.
# Usage: jhc_scenes.sh <scene_out_dir> <vdb files...>
# (camera: eased orbit around the jet axis phi -70 -> -20 deg with a dolly-out that follows
#  the growing flame, frame index from the file name, 250 frames)
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
OUT=$1; shift
python3 $P/data/cyclesphi/scenes/DLRJHC/make_jhc_scene.py --outdir $OUT --vdb "$@" \
    --nframes ${NFRAMES:-250} ${FRAMEARGS:---frame-from-name} \
    --quadrants 4 --mirror-shift 0.0002 --step-size 0.0004 --plate-r 0 \
    --tz0 0.035 --tz1 0.058 --dist0 0.125 --dist1 0.168 --phi0 -70 --phi1 -20 --el0 25 --el1 18 --roll -10 --fov 22 \
    --flame-range 1520 1850 --bb-range 1500 2500 --flame-emission 400 --flame-gamma 2.0 --flame-density 0.3 \
    --oh-range 0.0010 0.0035 --oh-emission 1000 --oh-edge 1.0 --oh-colors '0:0.10,0.05,1.0;0.6:0.18,0.12,1.0;1:0.35,0.30,1.0' \
    --fuel-range 0.02 0.9 --fuel-emission 3 --fuel-glow-color 0.1 0.4 1.0 --fuel-density 0 \
    ${EXTRA:-}
