# CyclesPhi scene: MB12 model wind farm (wakes and vortices)

Scene for the OpenFOAM HPC TC case `incompressible/pimpleFoam/LES/modelwindfarm/windfarmmodel`
(30 rotorDisk actuator-disc turbines, D = 0.15 m, hub 0.125 m, 10 rows x 3 columns, wind along +x).
The data come from mesioVDB: one `.vdb` per frame with the float grids `U_mag`, `Q` and
`vorticity_mag` on a 0.005 m voxel grid (box x 2.70..10.79, y 0.005..1.795, z 0..0.45 m,
1619 x 359 x 91 = 52.4M voxels). Setup, commands and timings: `docs/notes/animations_modelwindfarm.md`.

## Files

| File | Purpose |
|---|---|
| `make_windfarm_scene.py` | Scene generator (plain python3, no modules). Per-frame XMLs + one shared `common.bin`, or one template with `{VDB_DATA}`. |
| `looks.sh` | Final argument sets `LOOK_wake`, `LOOK_vortex`, `LOOK_combined` (environment, camera path, transfer functions). |
| `windfarm_{wake,vortex,combined}.xml` + `.xml.bin` | Reference scenes (frame 0 camera, `{VDB_DATA}` placeholder) generated from `looks.sh`. |
| `render_scenes.sh` | Renders scene XMLs on one node (CPU, OIDN, OCIO config by `OCIO_CFG`, default view here: `standard`). |
| `render_series.sh` | Frame-parallel worker with an atomic-mkdir claim queue (any number of nodes, any jobs, resumable; `FOLLOW=1` follows a running export). |
| `finish_movies.sh` | MP4s (H.264, 30 fps, CRF 18, yuv420p) + 4-frame contact sheet. |
| `variants.sh`, `contact.sh` | Look development: render argument variants of one VDB and tile them to a contact sheet. |

Use a template: `sed "s|{VDB_DATA}|/abs/path/wf_003000.vdb|" windfarm_combined.xml > f.xml; ln -s windfarm_combined.xml.bin f.xml.bin`.
Scene units are metres (the VDB world space); the VDB object transform is the identity.

## Geometry (all looks)

* 30 turbines built from simple meshes (CyclesPhi XML `<mesh geometry_type="0">`: `triangles`,
  `shader`, `smooth` arrays + `<attribute name="P" std="ATTR_STD_POSITION">`, positions as
  packed float3 = 12 bytes per vertex in the `.bin`):
  tower (tapered cylinder), nacelle, spinner, and a 3-blade rotor whose sections follow the
  rotorDisk blade table of `constant/fvOptions` (chord 6-15 mm, twist -22..-6.7 deg).
  Towers, nacelles and spinners are one merged mesh; the rotor is one mesh instanced by 30
  objects whose transforms rotate it about the x axis (11 deg per frame plus a per-turbine
  phase). The real 1070 rpm would be 64 deg (0.01 s frames) or 193 deg (0.03 s frames) per frame and strobe, so the rotation is visual only.
* Ground = calm sea: a 400 m x 400 m plane at z = -0.5 mm, principled BSDF, base colour
  (0.01, 0.03, 0.06) (checker texture node with equal colours), roughness 0.3.
* World: sky gradient (texture coordinate `generated` z -> smoothstep -0.02..0.3 -> mix
  horizon (0.62, 0.74, 0.92) / zenith (0.12, 0.30, 0.80)); camera rays see it at strength 1,
  other rays at 0.6 (light_path `is_camera_ray` + mix_closure).
* Sun: `<sunlight>` strength 5, angle 3 deg, warm (1.0, 0.90, 0.76), direction (-0.6, 0.3, 0.75),
  i.e. from upstream-left, giving long turbine/wake shadows and a soft glint on the sea.
* Camera: slow ease-in/out dolly over the 300 frames from (8.2, -1.1, 1.05) -> look at
  (6.0, 0.9, 0) to (6.4, -0.85, 0.78) -> (4.7, 0.9, 0.03): from the downstream side, moving
  upstream along the farm; vertical FOV 34 deg.
