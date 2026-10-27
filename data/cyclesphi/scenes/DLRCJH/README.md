# DLRCJH combustor: CyclesPhi scene and shaders

Scenes for the OpenFOAM HPC TC case `combustion/XiFoam/DLRCJH` (DLR confined-jet
high-pressure combustor, LES premixed flame, 24M mesh), rendered from the mesioVDB exports
(one `.vdb` per frame with the grids `T`, `b`, `Q`, `U_mag`). Setup, run and timings:
`docs/notes/animations_DLRCJH.md`.

## Files

| File | Content |
|---|---|
| `make_dlrcjh_scene.py` | Scene generator: writes one XML per VDB frame (orbit camera from the time index) plus one shared `scene.xml.bin`, or a template (`--template`) |
| `flame.xml` + `.xml.bin` | Template of the final **flame** look (camera at the middle of the orbit, 3M Q range); `{VDB_DATA}` = VDB path |
| `vortex.xml` + `.xml.bin` | Template of the final **vortex** look |
| `combined.xml` + `.xml.bin` | Template of the final **combined** look |
| `looks.sh` | The exact generator arguments of the three production looks (sourced by the render scripts) |

Use a template directly (the grid names are fixed: `T b Q U_mag`):
```bash
sed 's|{VDB_DATA}|/scratch/.../VDB/dlrcjh_000800.vdb|' flame.xml > f.xml; cp flame.xml.bin f.xml.bin
cycles --device CPU --samples 64 --width 1920 --height 1080 --output f.png f.xml
```
The generator needs the CAD surface `constant/triSurface/DLRCJH.obj` of the case
(`src/hpc/combustion/XiFoam/DLRCJH/mesh/common/triSurface.tar.xz`, extracted to
`runs/DLRCJH/geometry/` on scratch) for the wall mesh; it is baked into the `.xml.bin`.

## Coordinates and objects

World = OpenFOAM metres: x = chamber axis (0 = front plate, flow +x), y up, chamber
cross-section 95 x 95 mm. The VDB box `(-0.005 -0.0475 -0.0475) (0.505 0.0475 0.0475)`
is normalised to a scene diagonal of 10 (object `tfm` = uniform scale + shift, the same for
the volume and the wall mesh).

* `vdb_volume` (geometry_type 2): the grids of the look, `volume_type openvdb`, linear
  interpolation, ray marching with the default step (voxel size 0.4 mm).
* `walls` (geometry_type 0, triangle mesh): cut-away combustor built from the case CAD
  surface (mm -> m). Shader slots: 0 `mat_ceramic` (chamber back wall z = -47.5 mm, floor
  y = -47.5 mm, cut at x = 505 mm; front plate `wallChamberFront` with the main-nozzle and
  7 pilot openings), 1 `mat_metal` (`wallsPilots`, 60 mm stub of `wallInletPipe`),
  2 `mat_window` (optional quartz window, off in the production looks). Top and viewer-side
  walls are removed so that the flame is seen directly.
  Mesh format of this CyclesPhi build: positions are a geometry attribute
  `<attribute name="P" std="ATTR_STD_POSITION" type="point" element="ATTR_ELEMENT_VERTEX"
  size="<nverts>" buffer="<offset>"/>` (buffer = uint64 byte count + packed float3),
  `triangles`/`shader` = `array_int`, `smooth` = `array_boolean` (1 byte per entry); a
  `verts` socket does not exist (the reader segfaults on a mesh without `P`). Closure output
  sockets are case sensitive: `BSDF`, `volume`, `emission`, `background`.
* World: `default_background` = constant dim blue-grey light for shading, and a vertical
  gradient (near black -> dark blue-grey) seen by camera rays (`light_path.is_camera_ray`).
* Optional sun (vortex look of the tests only; off in production).
* Integrator: OIDN denoiser (`use_denoise`, accurate prefilter, high quality), biased ray
  marching with `volume_step_rate 2` (2 voxels per step), `max_bounce 1` (the walls still
  receive the flame light through the one diffuse bounce; 3 bounces cost ~2x for no visible
  gain), indirect clamp 10. Production: 1920x1080, 32 spp.
