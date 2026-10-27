# Production visualization runs (mesioVDB, anariVis, CyclesPhi)

Status: 2026-10-26, job 5270670 (Karolina, CPU). OpenFOAM v2606 cases from
`docs/notes/cases_prepared.md`, with these function objects:
- `mesioVDB` writes one OpenVDB file per export step
  (`docs/notes/mesio_openfoam_functionobject.md`).
- `anariVis` renders in-transit with Barney `"mpi"` on separate render nodes
  (`docs/notes/anari_openfoam_insitu_intransit.md`).

The VDB series are then rendered offline with CyclesPhi (`docs/notes/cyclesphi_render.md`).
All run data, VDBs and images are on scratch (`$S = /scratch/project/eu-25-121/milanjaros/openfoam`).

## 0. Common tools (new)

| File | Purpose |
|---|---|
| `scripts/cases/ofexec_vis.sh` | Fast per-rank launcher for OpenFOAM + mesioVDB + anariVis. It sources the `export -p` dump `runs/of_env_v2606_vis.sh` (= `env_anari_openfoam.sh` + `MESIO_ROOT`/`OPENVDB_ROOT`, `OMP_NUM_THREADS=1`). `--mkenv` regenerates the dump. `RENDER_RANK=1` unsets `OMP_NUM_THREADS` for render ranks. |
| `runs/<case>/run_vis.sh` | In-transit MPMD launch: one heterogeneous `srun` step, `<solver> -parallel -world sim : anariVisRender -parallel -world render -mpi-threads`, with `--kill-on-bad-exit=1`. Without that flag the render world keeps waiting when the solver dies. |
| `scripts/vis/pyvdb.sh` | Runs Python with the bundled python3.13 + `openvdb`/`numpy` of the CyclesPhi lib bundle. |
| `scripts/vis/vdb_stats.py` | Grid statistics (min/max, percentiles, Q threshold counts), used to choose transfer functions. |
| `scripts/vis/vdb_set_background.py` | Copies one grid with a new background value (see 1.4). |
| `scripts/vis/set_tf.py` | Edits a CyclesPhi template (from `make_vdb_scene.py`) in place: piecewise-linear opacity and colour ramp in the `.xml.bin`, inverted/explicit map range. |
| `scripts/vis/render_frames_parallel.sh` | Frame-parallel CyclesPhi rendering: one `cycles` process per node, frames round-robin, existing PNGs skipped (resumable). |
| `scripts/vis/make_mp4.sh` | PNG series to H.264 MP4 (module `FFmpeg/7.1.2-GCCcore-14.3.0`). |
| `scripts/vis/follow_render_pitz.sh` | Login-node driver that follows a running export. Each round it copies the grid of every new VDB with a chosen background (`GRID`, `BG`, `BGDIR`, `CONV_NODE`), then renders all frames without a PNG via `render_frames_parallel.sh`. It stops once the solver log has `End`. |
| `runs/pitzDaily3D/62M/run_mesio.sh` | Single-world XiFoam launch through `scripts/cases/ofexec_vis_mesiodev.sh` (fixed Mesio). By default it sets `MESIO_VDB_WRITER=single`; `NOENVWRITER=1` uses the controlDict `writer` key instead. |

## 1. HPC_motorbike Small (simpleFoam, 8.77M cells, 512 ranks on cn647-cn650)

Case `$S/runs/HPC_motorbike/Small`. Restart from `processor*/500` (100 iterations, 500 -> 600).
`system/controlDict` sets `writeInterval 1000000` (no solver writes, `vdbOnly` audit passes) and
`functions { #include "functionsVis" }`.
- `system/functionsVis`: `Q1`, `magU1` (every 2 iterations) and `vorticity1` (every 20), all with
  `writeControl none`. Then `mesioVDB1` and `#include "anariVisDict"`.
- The dictionaries of the first production run are kept in `logs_vis/dicts_prod1/`.

### 1.1 mesioVDB settings
`fields (U p Q vorticity)` -> grids `U_mag p Q vorticity_mag`.
`box (-0.5 -0.8 0) (2.9 0.8 1.8)` covers the bike (x -0.29..1.75, y -0.35..0.33, z 0..1.35) and the
near wake. `density 512` gives 512 x 241 x 272 voxels (32.5M active), h = 6.64 mm.
Export every 20 iterations (5 VDBs, 396 MB each, `VDB_prod1/motorbike_000{520..600}.vdb`).

