# occDrivAer (65M, simpleFoam RANS): CyclesPhi studio scene and shaders

Scene for the OpenFOAM HPC case `incompressible/simpleFoam/occDrivAerStaticMesh` (open-closed
cooling DrivAer notchback, 140 km/h, static wheels), rendered from mesioVDB exports (one `.vdb`
per export with the grids `U_mag`, `Cpt`, `Q`, `vorticity_mag`). Run setup, commands and timings:
`docs/notes/animations_occDrivAer.md`.

## Files

| File | Content |
|---|---|
| `make_car_mesh.py` | OBJ (from `surfaceMeshExtract`, one group per wall patch) -> `car_mesh.xml` + `.xml.bin` (11.6M triangles, 7 material slots). The include lives on scratch (`runs/occDrivAer/geometry/`, 267 MB) |
| `make_drivaer_scene.py` | Scene generator: shaders, studio (ground, lights, world), camera path; per-frame XMLs (`--orbit N`), one XML per VDB (`--vdb ...`) or a template (`--template`) |
| `shots.sh` | Exact generator arguments of the production shots (look, orbit, converging sequence) |
| `orbit_start.xml` + `.xml.bin` | Template of the final look, camera at the start of the orbit; placeholders `{VDB_DATA}` (hi-res VDB) and `{WALLD}` (wall-distance VDB) |
| `converge_rear34.xml` + `.xml.bin` | Template of the converging-sequence shot (fixed rear 3/4 camera) |

Helpers in `scripts/vis/occdrivaer/`: `vdb_walldist.py` (wall-distance grid), `vdb_stats_drivaer.py`,
`render_queue.sh` / `render_all_nodes.sh` (frame-parallel rendering with a claim queue),
`variants*.sh` (look-development contact sheets), `q_shell_probe.py`.

Use a template (the car include path inside is absolute, on scratch):
```bash
sed 's|{VDB_DATA}|/scratch/.../VDB_hires/drivaer_001001.vdb|; s|{WALLD}|/scratch/.../geometry/walld_h007.vdb|' \
    orbit_start.xml > s.xml; cp orbit_start.xml.bin s.xml.bin
cycles --device CPU --samples 64 --width 1920 --height 1080 --output s.png s.xml
```

## Coordinates and objects

World = OpenFOAM metres, z up, x = flow direction; origin at the front axle centre, floor at
z = -0.3176 m; car x -0.81..3.80, y +-1.015, z -0.317..1.10. All object transforms are identity.

* `vdb_volume` (geometry_type 2): grids `Cpt`, `Q`, `U_mag` of the export (`volume_type openvdb`)
  plus `walld` from a second file (`buffer` is per attribute). VDB box
  `(-1.3 -1.5 -0.3176) (8.5 1.5 1.7)`: car + about one car length of wake.
* `car` (geometry_type 0, include `car_mesh.xml`, the LAST element of every scene: the xml_bin
  reader switches to the include's `.bin` and closes it afterwards, and opens the include path
  relative to the working directory, so it is absolute). Faces of the 47 wall patches,
  fan-triangulated, winding reversed (OpenFOAM boundary normals point into the car), smooth shading.
  Slots: `car_paint` (Body*, Notchback*, Mirrors*), `car_glass` (*Window*), `car_trim` (*frame,
  ClosedGrill*), `car_tyre`, `car_metal` (Rims*, BrakeDisc*), `car_under` (undershield, underbody,
  powertrain, exhaust, wheel supports, CTRL surfaces), `car_lamp` (headlamps).
* `ground`: 3 x 3 km quad at the floor (the horizon is at infinity, no visible plane edge).
* Camera (`camera_for`): eased orbit, azimuth 200 -> 560 deg (0 = from behind, +x), elevation
  14 -> 20 deg + 4 sin(2 pi e), distance 9.5 m + 2.5 sin^2(az) (side views wider for the wake),
  rear views + 14 deg higher and target moved 1.2 m towards the car (x cos^2 az), target
  (2.6, 0, 0.25), vertical fov 32 deg. 360 frames = 12 s at 30 fps. Converging shot: fixed rear
  3/4 view (az 35, el 22, 10.5 m, target (3, 0, 0.2)).
* Lights: three area lights (emit along -Z of their frame): `key` 12 x 6 m softbox (350 W) above the car
  (warm white, visible in glossy reflections -> softbox highlights on paint and glass, visibility
  254 = everything but camera rays), `rim` 1.5 x 6 m strip behind/right (cool, 400 W), `fill` 4 x 4 m from
  the front-left (80 W) (both visibility 246 = not in glossy, so no light rectangles in the floor).
* World: dim neutral ambient (0.025) for lighting; camera rays see a vertical gradient
  (`texture_coordinate.generated.z -> map_range -> mix_color`), near black at the floor line to
  dark slate at the top.
