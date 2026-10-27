# CyclesPhi: rendering OpenVDB volumes on Karolina CPU nodes

Notes on the CPU build of CyclesPhi (`src/cyclesphi`, branch `develop`) and on rendering
OpenVDB files (e.g. OpenFOAM time series) with it. The setup is adapted from the working
ppam2026 GPU/CPU workflow in
`/mnt/proj1/open-36-34/milanjaros/projects/blender/scripts/ppam2026/` (read-only; copies are
in `data/cyclesphi/ppam2026_scripts_orig/`).

## 1. Build

| Item | Value |
|---|---|
| Build script | `scripts/build_cyclesphi.sh` (run on a compute node) |
| Environment | `scripts/env_cyclesphi.sh` (source it; sets HOME to scratch `fakehome`) |
| Toolchain | `foss/2025b` (GCC 14.3), `CMake/3.31.8-GCCcore-14.3.0` |
| Third-party libs | Blender precompiled bundle `lib-linux_x64` @ `30d9f881` (the commit pinned by the cyclesphi submodule), copied to `install/cyclesphi_libs/linux_x64` (OpenVDB 13.0 + NanoVDB, OpenImageIO, OpenEXR, TBB, Embree 4, OIDN, OCIO, pugixml, Python 3.13 with `openvdb`/`numpy` modules) |
| Build dir | `build/cyclesphi_cpu` |
| Install dir | `install/cyclesphi_cpu` (binary `install/cyclesphi_cpu/cycles`, runtime libs in `install/cyclesphi_cpu/lib`) |
| Log | `build/logs/cyclesphi_build.log` |

```bash
srun --jobid=<JOB> --overlap -N1 -n1 -w <node> bash -c \
  'export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome; \
   JOBS=96 bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/build_cyclesphi.sh' \
  > build/logs/cyclesphi_build.log 2>&1
```

Main CMake flags: `WITH_CYCLESPHI=OFF` (the client/server part needs
`braas_hpc_renderengine`; only the standalone XML renderer `cycles` is needed here),
CUDA/OptiX/HIP/oneAPI off, USD/Hydra/OSL/Alembic off, OpenVDB + NanoVDB + Embree + OIDN on,
`CYCLES_LIB_DIR=install/cyclesphi_libs/linux_x64`. The ppam2026 GPU build
(`build_cycles_kar_gpu.sh`) used the same precompiled libs with GCC 14.2 + CUDA + ZFP.

Why the Blender bundle and not a foss/2025b OpenVDB: OIIO/OCIO/Embree/OIDN etc. are not
available as foss/2025b modules, and the bundle is what the working workflow uses. The VDB
file format is version-stable, so VDBs written by a foss/2025b OpenVDB (11/12/13) can be
read by OpenVDB 13 in the bundle.

## 2. Running the renderer

```bash
source scripts/env_cyclesphi.sh
$CYCLES_BIN --device CPU --threads 128 --samples 64 --width 1280 --height 720 \
    --output out.png scene.xml            # scene.xml.bin must exist next to scene.xml
```

Other useful flags: `--log-level info`, `--tile-size N`, `--list-devices`.
The PNG writer applies the OCIO display transform `sRGB / "AgX"` (hard-coded in
`src/app/oiio_output_driver.cpp`), using the config in `$OCIO`:

* `data/cyclesphi/colormanagement/config.ocio` – original ppam2026 config (AgX look,
  desaturated/filmic colours),
* `data/cyclesphi/colormanagement/config_standard.ocio` – same config, but the "AgX" view
  is remapped to the *Standard* sRGB transform, so colormaps appear with their real colours
  (default in `render_vdb_series.sh`, `OCIO_VIEW=agx` switches back).

## 3. XML scene format (CyclesPhi "xml + bin")

A scene is **two files**: `scene.xml` and `scene.xml.bin` (the reader refuses to load the
scene if the `.bin` is missing). Every *array* socket (`array_color`, `array_float`,
`array_int`, `array_point`, `array_transform`...) is written in the XML as a decimal **byte
offset into the .bin**; at that offset the .bin stores `uint64 count` followed by `count`
elements (float 4 B; colour/point = 4 floats = 16 B). Scalar sockets (float, int, bool,
colour, string, enum, transform) are inline text. Node references (`used_shaders`,
`geometry`) use the `name` attribute of the referenced node. `ui_name` attributes (written by
the Blender exporter) are optional.