* Film: Blackman-Harris 1.5 px; PNG output through `config_standard.ocio` (sRGB standard).

## Shader graphs

Ramps are 257-entry LUTs in the `.xml.bin` (colour = 16 B per entry, alpha = float),
built from piecewise smoothstep control points (`t:r,g,b;...`).

### Flame (`f_*` nodes): emission-only "fire", smoke-free

```
T --map_range(700..2100 K)--> rgb_ramp ramp_T:  color = blackbody-like LUT  (ember red ->
                                                 orange -> amber -> yellow-white -> warm white)
                                                alpha = heat(t) = ((t-0.25)/0.75)^3  (~T^4 above 1050 K)
T --map_range(950..1250 K, clamp)--> mask        (front only where the gas is already burning:
                                                 hides the unburnt jet/pilot cores and the box faces)
b --rgb_ramp ramp_b--> front(b)                  (window peaked at the flame front b = 0.5,
                                                 shoulders 0.3/0.7 = 0.35, zero below 0.12 / above 0.88)
w     = front(b) * mask(T) * front_gain + glow * heat(T)     (math multiply / multiply_add)
principled_volume: emission_color   = ramp_T.color
                   emission_strength = w * E_flame
                   density           = w * D_flame, color 0 (no scattering),
                   absorption_color  = (0.05 0.25 0.6) -> the thin absorption is warm (absorbs blue)
```
The flame front sheet (premixed flame brush) carries the light; the recirculating hot
products only add a faint `glow` so that the chamber does not turn into an orange block.
`--color-mode blackbody` replaces the LUT colour by Cycles' physical `blackbody` node fed with
`bb_scale * T` (tested, more washed-out yellow-white; the LUT gives a richer ember-to-white
gradient).

### Vortex (`v_*` nodes): Q-criterion filaments in cool colours

```
Q --map_range(Qmin..Qmax, clamp) --math power(gamma)--> rgb_ramp ramp_Q: alpha = opacity LUT
                                                         (0 below 8 %, then rising: crisp tubes, no fog)
U_mag --map_range(10..140 m/s)--> rgb_ramp ramp_U: color = indigo (slow recirculation) -> blue ->
                                                   azure -> cyan -> ice white (jet core)
principled_volume: color (scatter albedo) = emission_color = ramp_U.color
                   density           = alpha * D_vortex
                   emission_strength = alpha * E_vortex, absorption 0, anisotropy 0.35
```
Mostly self-emissive (the cores glow) with some single scattering of the world light, so
the tubes keep depth cues (overlap darkening) without needing a key light that would light
up the walls.

### Combined

`add_closure(flame principled_volume, vortex principled_volume)` in one shader on one volume
object with all four grids; the vortex layer uses a lower density so that the flame stays
visible behind it, and the walls are a warm dark grey.

## Production parameters

`looks.sh` holds the exact generator arguments: `DLR_COMMON` (box, walls, orbit),
`DLR_FLAME`, `DLR_VORTEX`, `DLR_COMBINED` and `DLR_RENDER`. Expand them with `eval`
because they contain quoted ramp strings. Mesh-dependent settings:

| | 3M (main animations) | 24M (slow-motion bonus) |
|---|---|---|
| Q map range | `--qrange 5e7 1e9` | `--qrange 1.5e8 3e9` (default of `looks.sh`) |
| Orbit frame index | `--first 40 --step 40 --nframes 225` | `--first 8 --step 8 --nframes 225` |

Key values:
* Flame: E = 100, glow 0.01, T LUT over 700-2100 K, mask over 950-1250 K, front window
  0.12-0.88 peaked at 0.5.
* Vortex: D = 40, E = 70, exposure 2.0, U range 10-140 m/s, Q power 0.7.
* Combined: flame E = 70 with glow 0; vortex D = 20, E = 130.

Measured cost per 1080p frame at 32 spp on one node (128 threads): flame ~55 s, vortex
~55 s, combined ~110 s.