* Integrator: null-scattering volumes (`volume_ray_marching false`, 10x faster than ray marching
  for these dense 52M-voxel grids at equal look), `max_volume_bounce 0` (direct sun + sky only),
  OIDN denoiser (accurate prefilter, high quality), film exposure 1.2. Display transform: OCIO
  `config_standard.ocio` (saturated colours; the AgX/filmic views looked grey for this scene).

## Shader graph `wf_volume` (one volume object, all grids from the same .vdb)

```
geometry.position -> separate_xyz (x, y, z)
box mask M = prod of map_range smoothstep ramps on x, y, z:
    x: 2.70 -> 2.712 and 10.79 -> 10.754        (inflow/outlet faces)
    y: 0.005 -> 0.075 and 1.795 -> 1.725         (side-wall boundary layers, no-slip walls)
    z: 0 -> 0.022 and 0.45 -> 0.40               (floor wall-function layer, box top)
  (inactive voxels outside the box are 0, which would map to a full velocity deficit)

velocity deficit (WAKE):
    U_ref(z) = 0.3053 * ln(max(z, 0.004)) + 3.179      math: maximum, logarithm(base e), multiply_add
             (log-law fit of the inlet profile constant/boundaryData/inlet/0/UMean, u*/kappa = 0.305)
    d = 1 - U_mag / U_ref                              math: divide, subtract
    t = map_range(d, 0.05 .. 0.55, clamp)
    albedo  = rgb_ramp "ice"  (white 0.97,0.98,1 -> pale blue -> 0.10,0.25,0.80 at t = 1)
    emission colour = rgb_ramp "deep" (0.55,0.80,1 -> 0.05,0.15,0.80)
    alpha   = rgb_ramp alpha "crisp" (cosine-smoothed 0 / 0.02 / 0.2 / 0.7 / 1 at t = 0 / .2 / .45 / .7 / 1)
    principled_volume: color = albedo, density = alpha*M*20 [1/m], anisotropy 0.5 (forward scatter),
                       emission_color = deep ramp, emission_strength = alpha*M*3
    -> undisturbed boundary layer is transparent, the wakes are bright blue-white "clouds" with
       saturated blue cores where the deficit is largest (behind the rotors, merging downstream).

vortex tubes (VORTEX):
    tq = map_range(Q, 100 .. 700 1/s^2)    alpha ramp: 0 / 0.08 / 0.55 / 1 at t = 0 / .15 / .5 / 1
    tw = map_range(vorticity_mag, 30 .. 150 1/s) -> rgb_ramp amber (0.95,0.30,0.05) -> gold -> white-hot
    floor fade: smoothstep(z, 0.03 .. 0.06)      (removes the floor boundary-layer eddies)
    wake gate:  smoothstep(d, 0.03 .. 0.10)      (keeps the vortices in and at the edge of the wakes,
                                                  removes inflow (synthetic DFM) eddies between the rows)
    principled_volume: color (0.95, 0.6, 0.25), density = alpha*mask*40,
                       emission_color = amber ramp, emission_strength = alpha*mask*20 (vortex) / 12 (combined)

combined: add_closure(wake volume, vortex volume) -> output.volume
```

Value ranges were chosen from the grid statistics of frame 2010 (U_mag 1-99 % 1.15-3.28 m/s; Q 99 % 211,
99.9 % 483, max 2.6e3 1/s^2; vorticity 99 % 145 1/s, mostly floor shear).

## Look development (renders under `$S/renders/modelwindfarm/tests/v1..v13`, contact sheets `contact*.png`)

v1-v2 camera/ranges, v3 sea vs grey floor, v4 Q vs vorticity opacity (vorticity shows the side-wall
sheets, rejected), v5-v6 OCIO views and Q gating, v7 vortex "tube" style, v8 bright cloud albedo,
v9-v10 1080p timing (ray marching 180-250 s/frame vs null scattering 10-22 s/frame, same look),
v11 sun direction (glint position), v12-v13 final colours (`ice` albedo + `deep` emission).
`renders/modelwindfarm/preview_combined/preview.mp4` = 30-frame 640x360 temporal check.