Note: `box` is an OpenFOAM `boundBox`, written `(x0 y0 z0) (x1 y1 z1)`. The form
`((..) (..))` from the earlier notes fails with "Wrong token type"; the notes are corrected.

### 1.2 anariVis settings (in-transit, Barney "mpi")
- 1920x1080 frames, `dropPolicy drop`, every 2 iterations.
- prod1 (cn651-cn652): bike patch (`patches (motorBikeGroup)`) coloured by p (coolToWarm,
  -300..200), a floor cutting plane, and a Q = 5e4 iso-surface coloured by |U|.
  The Q iso-surface mostly wraps the bike's boundary layer. Q is huge near walls: the 99th
  percentile is 8.3e3, the 99.9th 9.7e4, and the maximum 4.9e7. So a Q iso-surface is not a
  good wake visual for this steady RANS case.
- prod2c (cn651-cn654): bike coloured by p (-350..200), plus a low-velocity |U| volume
  (`magU`, 320 points along x over the VDB box, opacity high for slow fluid). This shows the wake.

### 1.3 Timings (UCX_TLS=ud,sm,self)
Function objects of step n run at the start of step n+1, so the per-step times in the logs are
shifted by one.

| Quantity | Value |
|---|---|
| simpleFoam, pure iteration | 0.215 s (0.76 s in the old default-UCX run) |
| mesioVDB first export: context setup (Mesio mesh build + voxelisation) | 4.8-4.9 s |
| mesioVDB export, 32.5M voxels x 4 grids | 9.8 s (fields 0.002, convert 0.05, sample 0.73, gather 0.85, **write 8.85** on the single writer) |
| mesioVDB overhead per export interval | 9.8 s per 20 iterations (4.3 s of solver): **~230 %**. Single-writer bound; for the cheap 8.8M-cell case a VDB every 100+ iterations, or fewer grids, would be needed to stay under 15 %. |
| anariVis extraction on the solver | 0.23 s/frame (bike + Q iso), 0.04 s/frame (bike + volume, after the 0.4 s first-frame setup) |
| Barney render (2 nodes / 4 nodes) | 12.2 s / 15.9 s per 1080p frame at 16 / 24 spp (+0.5 s PNG) |
| In-transit frames, 100 iterations | 5 rendered, 45 dropped (both runs). The solver is ~60x faster than the renderer. |
| Run wall (100 its, 5 exports + ANARI) | 67 s ExecutionTime (pure solver ~22 s) |
| CyclesPhi 960x540, 32 spp | 5-11 s/frame (tests) |
| CyclesPhi 1920x1080, 128 spp | 99-102 s/frame (5 nodes in parallel, 1 frame each) |
| CyclesPhi 1920x1080, 256 spp | 152 s/frame |

### 1.4 CyclesPhi renders
The velocity deficit (wake) is shown by an **inverted** U_mag map: t = (20 - |U|)/20, with
opacity 0 for |U| > 15 m/s.
- Problem: inactive voxels (outside the box, inside the bike) carry the background 0, which
  maps to t = 1. At the box faces, trilinear interpolation between active voxels and the
  background 0 runs through all t values, so the box walls render as opaque sheets.
- Fix: rewrite the grid with background = 20 (freestream) using `vdb_set_background.py`
  (2 s per file). The box edges and the bike interior then become transparent, and the bike
  appears through its low-velocity boundary layer.

