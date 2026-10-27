#!/bin/bash
# Production shots of the occDrivAer animation (generator arguments in one place).
# Usage (on a compute node):
#   shots.sh orbit   <hires.vdb> <walld_h007.vdb> <out_dir> [nframes=400] [frames=a:b:s]
#   EXTRA="--step-rate 2.5" shots.sh converge <walld_h014.vdb> <out_dir> <vdb...>   (14 mm grid: smaller step)
#   shots.sh template <out_dir>       (writes the workspace templates orbit_start.xml/.bin)
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
G="python3 -I $P/data/cyclesphi/scenes/occDrivAer/make_drivaer_scene.py"
# Look: graphite clear-coat car, total-pressure-loss wake (ice blue, soft scattering),
# Q vortex filaments coloured by |U| (ember ramp), near-wall shell removed via wall distance.
LOOK="--look combined --paint graphite --key 350 \
 --loss 0.25 1.3 --wake-gamma 1.5 --wake-density 3 --wake-emission 0.15 --wake-colors wake_ice \
 --qrange ${QRANGE:-2e3 1e5} --qgamma 0.5 --urange 10 50 --vortex-colors vort_ember \
 --vortex-density 40 --vortex-emission 8 --wall-fade 0.05 0.10 --step-rate 5 --max-steps 384"
# Orbit: 360 deg eased, starting front-left 3/4; slightly higher and wider at the sides.
ORBIT="--az 200 560 --el 14 20 --el-wave 4 --dist 9.5 9.5 --dist-side 2.5 --el-rear 14 --target-rear 1.2 --target0 2.6 0 0.25 --fov 32"
# Converging sequence: fixed rear 3/4 view (wake + vortex system), slightly elevated.
CONV="--az 35 35 --el 22 22 --dist 10.5 10.5 --target0 3.0 0 0.2 --fov 32"
case $1 in
orbit)  $G $LOOK $ORBIT --walld $3 --vdb $2 --outdir $4 --orbit ${5:-400} ${6:+--frames $6} $EXTRA ;;
converge) W=$2; O=$3; shift 3; $G $LOOK $CONV --walld $W --outdir $O --vdb "$@" $EXTRA ;;
template) $G $LOOK $ORBIT --walld "{WALLD}" --outdir $2 --template orbit_start --cam-t 0 $EXTRA
          $G $LOOK $CONV --walld "{WALLD}" --outdir $2 --template converge_rear34 $EXTRA ;;
esac
