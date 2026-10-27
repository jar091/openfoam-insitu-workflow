# Animation: DLR jet-in-hot-coflow flame (reactingFoam DLRJHC 1M), mesioVDB + CyclesPhi

Status: 2026-10-27, jobs 5270670 (cn356-cn358: simulation) and 5275975 (cn516-cn523,
cn319-cn321: rendering). OpenFOAM v2606, dev Mesio (`scripts/cases/ofexec_vis_mesiodev.sh`,
`writer distributed`), CyclesPhi CPU. Data on scratch, `$S = /scratch/project/eu-25-121/milanjaros/openfoam`.

## 1. Case and v2606 fixes

`src/hpc/combustion/reactingFoam/LES/DLRJHC/{1M,4M}` copied with `cp -rL` to
`$S/runs/DLRJHC/{1M,4M}` (`run_pre.sh <1M|4M> <nproc>`: 0.orig -> 0, blockMesh, checkMesh,
decomposePar). Quarter of the burner (symmetry planes x = 0, y = 0), 2 mm CH4 jet at 163 m/s
(600 K) in a 1490 K vitiated coflow (4.1 m/s), nozzle tip at z = 8 mm, chamber 120 mm high;
LES (kEqn, cubeRootVol delta), PaSR, reduced GRI mechanism (36 species, 219
reactions) with TDAC (DAC reduction + ISAT tabulation).

v2606 incompatibilities fixed in the copies:
1. `system/blockMeshDict`: the cell counts are computed with `#calc` and come out as doubles
   (e.g. 3.6363636); v2606 refuses them ("Expected integral (int32), found non-integral value").
   Wrapped in `label(...)` (truncation, as older versions did implicitly):
   `nCellsZ1 #calc "label(max(abs($bottomNoz / $avgMeshSize),1))";` (all `nCells*` entries;
   originals kept as `blockMeshDict.orig`). Result: 1M = 1,046,721 cells, 4M = 3,949,033 cells,
   checkMesh OK.
2. `constant/chemistryProperties`: TDAC `log on` (reduction and tabulation) writes ~10 statistics
   files per rank into `processor*/TDAC/`; set to `log off` for the VDB-only runs.
3. `system/decomposeParDict`: the original `simple (1 1 24)`. Scotch on 128 ranks gave a strong
   chemistry load imbalance (2.3-2.6 s/step); slabs along the jet axis put a piece of the
   reacting jet on every rank: `simple (2 2 64)` on 256 ranks 1.0 s/step at the start,
   `simple (2 2 96)` on 384 ranks for the production run.

Cost (1M): the 4M mesh would need ~1.6x more steps (finer cells, same Courant number) at a
similar cost per step per rank, i.e. > 3 h on 3 nodes for 1.5 ms; the 1M mesh was used.

## 2. Runs

Common: `system/functionsVis` = `mesioVDB1` only (`fields (T OH Qdot CH4)`,
`box (0 0 0) (0.025 0.025 0.12)`, `voxelSize 0.00013` -> 193 x 193 x 924 = 34.4M voxels,
mesh 0.09-0.6 mm near the axis), `writeControl adjustableRunTime; writeInterval 6e-6`
(250 frames over 1.5 ms), `outputPolicy vdbOnly`, solver output off, the original sampling
function objects removed, `maxCo 0.6` (original 0.4), `endTime 1.5e-3` (original 5e-3).
Motion per frame: 6 us x 163 m/s = 1 mm of jet travel near the nozzle (~1 % of the 120 mm
region); 1.5 ms = 2 convective times of the jet (120 mm / 163 m/s = 0.74 ms).

### 2.1 Run 1 (laminar, superseded): `$S/runs/DLRJHC/1M`, log `log.reactingFoam.vis1`
256 ranks on cn356+cn358, from t = 0 with the original inlet. 1141 steps, 0 -> 0.85 ms in
3331 s, then stopped (`stopAt writeNow`, restart `processor*/0.0008504`), 141 VDB files
(`VDB/jhc_0000..0140.vdb`, 282 MB each, 36 GB). Axial slices (`$S/tmp/fire_agent/slice136.png`)
showed a completely laminar jet: a smooth cold CH4 column with a thin flame sheath and a
starting-jet head; the LES on this mesh, with no inflow perturbation, does not transition within
the domain. Rendered tests: `$S/renders/DLRJHC/tests/t1..t4`.

### 2.2 Run 2 (production): `$S/runs/DLRJHC/1M_turb`, log `log.reactingFoam.turb1`
Same case, restarted from t = 0 with a random fuel-inlet perturbation (`0/U`):
```
fuel_inlet { type turbulentInlet; referenceField uniform (0 0 163.18);
             fluctuationScale (0.5 0.5 0.5); alpha 0.3; value uniform (0 0 163.18); }
```
(components fluctuate by +-0.5 x 0.5 x |U|, low-pass filtered with alpha 0.3, ~6 % rms).
384 ranks on cn356-cn358 (`run_vis_turb.sh turb1`). The perturbation produces varicose
waves on the jet core and a wrinkled flame with vortex structures at the head; the jet is
still not fully turbulent at 1M resolution.

