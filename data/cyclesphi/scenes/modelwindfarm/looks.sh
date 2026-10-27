# Final look settings for make_windfarm_scene.py (sourced by render_series.sh).
# Environment: calm dark sea (glossy ground), blue sky gradient, warm sun from upstream-left
# with a soft glint, null-scattering volumes (no ray marching: ~10x faster here, same look).
ENV="--ground-c1 0.01 0.03 0.06 --ground-c2 0.01 0.03 0.06 --ground-roughness 0.3 \
 --sky-horizon 0.62 0.74 0.92 --sky-zenith 0.12 0.30 0.80 --sky-height 0.3 \
 --sun-dir -0.6 0.3 0.75 --sun-strength 5 --ambient 0.6 --exposure 1.2 \
 --ray-marching 0 --volume-bounces 0"
# camera: slow dolly upstream along the farm, from the downstream side (300 frames)
CAM="--cam-pos0 8.2 -1.1 1.05 --cam-tgt0 6.0 0.9 0.0 --cam-pos1 6.4 -0.85 0.78 --cam-tgt1 4.7 0.9 0.03"
WAKE="--wake-ramp ice --wake-emit-ramp deep --wake-alpha crisp --wake-density 20 --wake-anisotropy 0.5 --wake-emission 3"
VORT="--q-range 100 700 --w-range 30 150 --q-gate 0.03 0.1 --q-density 40 --q-emission 12 --q-albedo 0.95 0.6 0.25"
LOOK_wake="--look wake $ENV $CAM $WAKE"
LOOK_vortex="--look vortex $ENV $CAM $VORT --q-emission 20"
LOOK_combined="--look combined $ENV $CAM $WAKE $VORT"