Commands:
```bash
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
srun --jobid=5270670 --overlap -N1 -n1 -c 16 -w <node> bash $P/scripts/vis/pyvdb.sh \
    $P/scripts/vis/vdb_set_background.py <in.vdb> U_mag 20 $S/renders/motorbike/vdb_bg20/<file>.vdb
# template: side view, inverted map + custom TF/colours
bash $P/scripts/vis/pyvdb.sh $P/data/cyclesphi/make_vdb_scene.py --out side_tpl.xml \
    --bbox -0.5 -0.8 0 2.9 0.8 1.8 --range 0 20 --density 15 --emission 0.4 --light-strength 1.5 \
    --azimuth -90 --elevation 10 --up z --zoom 1.75
bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/set_tf.py side_tpl.xml --invert \
    --alpha "0:0,0.25:0,0.5:0.1,0.8:0.35,0.9:1,0.97:1,0.985:0,1:0" \
    --colors "0:0.05,0.05,0.35;0.25:0.1,0.25,0.85;0.5:0.1,0.7,0.9;0.7:0.45,0.9,0.4;0.85:1,0.8,0.2;0.93:1,0.45,0.1;1:0.9,0.15,0.05"
bash $P/scripts/vis/render_frames_parallel.sh side_tpl.xml U_mag $S/renders/motorbike/final/U_wake_side \
    1920x1080 128 cn356,cn357,cn358,cn627,cn629 $S/renders/motorbike/vdb_bg20/*.vdb
```
Vorticity (no inversion needed): `SCENE_ARGS="--range 60 3000 --colormap inferno --density 25 --emission 1.5 --alpha-min 0 --alpha-gamma 0.7 --azimuth -60 --elevation 18 --up z --zoom 1.8"`.

**Best images** (`$S/renders/motorbike/final/`):
- `U_wake_side/motorbike_000600.png`: side view, wake deficit, 128 spp. Best overall.
- `U_wake_front34/motorbike_000600.png`: front 3/4 view, 256 spp.
- `vorticity/motorbike_000600.png`: vorticity shell of bike and rider, wake shadow on the floor.
- `U_wake_side.mp4`: the 5 VDB steps, nearly identical (steady RANS).

In-transit ANARI images:
- `$S/runs/HPC_motorbike/Small/images_anari/` (prod2c: wake volume; best `motorbike_000580.png`)
- `images_anari_prod1/` (Q iso)

Exploration renders: `$S/renders/motorbike/tests/`.

### 1.5 Problems found and fixed
1. **anariVis volume deadlock** (real bug, fixed). `cellPointWeight` triggers the lazy
   `polyMesh::tetBasePtIs()`, whose construction is collective (`syncTools` face sync). Ranks
   without any volume sample point never called it, so all others blocked. This happens when
   a subdomain lies outside the volume `bounds` or is smaller than the grid spacing; the cavity
   tests never hit it. The fix in
   `src/openfoam-insitu-modules/anariVis/functionObject/anariVisVolumeSampler.C::setup()` calls
   `mesh_.tetBasePtIs()` on all ranks before the sampling loop (cellPoint scheme). Rebuilt with
   `scripts/build_anariVis.sh` (log `build/logs/anariVis_build_tetfix.log`). The old library is
   kept at `$S/runs/HPC_motorbike/Small/logs_vis/libanariVis.so.before_tetBasePt_fix`.
2. **Mesio segfault in `MESIOInSituCommit`** (`espreso::mesh::linkNodesAndElements`,
   `pure.cpp:124`, element node index out of range) at the first export (context creation).
   **Fixed by the Mesio agent** in `install/mesio-dev`: a heap-buffer-overflow read on the
   in-situ FVM path, confirmed with ASan. Use the dev build via `scripts/cases/ofexec_vis_mesiodev.sh`.
   With it: cavity3D 8M passed 3 of 3 runs, and pitzDaily 62M passed 5 of 5 runs
   (1 production + 4 writer tests). Before the fix:
   - motorbike 512 ranks: 1 of 4 runs failed;
   - cavity3D 8M 512 ranks: 1 of 1 failed;
   - pitzDaily3D 62M 2048 ranks: 5 of 5 failed, with and without anariVis, with and without `box`.

   Logs of the failing runs: `runs/HPC_motorbike/Small/logs_vis/log.vis.prod2b`,
   `runs/pitzDaily3D/62M/logs_vis/log.vis.test1`, `log.mesioOnly1`, `log.mesioOnly_nobox`,
   `runs/cavity3D/8M/logs_vis/log.icoFoam.startup`.
3. The `colour` of a `cuttingPlane` surface without `colourField` seems to be ignored by
   Barney: the floor renders light grey for both 0.22 and 0.12.

## 2. pitzDaily3D 62M (XiFoam LES flame, 2048 ranks on cn631-cn646)