Elements used for volume rendering (see `data/cyclesphi/make_vdb_scene.py` and the ppam2026
scenes in `data/cyclesphi/scenes_ppam2026/` for full examples):

* **Shader graph** – `<shader name="...">` containing nodes (`attribute`, `map_range`,
  `rgb_ramp`, `math`, `principled_volume`, `background_shader`, `light_path`,
  `mix_closure`, ...) with `<socket name=... value=...>` children, and
  `<connect from_node= from_socket= to_node= to_socket=>` (target `output` node, socket
  `volume` / `surface`). Special names `default_background`, `default_volume`, ... replace the
  scene defaults.
* **Density / colour mapping** (transfer function), as in the ppam2026 OpenFOAM scenes:
  `attribute(attribute=<grid>) .fac -> map_range(from_min, from_max) -> rgb_ramp(ramp, ramp_alpha)`;
  `ramp.color -> principled_volume.color`, `ramp.alpha (* k via math multiply) -> principled_volume.density`.
  `from_min/from_max` are inline floats (easy to edit); `ramp` (257 RGB entries, linear) and
  `ramp_alpha` (257 floats) live in the .bin. ppam2026 used Q range 500..10000, blue-green-red
  ramp, alpha linear 0..1, density x10. `principled_volume` also has `emission_strength`,
  `emission_color`, `absorption_color`, `anisotropy`.
* **VDB volume** – a geometry node with `geometry_type="2"` (VOLUME):
  ```xml
  <volume name="vol" geometry_type="2">
    <socket name="used_shaders" value="<shader name>" type_name="array_node" />
    <socket name="object_space" value="true" type_name="boolean" />
    <attribute name="<GRID>" std="ATTR_STD_NONE" type="float" element="ATTR_ELEMENT_VOXEL"
               flags="0" buffer="/abs/path/file.vdb" volume_type="openvdb"
               [interpolation="INTERPOLATION_CLOSEST|INTERPOLATION_CUBIC"] />
  </volume>
  ```
  The attribute `name` must equal the **grid name in the .vdb file** and the name used in the
  shader's `attribute` node. `buffer` is either an absolute .vdb path or (all digits) an
  offset of an embedded VDB stream in the .bin. Other `volume_type`s: `nanovdb`
  (.nvdb file), `nanovdb_multires`, `nanovdb_derivates[_vec4]`, `zfp` (needs
  `WITH_ZFP_LOADER`), `raw`, `cub`. The bounding mesh is generated from the grid at load
  time (the triangles/verts arrays in the ppam scenes are ignored).
* **Object** – `<object>` with `geometry` (node name) and `tfm` (3x4 row-major transform,
  12 floats: `r00 r01 r02 tx r10 r11 r12 ty r20 r21 r22 tz`); maps VDB world coordinates to
  scene coordinates (ppam: 0.01 scale + Y-up -> Z-up rotation).
* **Camera** – `<camera name="camera">` with `matrix` (3x4 row-major; columns = right, up,
  forward (view direction), position; Cycles camera looks along +Z of its frame), `fov`
  (radians, spans the shorter image side), `nearclip`, `farclip`, optional
  `panorama_type`/`full_width`/`viewplane.*`. With `--width/--height` given on the command
  line the viewplane is recomputed automatically when the aspect ratio differs.
* **Lights** – lights are geometry nodes: background light
  `<backgroundlight geometry_type="5">` with `used_shaders=default_background`,
  `light_type=background`, plus an `<object>` referencing it; the world shader is
  `<shader name="default_background">` (ppam: environment texture `city.exr` for lighting,
  constant grey seen by camera rays via `light_path.is_camera_ray` + `mix_closure`).
  Other lights: `<arealight geometry_type="4">`, `<pointlight geometry_type="6">`,
  `<spotlight geometry_type="7">`, `<sunlight geometry_type="8">` (cf. `Geometry::Type`
  in `src/scene/geometry.h`), each placed by an `<object>` with `tfm`.
* **Integrator / film / background** – `<integrator>` (`max_volume_bounce`,
  `volume_ray_marching` (biased ray marching), `volume_max_steps`, `use_adaptive_sampling`),
  `<film>`, `<background>` (`visibility`).

## 4. Rendering a VDB time series (OpenFOAM output)

Files:

* `data/cyclesphi/render_vdb_series.sh` – renders all `*.vdb` in a dir (or a glob), one PNG
  per file:
  `render_vdb_series.sh <vdb_dir|glob> <grid> <out_dir> [WxH] [samples]`