| Quantity | Value |
|---|---|
| Ranks / nodes | 384 on cn356-cn358 (`UCX_TLS=ud,sm,self`) |
| Physical time | 0 -> 1.35 ms (`endTime` lowered from 1.5e-3 at run time at t = 0.97 ms, wall-time budget) |
| Steps | 2003, deltaT 0.27..1.27 us (maxCo 0.6) |
| Wall time | 8266 s (2 h 18 min), 4.1 s/step mean; the cost per step grows with the flame (chemistry): 2.2 s/us of physical time at the start, ~7 s/us at the end |
| mesioVDB export | 225 files `VDB/jhc_0000..0224.vdb` (~285 MB, 60 GB), median 0.67 s, max 1.45 s, 152 s in total = 1.8 % of the run |
| T max | 2086 K at the end; flame OH up to 5e-3 |

## 3. Rendering

Scene: `data/cyclesphi/scenes/DLRJHC/` (generator, template, README with the node graph);
final options `scripts/vis/fire/jhc_scenes.sh`; follow-mode driver
`scripts/vis/fire/follow_render.sh` (renders new VDB files while the solver runs, on 11 nodes).

Look development (`$S/renders/DLRJHC/tests/t*/out/sheet.png`):
- t1-t4: laminar run; emission scale (thin flame -> emission 200-600 per scene unit), OH colour,
  rim light (removed: visible as a disc, no benefit without scattering);
- t5-t7: production run; brighter blackbody, cold-jet glow (CH4), the seam at the mirror planes
  (fixed by overlapping the copies, `--mirror-shift`);
- t8: 1080p still (262 s at the default voxel step -> object step 0.25 mm: 1.6x faster);
- t9: seam/step tests on a close-up; t10: OH sheath weighting `(1 - h)` so that OH shows as a
  blue-violet edge around the blackbody core instead of tinting it pink.
- Preview: 28 frames (every 5th) at 640x360 (`$S/renders/DLRJHC/preview/sheet8.png`); found
  the whole box glowing in frame 0 (initial OH = 0.001 above the old OH threshold) -> OH window
  starts above 0.0012.

Production: `follow_render.sh` started while the solver was running (first round at 23:57),
11 nodes (cn516-cn523, cn319-cn321), one cycles process per node.
- Frames 0-7, 11-18, 22-29 (24 frames) were rendered with 64 spp / 0.25 mm step (174 s per frame);
  the follow driver was then restarted with 32 spp / 0.4 mm step (~62 s per frame); the two
  settings give visually identical images (t11 crops), so the 24 frames were kept.
- 225 frames, mean 72 s per frame (including the slow ones), ~4.5 node-hours; the renders kept up
  with the solver (one export every ~35 s at the end) and were complete one minute after the
  solver finished (01:13).
- First round on cn319-cn321 failed (`render_xml_parallel.sh` mapped them to job 5270670);
  fixed (cn356-cn358 -> 5270670, all other nodes -> 5275975), the follow loop re-rendered them.

## 4. Results

- **Animation: `$S/renders/DLRJHC/DLRJHC_jetflame_cyclesphi.mp4`** (225 frames, 30 fps, 7.5 s,
  H.264 CRF 18, yuv420p, 1920x1080). Cold jet (faint blue) entering the hot coflow, ignition
  along the jet sides (~0.25 ms), a growing flame with a blackbody core and a blue-violet OH
  sheath, wrinkled head vortices; the camera orbits 50 deg around the jet axis and dollies out.
- Contact sheet (frames 60, 120, 170, 224 = t 0.37, 0.73, 1.03, 1.35 ms):
  `$S/renders/DLRJHC/DLRJHC_contact_sheet.png`.
- Best stills: `final/png/jhc_0224.png` (full flame, head structure), `final/png/jhc_0170.png`,
  `final/png/jhc_0115.png` (OH sheath around the orange core).
- PNGs `$S/renders/DLRJHC/final/png/`, scene XMLs `final/scene/` (and `final/scene_old/` for the
  first 24 frames), logs `final/png/log/`, follow logs `final/follow*.log`.

## 5. Issues / remarks

- At 1M cells the LES jet is laminar without inflow perturbation (run 1); with `turbulentInlet`
  it develops waves and a wrinkled head, but not a fully turbulent flame within 1.35 ms. A finer
  mesh (4M/11M) or a longer run (several flow-through times, the case's original 5 ms) would be
  needed for a developed turbulent lifted flame; both exceed the wall-time budget of this task
  (detailed chemistry: 4-7 s per microsecond on 3 nodes).
- The quarter domain is mirrored four times, so the image is symmetric about the jet axis;
  a faint crease remains along the axis in some frames (symmetry-plane flame sheets).
- `Qdot` is exported but not used by the final shader (OH and T give the cleaner look).