Case `$S/runs/pitzDaily3D/62M`, 62.2M cells, deltaT 5e-7 s, `UCX_TLS=ud,sm,self`.
Because of the Mesio crash (1.5) the work was split into two runs: first anariVis only,
then mesioVDB with the fixed Mesio from the written restart.

### 2.1 Run 1: anariVis in-transit, 2200 steps (t = 0.095401 -> 0.096501)
Commands:
- `bash run_vis.sh anari1h`: XiFoam on 2048 ranks (cn631-cn646, `-world sim`) +
  `anariVisRender` on cn651-cn655 (5 render ranks, `-world render -mpi-threads`).
- Dictionaries: `system/controlDict.anari1h` (`writeControl runTime; writeInterval 0.0011` =
  endTime - startTime, so the restart **`processor*/0.096501`** is written at the end) and
  `system/functionsVis` (`Q1`, `magU1` every 10 steps, `#include "anariVisDict"`).
- Scene (`system/anariVisDict`), 1920x1080, 16 spp, Barney `"mpi"`, `dropPolicy drop`, a
  frame every 10 steps:
  - T volume (512 points along x over the chamber box (-0.02 -0.0254 -0.01905) (0.29 0.0254
    0.01905), inferno 300..1700 K, opacity peaked at the flame front);
  - Q = 5e6 iso-surface coloured by |U| (opacity 0.6);
  - lower wall.

| Quantity | Value |
|---|---|
| Wall time | 3317 s (ExecutionTime 3221 s, 1.464 s/step mean) |
| Solver step without vis | 1.43 s mean (median 1.33 s) |
| Step carrying an anariVis frame | 1.80 s: +0.37 s per frame (extract 0.13 s, Q/mag, send), **2.6 % overhead** at one frame per 10 steps |
| Barney render on 5 nodes | 6.04 s render + 0.4 s PNG per frame (6.5 s total); the renderer waits ~8.4 s per frame for data |
| Frames | **220 rendered, 0 dropped** |

Output:
- `$S/runs/pitzDaily3D/62M/images_anari/pitz_190810..193000.png`
- animation **`$S/renders/pitzDaily3D/pitz_anari_intransit.mp4`** (220 frames, 24 fps, 24 MB)
- example frame `images_anari/pitz_191880.png`

### 2.2 Run 2: mesioVDB (fixed Mesio), 1500 steps (t = 0.096501 -> 0.097251), 100 VDB frames
Commands:
- `bash run_mesio.sh vdb1` with `system/controlDict.mesioRun` (= `controlDict` now; no solver
  writes, `vdbOnly`) and `system/functionsVis.mesioRun`.
- `fields (T b U Q)` -> grids `T b U_mag Q`.
- `box (-0.02 -0.0254 -0.01905) (0.29 0.0254 0.01905)`, `density 768` gives 768 x 126 x 95
  voxels (8.47M active, h = 0.40 mm).
- An export every 15 steps; 100 files of 100 MB in `$S/runs/pitzDaily3D/62M/VDB/pitz_193005..194490.vdb` (9.9 GB).
- Writer: `single` (`MESIO_VDB_WRITER=single`, as recommended for the production run).

| Quantity | Value |
|---|---|
| Wall time | 2548 s (ExecutionTime 2467 s = 1.645 s/step) |
| Solver step without export | 1.45 s |
| Context setup (first export) | 0.73 s |
| Export, single writer | 2.94 s mean (first 4.18 s): convert 0.10-0.22, sample 0.002-0.015, gather 0.26-0.75, write 2.5-3.8 |
| **Export overhead** | 2.94 s per 15 steps (21.8 s) = **13.5 %**, measured overall 1.645 vs 1.450 s/step = 13.4 % |

#### Writer comparison on 16 nodes (2048 ranks, 4 exports each, `NOENVWRITER=1`)
These runs use the dev `writer` key: logs `logs_vis/log.mesio.wtest_<writer>_<density>`, output `VDB_wtest_*`.