* Integrator: volume ray marching with step = 5 x voxel size (35 mm for the 7 mm hi-res grid;
  1 x gave no visible difference at 4-6x the cost), max 384 steps, 4 bounces (diffuse 1, glossy 2),
  volume bounces 0 (single scattering), OIDN denoiser (prefilter accurate, quality high), 20 spp, fixed seed.
  Film: Blackman-Harris 1.5 px. PNG through `config_standard.ocio` (Standard sRGB view).

## Shader graphs

Ramps are 257-entry LUTs in the `.xml.bin` (colour 16 B per entry, alpha float), built from
piecewise smoothstep control points (`t:r,g,b;...`).

### Masks (shared by both volume closures)

```
texture_coordinate.object -> separate_xyz -> per axis map_range(face -> face +- 0.25 m) (6 factors,
       floor face 0.03 m)                                 -> box fade: hides the half-voxel band
                                                            towards the background value 0
walld -> map_range(0.05 -> 0.10 m)                        -> wall fade: removes the near-wall shell
mask = product of the 7 factors (math multiply chain)
```
`walld` (from `vdb_walldist.py`) is the distance from the car interior (the inactive voxels of
`U_mag`, 6-neighbour layer count x voxel size, capped at 7-12 voxels). Without it the first voxel
layers outside the walls carry large Q and total-pressure loss (boundary layer), and the car looks
wrapped in an orange staircase shell; a `U_mag` mask did not remove it (U is already 25-40 m/s
in the first voxel), the normalised Q (2Q/|omega|^2) separates it only partly.

### Wake: total pressure loss L = 1 - Cpt (soft translucent volume)

```
Cpt -> math(1 - Cpt) = L -> map_range(0.25 .. 1.3, clamp) -> math power(1.5) = t
t -> rgb_ramp: colour = wake_ice (pale steel blue -> blue -> deep blue core)
               alpha  = 0 below 0.08, 0.25 @ 0.3, 0.7 @ 0.7, 1 @ 1
w = alpha * mask
principled_volume: color (albedo) = ramp colour, density = 3 * w, anisotropy 0.3,
                   emission_color = ramp colour, emission_strength = 0.15 * w
```
Total pressure loss is zero in the inviscid outer flow (unlike the velocity deficit, which also
marks the stagnation region in front of the car), so only the viscous wake, the wheel wakes and the
underbody wake carry density. The power shaping and the alpha floor keep the low-loss outskirts
transparent (no fog); the scattering lets the key light model the wake surface.

### Vortices: Q-criterion filaments coloured by |U|

```
Q     -> map_range(2e3 .. 1e5, clamp) -> math power(0.5) -> rgb_ramp alpha (0 below 0.06,
         0.3 @ 0.25, 0.85 @ 0.6, 1 @ 1) = q
U_mag -> map_range(10 .. 50 m/s)      -> rgb_ramp colour vort_ember (crimson -> orange -> amber ->
         warm white): slow wake vortices red/orange, A-pillar and roof-edge vortices amber/white
U_mag -> map_range(12 .. 20 m/s)      -> low-speed factor (dead-water suppression)
w = q * mask * lowspeed
principled_volume: color = emission_color = ramp colour, density = 40 * w,
                   emission_strength = 8 * w, anisotropy 0.2
```
Mostly self-emissive (the tubes glow and light the paint and the floor through indirect bounces),
the scattering part keeps occlusion/depth between overlapping tubes.

`add_closure(wake, vortex) -> output.volume` on the single volume object.

### Surfaces (principled_bsdf)

| Shader | base colour | metallic | roughness | coat |
|---|---|---|---|---|
| `car_paint` (graphite) | 0.05 0.053 0.058 | 0.7 | 0.30 | 1.0 (roughness 0.03) |
| `car_glass` | 0.004 0.005 0.006 | 0 | 0.12 | 0.6 (roughness 0.08) |
| `car_trim` | 0.012 | 0 | 0.45 | - |
| `car_tyre` | 0.018 | 0 | 0.75 | - |
| `car_metal` | 0.62 0.63 0.65 | 1 | 0.22 | - |
| `car_under` | 0.03 | 0 | 0.6 | - |
| `car_lamp` | 0.85 | 1 | 0.06 | - |
| `ground_mat` (3 x 3 km) | 0.035 -> 0.006 with the distance from the car (6 -> 30 m), roughness 0.28 -> 0.9 | 0 | | |

The radial ground vignette (`texture_coordinate.object -> vector_math distance -> map_range ->
mix_color`) lets the floor dissolve into the background, so there is no hard horizon line.
Other paints (`--paint silver|white|clay|midnight|red`) and ramps (`wake_teal`, `wake_white`,
`vort_ice`, `vort_plasma`, `vort_turbo`) were tested in the contact sheets.