* `data/cyclesphi/make_vdb_scene.py` – writes a template `template.xml` + `template.xml.bin`
  with placeholders `{VDB_DATA}`, `{GRID_NAME}`; computes the world bbox and value range from
  a VDB (bundled Python + `openvdb` module) or takes `--bbox`/`--range`; the object transform
  normalises the data box to diagonal 10 centred at 0, camera orbits it (`--azimuth`,
  `--elevation`, `--up`, `--fov`, `--zoom`); colormaps viridis/inferno/plasma/coolwarm/turbo/
  ppam/gray; opacity `--alpha-min`, `--alpha-gamma`, `--density`, `--emission`.
* `data/cyclesphi/template_vdb_volume.xml(+.bin)` – reference output of the generator for a
  unit box [0,1]^3 and value range 0..1 (viridis). For real data either regenerate it
  (`make_vdb_scene.py --vdb ... --grid ...` or `--bbox ... --range ...`) or edit
  `from_min/from_max` (map range) and the object `tfm` by hand.
* `data/cyclesphi/run_render_ppam_cpu.sh` – CPU version of the ppam2026 render (original
  scene + `.bin`, AgX look).

Template command (on a compute node):

```bash
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
WS=/mnt/proj2/eu-25-121/milanjaros/openfoam
# fixed colour range for all time steps, z-up domain, 1080p, 128 spp
SCENE_ARGS="--range 0 3.0 --colormap viridis --density 8 --alpha-min 0.1 --azimuth 40 --elevation 25 --up z" \
  $WS/data/cyclesphi/render_vdb_series.sh '/scratch/.../vdb/U_mag_*.vdb' U_mag \
  /scratch/project/eu-25-121/milanjaros/openfoam/renders/U_mag 1920x1080 128
# then e.g.: ffmpeg -framerate 24 -pattern_type glob -i 'renders/U_mag/*.png' U_mag.mp4
```

Notes for OpenFOAM VDBs:

* Grid must be a **FloatGrid** (scalar); vector fields (U) need a magnitude grid (`U_mag`).
* Without `--range` the range of the first file is used for the whole series (min/max over
  all voxels can be dominated by outliers – better give `--range` explicitly, e.g. Q > 0
  iso-range for vortices).
* Sparse grids: inactive voxels = background value (usually 0) -> transparent if
  `--alpha-min` > normalised background.
* `--density` is per scene unit with the box diagonal normalised to 10; start with 2-10.
* `TEMPLATE=<xml>` reuses a hand-tuned template (e.g. edited camera).

## 5. Verification (2026-10-26, cn358, 128 threads)

* Build: `install/cyclesphi_cpu/cycles` (Release, GCC 14.3, ~10 min with 96 jobs).
* Original ppam2026 scene, CPU: `data/cyclesphi/run_render_ppam_cpu.sh` (defaults: VDB
  `/mnt/proj1/.../PPAM/aircraft_512/origin.vdb`, 590 MB, grid `Q_in_nodes`, scene
  `openfoam_ofstore.512.xml`, 640x360, 16 spp) ->
  `/scratch/project/eu-25-121/milanjaros/openfoam/renders/cyclesphi_test/openfoam_ofstore.512.origin.cpu.png`
  (Q-criterion vortex tubes of the aircraft wake, blue-green-red ramp, AgX look);
  total 5.8 s, of which 3.2 s path tracing.
* Generated template, series script:
  `render_vdb_series.sh ".../aircraft_512/vdb/psnr.02*.vdb" Q_in_nodes .../cyclesphi_test/series 640x360 16`
  with `SCENE_ARGS="--range 500 10000 --colormap viridis --density 8 --up y"` -> 
  `renders/cyclesphi_test/series/psnr.0{20,25}.png`, ~4 s per frame.

## 6. Pitfalls

* Colour sockets need **4 numbers** (`"r g b 0"`); with 3 the reader prints
  `Wrong number of values (3, expected a multiple of 4)` and silently keeps the default
  (render_vdb_series.sh greps the logs for such XML warnings).
* `Unknown socket "verts" in ... (volume)` from the ppam scenes is harmless.
* Missing `scene.xml.bin` -> "Could not open file for reading" and an empty scene.
* The value range / bbox printed by `make_vdb_scene.py` comes from the first file only.
* The camera distance fits the bounding sphere of the box (conservative); use
  `--zoom 1.3..2` to fill the frame.