| writer | density | voxels (active) | file | export time (first / steady) | main phases (steady) |
|---|---|---|---|---|---|
| single | 768 | 8.47M | 100 MB | 4.18 / 2.9 s (production run, mean of 100) | write 2.5-3.8 s on rank 0 |
| distributed | 768 | 8.47M | 100 MB | 0.98 / 1.04-1.06 s | gather 0.81-0.91, file 0.70-0.76 |
| parallel | 768 | 8.47M | 100 MB | 1.04 / 0.67-0.82 s | file 0.55-0.71, gather 0.005 |
| distributed | 1536 | 67.4M | 760 MB | 3.18 / 2.11 s | gather 1.82-1.95, file 1.53-1.82 |
| parallel | 1536 | 67.4M | 760 MB | 1.64 / 0.78-1.19 s | file 0.64-1.05, gather 0.014 |

- All writers give identical files (byte size 105,029,454 for frame 193005 from single,
  distributed and parallel) and identical grid statistics.
- With `writer parallel`, an export every 15 steps costs ~3-5 % instead of 13.5 %, even at
  8x the voxels (density 1536, 0.2 mm, 67M voxels). That allows a finer grid or an export
  every 5 steps within the 10-15 % budget.
- The first export includes the plan (0.2-0.7 s).

### 2.3 CyclesPhi frame series
Both series ran **while the solver was running**, using `follow_render_pitz.sh`
(10 nodes cn358, cn647-cn655, one cycles process per node, frames round-robin).
Each new frame was ready ~20-30 s after its export.

- **b flame sheet** (`$S/renders/pitzDaily3D/b_flame/`, 100 frames, 1920x1080, 128 spp, ~18-28 s/frame):
  - Grid b (regress variable), copied with background 1 (unburnt) into `$S/renders/pitzDaily3D/vdb_b_bg1/`.
    With background 0, interpolation at the box faces crosses b = 0.5 and draws a faint box sheet.
  - Opacity window around b = 0.5 (`0:0,0.36:0,0.5:1,0.64:0,1:0`), warm flame colours, emission 2.
  - Camera `--azimuth -20 --elevation 28 --up y --zoom 2.0`.
  - Animation **`$S/renders/pitzDaily3D/pitz_b_flame_cyclesphi.mp4`** (100 frames, 24 fps).
- **Q vortex tubes** (`$S/renders/pitzDaily3D/Q_vortices/`, 100 frames, 128 spp, ~25 s/frame):
  - Q range 3e5..1e7, viridis, density 40, emission 2.5, alpha gamma 0.6.
  - Animation **`$S/renders/pitzDaily3D/pitz_Q_vortices_cyclesphi.mp4`**.
- High-resolution stills from the 67M-voxel `writer parallel` test (density 1536), 256 spp, 62-64 s/frame:
  - **`$S/renders/pitzDaily3D/hires1536/b/pitz_193050_b1536.png`**
  - `$S/renders/pitzDaily3D/hires1536/Q/pitz_193050.png`

Templates are in `b_flame/template.xml` and `Q_vortices/template.xml` (+ `.bin`).
Test renders (T and b variants) are in `$S/renders/pitzDaily3D/tests/`.
`T` alone reads as a murky block, because the burnt gas fills the lower half of the chamber.
The b = 0.5 sheet is the clearest view of the flame front.

### 2.4 State of the case
- Latest restart: `processor*/0.096501` (written by run 1, complete for all 2048 ranks).
- Older restarts: `processor*/0.095401` and the original `0.0932695`.
- `system/controlDict` is the VDB-run version (`startFrom latestTime; endTime 0.097251`, vdbOnly).
  A run started now would continue from 0.096501.
- Dictionaries of all runs are kept in `system/` with `.anari1h`, `.mesioRun`, `.wtest_*` and `.before_vis` suffixes.

### 2.5 v2/v3 animations (CyclesPhi, 81M-voxel VDBs, blackbody flame)
Goal: replace the dull 8.5M-voxel animations of 2.3 with bright, well-framed 1080p
animations. All files are on scratch: `$S/renders/pitzDaily3D/v2/` and `.../v3/`.
The scripts are in `scripts/vis/v2/`. The final scenes and a README describing the node
graphs are in `data/cyclesphi/scenes/pitzDaily3D/`.

