# Production arguments of make_dlrcjh_scene.py for the DLRCJH animations (bash, sourced;
# the strings contain quoted ramp specs, so expand them with eval).
# COMMON: VDB box (scene normalisation), cut-away walls, slow eased orbit over the 225 frames
# (time index 8..1800, step 8): side 3/4 view -> higher 3/4 view from downstream.
DLR_COMMON="--box -0.005 -0.0475 -0.0475 0.505 0.0475 0.0475 --walls-xmax 0.505 \
 --az0 18 --az1 42 --el0 12 --el1 24 --dist0 0.52 --dist1 0.56 \
 --target0 0.235 -0.005 0 --target1 0.24 -0.008 0"
DLR_FLAME="--look flame --flame-emission 100 --glow 0.01 \
 --front-alpha '0:0;0.12:0;0.3:0.35;0.5:1;0.7:0.35;0.88:0;1:0'"
DLR_VORTEX="--look vortex --wall-color 0.03 0.035 0.045 --exposure 2.0 \
 --qrange 1.5e8 3e9 --qgamma 0.7 --vortex-density 40 --vortex-emission 70 --vortex-absorption 0 0 0 \
 --vortex-alpha '0:0;0.08:0;0.25:0.3;0.6:0.9;1:1' --urange 10 140 \
 --vortex-colors '0:0.25,0.02,0.6;0.3:0.05,0.1,0.9;0.55:0.0,0.5,1.0;0.8:0.1,0.9,0.9;1:0.8,1.0,0.95'"
DLR_COMBINED="--look combined --wall-color 0.05 0.045 0.04 --flame-emission 70 --glow 0.0 \
 --front-alpha '0:0;0.12:0;0.3:0.35;0.5:1;0.7:0.35;0.88:0;1:0' \
 --qrange 1.5e8 3e9 --qgamma 0.7 --vortex-density 20 --vortex-emission 130 --vortex-absorption 0 0 0 \
 --vortex-alpha '0:0;0.08:0;0.25:0.3;0.6:0.9;1:1' --urange 10 140 \
 --vortex-colors '0:0.25,0.02,0.6;0.3:0.05,0.1,0.9;0.55:0.0,0.5,1.0;0.8:0.1,0.9,0.9;1:0.8,1.0,0.95'"
# render cost: ray-march step 2 voxels (0.8 mm), 1 bounce (walls still see the flame), OIDN
DLR_RENDER="--step-rate 2 --max-bounce 1"
