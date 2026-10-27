# Animation: Steckler room fire (fireFoam stecklerWithSpray), mesioVDB + CyclesPhi

Status: 2026-10-26, jobs 5270670 (cn357: simulation) and 5275975 (cn516-cn523: rendering).
OpenFOAM v2606, dev Mesio (`scripts/cases/ofexec_vis_mesiodev.sh`, `writer distributed`),
CyclesPhi CPU. All data on scratch, `$S = /scratch/project/eu-25-121/milanjaros/openfoam`.

## 1. Case

`src/hpc/combustion/fireFoam/RAS/stecklerWithSpray` copied (`cp -rL`) to
`$S/runs/stecklerWithSpray/case`. Room 2.8 x 2.13 x 2.8 m with a 0.74 x 1.83 m doorway in the
wall x = 1.4, exterior region (x 1.4..4.2, y 0..4.6) in front of the facade; blockMesh
3 x 120x60x80 = 1.728M hex cells; walls of the room are 1D thermal baffles (`createBaffles`).
Physics: kOmegaSST RAS, fvDOM radiation, `combustionModel none` with a volumetric heat source
(62.9 kW after 5 s) in the burner zone, CH4 injected through the burner patch, a water-spray
Lagrangian cloud injected from t = 85 s.

### v2606 compatibility
No change was needed: `run_pre.sh` (= `Allrun.pre` + `restore0Dir` + `decomposePar`:
blockMesh, two topoSets, createPatch, createBaffles) and fireFoam run unchanged on v2606
(`log.fireFoam.test1`: 3 s of physical time, no warnings except a missing `TMean/UMean` in the
original sampling function object, which is dropped in the animation run). So no swap was needed.

### Changes for the animation run (`system/controlDict`, `system/solverControls.anim`, `system/functionsVis`)
- All original function objects (probes, averages, flux summary, surface sampling, the
  `timeActivatedFileUpdate` of `solverControls`) removed; only `mesioVDB1` remains
  (`outputPolicy vdbOnly`, audit passed); solver `writeInterval 1000` (no field output).
- One set of time-step controls for the whole run instead of the 0/40/80 s switching:
  `maxCo 2, maxDeltaT 0.05`; at t = 8 s raised at run time to `maxCo 5` (wall-time budget;
  the original case uses maxCo 10 for t < 40 s).
- `endTime 62.5` (originally 120): the spray starts at t = 85 s, so the animated window
  (0..62.5 s) shows fire growth, ceiling layer, door outflow and the exterior plume, without spray.
- `decomposeParDict`: 112 subdomains (scotch) on cn357, 16 cores left for render tests.

### Smoke proxy
The case has no soot model and no combustion; the burner injects CH4, which (with
`combustionModel none`) is a passive tracer of the fire effluent. `CH4` is exported as the smoke
density, `T` gives flame and hot-gas glow.

### mesioVDB (`system/functionsVis`)
`fields (T CH4 U)` -> grids `T CH4 U_mag`; `box (-1.4 0 -1.4) (4.2 4.6 1.4)`, `density 448`
-> 448 x 368 x 224 voxels, h = 12.5 mm (mesh 23-41 mm), 27.0M active voxels (the L-shaped
domain; the empty corner above the room is outside the mesh). `writeControl adjustableRunTime`,
`writeInterval 0.25` -> 250 files `VDB/steckler_0000..0249.vdb` (t = 0.25..62.5 s),
~175 MB each, 43 GB total.

## 2. Run (`$S/runs/stecklerWithSpray/run_vis.sh vis1`, log `case/log.fireFoam.vis1`)

| Quantity | Value |
|---|---|
| Ranks / node | 112 on cn357 (`UCX_TLS=ud,sm,self`) |
| Steps | 3475, deltaT 0.0007..0.052 s (Co max 2, later 5) |
| Wall time | 4069 s (ExecutionTime 3716 s), ~1.07 s/step |
| mesioVDB export | median 0.45 s, max 1.3 s per file (distributed writer), 250 exports = ~3 % of the run |
| T max | 1895 K (heat-source zone); hot layer 350-430 K; CH4 in the layer 1e-3..4e-3 |

Motion per frame: 0.25 s physical; plume velocities 1-3 m/s -> 0.25-0.75 m per frame near the
burner, the ceiling layer and the exterior plume develop over the whole 62 s
(convective time of the 4.6 m region ~3 s, so the animation covers ~20 convective times).
A 35-frame low-resolution preview (every 5th frame) was checked before the 1080p batch.

## 3. Rendering

Scene: `data/cyclesphi/scenes/stecklerWithSpray/` (generator, template XML + .xml.bin, README with
the node graph). Final options: `scripts/vis/fire/steckler_scenes.sh <out_dir> <vdbs...>`.
Frame-parallel rendering: `scripts/vis/fire/render_xml_parallel.sh standard 1920x1080 48 <png_dir>
<nodes> <xmls...>` (one cycles process per node, node -> job mapping built in).

Look development (all in `$S/renders/stecklerWithSpray/tests/`, contact sheets `t*/out/sheet.png`):
- t2: smoke too thin, hot layer glow as a red haze -> glow reduced, smoke density x10;
- t3/t4: camera views (section view along the facade, 3/4 views from the exterior side) and
  smoke density 10..50 -> 3/4 view from the exterior side, density 25, dark sooty albedo;
- t5: boundary fade (smoke would end abruptly at the outlet y = 4.6);
- t6: key-light direction -> raking light from +x;
- t7: 1080p, 64 spp, with/without one volume bounce (~127 s per frame both; the bounce adds a
  warm glow of the ceiling layer and was kept).

Production (final look, `steckler_scenes.sh`, 1920x1080, 48 spp, OIDN):
- frames 0-192 on cn516-cn521 (started while the solver was still running, 3566 s), frames
  193-249 on cn522-cn523 (3276 s); 109 s per frame on average (one cycles process, 128 threads,
  per node); ~7.6 node-hours, ~60 min wall.
- PNGs: `$S/renders/stecklerWithSpray/final/png/steckler_0000..0249.png`
  (scene XMLs in `final/scene/`, `final/scene2/`, per-frame logs and `times.txt` in `final/png/log/`).

## 4. Results

- **Animation: `$S/renders/stecklerWithSpray/steckler_fire_cyclesphi.mp4`** (250 frames, 30 fps,
  8.3 s, H.264 CRF 18, yuv420p, 1920x1080; `scripts/vis/make_mp4.sh <png_dir> <mp4> 30`).
  The fire grows from the burner, the dark ceiling layer fills the room, smoke spills out of the
  upper part of the doorway and rises along the facade as a plume, lit by a raking key light;
  the camera orbits 16 deg.
- Contact sheet (frames 20, 60, 140, 249 = t 5.25, 15.25, 35.25, 62.5 s):
  `$S/renders/stecklerWithSpray/steckler_contact_sheet.png` (`scripts/vis/v2/tile.sh`).
- Best stills: `final/png/steckler_0140.png` (plume along the facade, warm interior),
  `final/png/steckler_0249.png` (full outflow), `final/png/steckler_0020.png` (fire + first ceiling layer).
- Low-resolution preview (every 5th frame, 640x360): `$S/renders/stecklerWithSpray/preview/`.

## 5. Issues / remarks

- RAS: the smoke is smooth (no turbulent puffing); the motion comes from the filling process.
- The spray phase (t > 85 s) was not simulated (wall-time budget, Co 0.3 required there).
- `render_xml_parallel.sh` maps nodes to jobs (cn356-cn358 -> 5270670, other nodes -> 5275975).