**Simulation + export** (both runs restart from `processor*/0.096501`; `run_mesio.sh <tag>` with
`NOENVWRITER=1`; dictionaries `system/controlDict.v2|v3`, `functionsVis.v2|v3`):
- mesioVDB settings:
  - `fields (T b U Q)`, `writer parallel`;
  - box `(-0.004 -0.0254 -0.01905) (0.29 0.0254 0.01905)` (lip to outlet; the flame front and
    the vortices fill the whole cross-section);
  - `density 1536`: 1536 x 266 x 199 voxels (77-81M active), h = 0.19 mm (about the mesh
    spacing), 0.91 GB per file.
- v2: an export every 10 steps, 260 frames (`VDB_v2`, 221 GB), 2600 steps.
  - Run: 3969 s wall, ExecutionTime 3713 s = 1.43 s/step.
  - Export: median 1.04 s, max 2.7 s, total 273 s, i.e. ~7 % of the run.
  - Problem: the 260 frames span only 1.3 ms, so the structures move ~0.07 mm per frame and
    **the v2 animations look static**.
- v3: an export every 50 steps (25 us per frame), 300 frames, 15000 steps
  (7.5 ms ~ 0.33 flow-through of the 0.3 m chamber at 13.3 m/s); 1.42 s/step.
  - Motion check on the first 10 rendered frames (`scripts/vis/v2/flicker.py`, mean
    frame-to-frame |diff| over bright pixels): 2.83 (v3) vs 0.57 (v2) 8-bit units, including
    the same camera orbit rate. Structures convect ~0.35-0.75 mm (2-4 px) per frame.
  - 2048 ranks (16 nodes) were kept: 4096 ranks would need 32 nodes in one job and a new
    decomposition (65 min serial), and at ~30k cells/rank the scaling is already poor.

**Look development** (contact sheets in `v2/tests/`; details in the scene README):
- Linear EXR renders (OCIO "raw" config) were graded offline with oiiotool (`grade.sh`), comparing
  Standard, AgX, AgX Punchy and Filmic + Medium High Contrast at several exposures.
  **Filmic MHC at +1.5 stops** gave the most fire-like colours. Standard/AgX at the old
  emission gave the beige/brown look of 2.3. The fix was 10-20x more emission and a
  saturated, blackbody colour ramp.
- Flame: blackbody front `w = (4 b (1-b))^25` (power shaping gives crisp sheets; power 3
  gives an over-exposed slab), emission colour = blackbody(1000..3000 K from w), black
  absorption, plus a faint 1300 K glow of the hot products from T. Grid T also masks
  inactive voxels, which replaces the background-1 copy of b in 2.3 (no file conversion needed).
- Vortices: Q volume (3e5..1.2e7) coloured by |U| with a cool ramp, lit by a key light and
  a strong rim light (sun lamps).
- Combined: both closures added; the vortices are semi-transparent inside the flame.
- Camera: eased orbit from a wide 3/4 view (az 100, el 22, 0.30 m) to a close 3/4 view (az 135,
  el 33, 0.245 m). The background is a dark navy gradient.
- 1920x1080, 64 spp + OpenImageDenoise (CPU). OIDN works in the CPU build. With the denoiser,
  16-128 spp look the same; seed-to-seed noise is 0.8/255. Flicker check: 60-frame previews at
  960x540 (`tests/preview_*.mp4`).
- Pitfall: CyclesPhi colour sockets need 4 values. A 3-value light `strength` is ignored
  silently: a "Wrong number of values" line appears in the log, but the light stays dark.

**Rendering** (`render_worker.sh`: a dynamic queue with an atomic `mkdir` claim per (frame, shot);
workers wait for complete VDBs and can join at any time; resumable):
- v2: 5 nodes (cn651-655) in follow mode during the run. After the solver ended, 16 more
  nodes (cn631-646) and 6 nodes of job 5275975 (cn524-529) joined.
  - 780 frames, 22:00-22:52.
  - Mean time per 1080p frame: flame 52 s, vortex 45 s, combined 96 s, including ~15 s
    to load 2-4 grids of 0.9 GB.
- v3: follow mode on cn651-655 + cn524-529 (11 nodes); this keeps up with one VDB every
  ~71 s.

**Outputs**:
- v2 (static-looking, kept for reference):
  - `v2/pitz_v2_{flame,vortex,combined}.mp4` (260 frames, 30 fps, CRF 18);
  - `v2/pitz_v2_contact_combined.png`, `v2/pitz_v2_contact_shots.png`;
  - frames in `v2/<shot>/`; the old ramp-look frames are in `v2/tests/v2a_ramp_look/`.
- v3: see 2.6.

### 2.6 v3 run and final animations
- **Run** (2026-10-26 22:53 to 10-27 04:47), log `logs_vis/log.mesio.v3`:
  - 15000 steps, t = 0.096501 -> 0.104001;
  - 21287 s wall, ExecutionTime 20591 s = 1.37 s/step;
  - Courant max ~0.3;
  - 300 exports, total 373 s (1.24 s per export, 1.8 % overhead);
  - `VDB_v3/pitz_193050..208000.vdb`, ~270 GB.
- **Rendering**: follow mode on cn651-655 + cn524-529 (11 nodes). It kept up with the
  solver: the last frame was ready 2 min after `End`, and no batch nodes were needed.
  - Mean time per 1080p frame (64 spp + OIDN): flame 52.5 s, vortex 43.2 s, combined 96.4 s.
- **Motion and flicker** over all 300 frames (`flicker.py`, 8-bit units, bright pixels):

  | Shot | mean \|d1\| (v3) | mean \|d2\| (v3) | mean \|d1\| (v2) |
  |---|---|---|---|
  | flame | 4.05 | 2.80 | 0.57 |
  | vortex | 6.79 | 4.56 | — |
  | combined | 4.96 | 3.39 | — |

  The motion is clearly visible, and |d2| < |d1| means it is smooth (no flicker).
- **Final outputs** (`$S/renders/pitzDaily3D/v3/`):
  - **`pitz_v3_flame.mp4`**, **`pitz_v3_vortex.mp4`**, **`pitz_v3_combined.mp4`**: 300 frames,
    30 fps (10 s), 1920x1080, H.264 CRF 18, yuv420p, 1.7-2.7 Mbit/s;
  - `pitz_v3_contact_combined.png`: 4 key frames of the combined shot;
  - `pitz_v3_contact_shots.png`: 3 shots x start/middle/end;
  - frames in `v3/<shot>/pitz_<idx>.png`, scenes in `v3/<shot>/scene/`;
  - best stills: `v3/combined/pitz_203000.png`, `v3/flame/pitz_208000.png`,
    `v3/vortex/pitz_200500.png`.
- Reproduce:
  - scenes: `VER=v3 FIRST=193050 STEP=50 NF=300 bash scripts/vis/v2/make_v2_scenes.sh` (on a compute node);
  - rendering: one `VER=v3 FIRST=193050 STEP=50 NF=300 render_worker.sh <log> 64 1920x1080 combined flame vortex` per node;
  - assembly: `scripts/vis/v2/finish_v3.sh`.
- Case state: `system/controlDict` = `controlDict.v3`. No restart was written
  (vdbOnly), so the latest restart is still `processor*/0.096501`.


## 3. cavity3D 8M (icoFoam, 512 ranks on cn647-cn650): start-up demo

Case `$S/runs/cavity3D/8M`: start from rest (`processor*/0`), t = 0..1 (1000 steps).
`system/functionsVis` has `Q1` and `mesioVDB1` (`fields (U p Q)`, `density 200` = 200^3
voxels, an export every 20 steps). `system/controlDict.startup` holds the run settings;
`controlDict.before_vis` is the original.

- With the old Mesio it crashed at the first export (1.5).
- With the fixed Mesio (`ofexec_vis_mesiodev.sh`, log `logs_vis/log.icoFoam.startup_dev1`):
  - 50 exports, 64-71 MB each, `VDB_startup/`;
  - export 2.1 s (first 4.1 s, write 1.8 s), setup 1.6 s;
  - 413 s wall, 0.40 s/step including exports.
- Two further repro runs (`MESIO_VDB_WRITER=single`, endTime 0.2): both clean
  (`log.icoFoam.repro_dev{2,3}`).
- CyclesPhi: |U| 0.005..0.3 turbo volume, 1280x720, 64 spp, 7 s/frame, 50 frames on 5 nodes in 107 s.
  Output in `$S/renders/cavity3D/U_mag_startup/` and **`$S/renders/cavity3D/U_mag_startup.mp4`**.
  Momentum diffusing down from the lid; soft, abstract look.
