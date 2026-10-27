# DLRCJH combustor animations (XiFoam + mesioVDB + CyclesPhi)

Status: 2026-10-26/27. Jobs 5270670 (cn647-cn650 for the solver runs; cn627-cn630 and
cn647-cn650 later for rendering) and 5275975 (cn309-cn316). Tools: OpenFOAM v2606, mesioVDB
dev build (`writer distributed`), CyclesPhi CPU build.
All data on scratch: `$S = /scratch/project/eu-25-121/milanjaros/openfoam`. Sources and
scenes are in the workspace: `$P = /mnt/proj2/eu-25-121/milanjaros/openfoam`.

## 0. Results

| What | Path (`$S/renders/DLRCJH/`) |
|---|---|
| Flame (main, 3M dynamic run, 225 frames, 1080p, 30 fps, 7.5 s) | `DLRCJH_flame.mp4` |
| Vortices (Q coloured by U_mag) | `DLRCJH_vortices.mp4` |
| Combined (flame + vortices) | `DLRCJH_combined.mp4` |
| Contact sheet, 4 frames of the combined look | `DLRCJH_contact_sheet.png` |
| Bonus: 24M high-resolution slow motion (1.08 ms, flame + combined) | `DLRCJH_24M_slowmo_{flame,combined}.mp4` |
| PNG frames | `dyn3M/{flame,vortex,combined}/dlr3M_<timeIndex>.png`, `hires24M/{flame,combined}/dlrcjh_<timeIndex>.png` |
| Best stills | `best/combined_24M_000016.png`, `best/flame_24M_000280.png`, `best/vortices_3M_001600.png`, `best/combined_3M_006000.png` |

Scene, shaders and README: `$P/data/cyclesphi/scenes/DLRCJH/` (`make_dlrcjh_scene.py`,
`looks.sh`, templates `{flame,vortex,combined}.xml` + `.xml.bin`, `README.md` with the node graphs).

## 1. Case setup

* Source: `src/hpc/combustion/XiFoam/DLRCJH/run/{24M,3M}/fixedTol`, copied with `cp -RL` to
  `$S/runs/DLRCJH/{24M,3M}`. Symlinks are resolved and `src/hpc` is untouched.
* Restart data is the developed flame from DaRUS (doi:10.18419/darus-3699). It was
  downloaded on a compute node with `curl https://darus.uni-stuttgart.de/api/access/datafile/<id>`
  into `$S/runs/downloads/DLRCJH/`; `dataset.json` holds the file list:
  * 24M: `24M_polyMesh.tar.bz2` (0.9 GB) and `24M_restartFields.tar.bz2` (6.0 GB);
  * 3M: `3M_polyMesh.tar.bz2` (0.1 GB) and `3M_restartFields.tar.bz2` (0.76 GB).

  All four files downloaded in ~2 min.
* Extraction uses serial bzip2 (no lbzip2/pbzip2 on Karolina): 3M 3 min, 24M mesh 3 min,
  24M fields 16 min. The tarballs give `constant/polyMesh` and `0/`. The fields are ASCII
  and include the old-time `*_0` and `ddt0(...)` fields, so the CrankNicolson 0.7 restart is
  exact. The restart time is named `0`.
* Cells: 24M = 24,362,150; 3M = 3,024,488.
* v2606 compatibility: **no case changes were needed**. Both fixedTol setups ran unchanged.
* Changes made in the copies:
  * `system/decomposeParDict`: 512 ranks, multiLevel scotch `(4 2 64)`. The originals are
    kept as `*.orig`.
  * `system/controlDict`:
    * `startFrom latestTime`;
    * `writeControl timeStep; writeInterval 100000000; purgeWrite 1; writeFormat binary`
      (no field output; the `vdbOnly` audit passes);
    * `functions { #include "functionsVis" }`. The `fieldAverage` object of the benchmark
      is removed.

    The run versions are saved in `logs/controlDict.{prod,dyn}`.
  * `system/functionsVis`: `Q1` (Q in memory only, `writeControl none`) followed by `mesioVDB1`.
* Preparation timings:
  * 24M `decomposePar` (serial): 1355 s;
  * 3M `decomposePar` to 512: 443 s;
  * `renumberMesh -overwrite -parallel`: ~60 s.
* CAD surface for the wall mesh: `mesh/common/triSurface.tar.xz` (`DLRCJH.obj`, mm, with
  patch groups), extracted to `$S/runs/DLRCJH/geometry/`.

## 2. Runs and mesioVDB export

Both runs use the same export box `(-0.005 -0.0475 -0.0475) (0.505 0.0475 0.0475)`. It
covers the chamber from 5 mm upstream of the front plate (nozzle and pilot exits) to
x = 505 mm, over the full 95 x 95 mm cross-section. The flame brush, measured with
`scripts/vis/dlrcjh/vdb_profile.py`, ends at x ≈ 420-480 mm. Grids: `T b U_mag Q`.

Launch: `bash $S/runs/DLRCJH/<case>/run_xifoam.sh <tag> [renumber]`. This calls
```
UCX_TLS=ud,sm,self srun --jobid=<job> --overlap --mpi=pmix --kill-on-bad-exit=1 -N4 -w <4 nodes> \
  --ntasks-per-node=128 --cpu-bind=cores bash $P/scripts/cases/ofexec_vis_mesiodev.sh <case> XiFoam -parallel
```

| | 24M "slow motion" (`runs/DLRCJH/24M`) | 3M "dynamic" (main, `runs/DLRCJH/3M`) |
|---|---|---|
| Nodes / ranks | cn647-650, 512 | cn309-312 (job 5275975), 512 |
| deltaT, steps | 6e-7 s, 1800 | 1.4e-6 s, 9000 |
| Export every | 8 steps = 4.8 us | 40 steps = 56 us |
| Physical time | 1.08 ms (~0.2 flow-through) | 12.6 ms (~2 flow-throughs) |
| Jet (113 m/s) motion per frame | 0.5 mm (0.1 % of the region) | 6 mm (1.3 %) |
| Voxels (density) | 1280 x 239 x 239 = 72.5 M active, h = 0.40 mm | 1024 x 191 x 191 = 37.1 M, h = 0.50 mm |
| VDB file | 0.96 GB, 211 GB total (`24M/VDB/dlrcjh_<idx>.vdb`) | 0.48 GB, 107 GB total (`3M/VDB_dyn/dlr3M_<idx>.vdb`) |
| Solver step (no export) | 2.4 s (median) | 0.21 s (median) |
| Export time | 2.88 s mean (2.2-6.4 s; file write 1.4-5.3 s) | 1.18 s mean (0.9-2.5 s) |
| Context setup (first export) | 4.1 s | 2.5 s |
| Export overhead | 648 s of 5070 s = 15 % (2.88 s per 8 x 2.4 s) | 265 s of 2311 s = 13 % |
| Wall (ClockTime) | 5070 s (84.5 min) | 2311 s (38.5 min) |
| Log | `24M/logs/log.XiFoam.prod` | `3M/logs/log.XiFoam.dyn` |

* The distributed writer at 72.5 M voxels x 4 grids on 4 nodes costs 2-6 s per export. The
  file write itself (1 GB, ~0.3-0.7 GB/s on `/scratch`) dominates. At 37 M voxels it costs
  ~1 s, as expected.
* **Lesson (motion):** the 24M series was planned first, with an export every 8 steps. The
  frames were then only 4.8 us apart, so the whole series covers 1.08 ms, about 0.2
  flow-throughs of the 0.45 m flame region. The jet moves 0.5 mm per frame, which looks
  nearly static (the same problem as pitzDaily3D). The 24M time step is limited by the
  Courant number in the pilot pipes (Co 1.5). Reaching 1-2 % of the region per frame would
  need ~100 steps per frame (~11 h on 4 nodes).

  The main animations therefore use the 3M mesh (dt 1.4e-6, 0.21 s/step on 512 ranks) with
  an export every 40 steps. That gives 6 mm of jet motion per frame and ~2 flow-throughs in
  225 frames. The flame length and the shed flame pockets change visibly. The mean
  frame-to-frame luma difference of the flame MP4 is 1.9/255.

  Before rendering, check motion with: physical time per frame x convective velocity vs.
  region size, and a low-res preview.
* After `End`, the 24M run aborted in `MPI_Finalize` with a UCX-UD endpoint timeout
  (`ud_ep.c:296 unhandled timeout error`, srun rc 143). All 225 exports were complete
  (`mesioVDB1 end: 225 export(s)`), so the results are unaffected.
* The 24M validation run (36 steps, `logs/log.XiFoam.validate`, VDBs in `VDB_validate/`)
  ran cleanly on v2606.

## 3. Scene and shaders

See `$P/data/cyclesphi/scenes/DLRCJH/README.md` for the node graphs. Summary:

* **Flame:** emission-only, smoke-free. Colour comes from a blackbody-like LUT of T
  (700-2100 K: ember red -> orange -> amber -> yellow-white). Strength =
  `front(b) * mask(T) + glow * heat(T)`, where:
  * `front(b)` is a window peaked at b = 0.5;
  * `mask(T)` (950-1250 K) hides the unburnt cores and the box faces;
  * `heat(T)` ~ T^4.

  A thin warm absorption gives depth. The physical `blackbody` node is available as
  `--color-mode blackbody`; it was tested but looked more washed out.
* **Vortices:** a Q-criterion volume. The Q map range is 5e7-1e9 1/s^2 on 3M and
  1.5e8-3e9 on 24M (Q is ~3x larger on the finer mesh), followed by power 0.7 and a
  thresholded opacity LUT, which gives crisp tubes. Colour comes from U_mag (10-140 m/s):
  indigo -> blue -> azure -> cyan -> ice white. Mostly self-emissive, with some scattering.
* **Combined:** `add_closure` of both volumes in one shader on one volume object. The
  vortices use a lower density and higher emission so that the flame remains visible.
* **Walls:** a cut-away triangle mesh from the case CAD: back wall and floor as dark
  ceramic, front plate with the nozzle and pilot openings, and metal pilot tubes and nozzle
  stub. The flame lights the walls through 1 bounce.
* **Camera:** a slow eased orbit over the 225 frames, from az 18°, el 12°, d 0.52 m to
  az 42°, el 24°, d 0.56 m, around x ≈ 0.24 m. The flame fills ~80-85 % of the frame width.
* **Render settings:** 1920x1080, 32 spp, OIDN (accurate prefilter, high quality),
  `volume_step_rate 2` (0.8-1 mm steps), max 1 bounce, Standard sRGB view
  (`config_standard.ocio`).
* **Findings on the CyclesPhi XML format:**
  * Mesh vertices are an `ATTR_STD_POSITION` attribute `P` with a byte buffer; there is no
    `verts` socket, and the reader segfaults if `P` is missing.
  * Closure output sockets are case sensitive (`BSDF`).
  * Ramp strings contain `;`, so `looks.sh` strings must be expanded with `eval`.

## 4. Rendering

Iteration workflow:
* `scripts/vis/dlrcjh/variants.sh` renders 4-8 look/camera variants of one VDB.
* `scripts/vis/v2/tile.sh` builds contact sheets.
* Test renders: `$S/renders/DLRCJH/tests/` (r1-r6 on 3M test data, c1 and hd24 on 24M, dyn1
  and the low-res `preview_dyn.mp4` motion check on 3M).

Production renders use a work queue, so nodes can be added while it runs:
* `scripts/vis/dlrcjh/queue_gen.sh <vdb_dir> <solver_log> <out_root> <looks>` (login-node
  driver) writes one XML per new VDB and look. The orbit camera comes from the time index.
  When the solver ends, it touches `ALLGEN`.
* `scripts/vis/dlrcjh/worker.sh <out_root> 1920x1080 32 <looks>` runs one per node via
  `srun`. It claims frames with an atomic `mkdir <out_root>/claims/<look>_<frame>`,
  renders, and exits when `ALLGEN` exists and no work is left.
* The 3M frames were rendered in follow mode during the solver run, first on cn313-316,
  then on cn309-312 once the solver finished, then on cn647-650 and cn627-630.
* `scripts/vis/dlrcjh/render_look.sh` and `follow_render.sh` are the earlier static
  round-robin variants. Their drawback: nodes freed during a round stay idle.
* MP4s: `scripts/vis/make_mp4.sh <dir> <out.mp4> 30 'dlr3M_*[0-9].png'` (H.264, CRF 18,
  yuv420p, slow preset). Use a pattern that excludes the workers' `*.tmp.png` files.

### Render timings (1920x1080, 32 spp + OIDN, 128 threads per node, one frame per node)

| Look | 3M series: s/frame mean (min-max) | 24M bonus: s/frame mean |
|---|---|---|
| flame | 56.8 (45-96) | 78.4 |
| vortex | 54.5 (43-95) | - |
| combined | 97.0 (61-181) | 128.7 |

* The spread comes from the nodes (cn3xx vs cn6xx) and from scratch I/O contention when
  16 nodes read 0.5-1 GB VDBs at once.
* Fixed cost per frame (VDB load, BVH, OIDN) is ~5 s. Each sample at 1080p costs ~3.5 s
  (24M). 3 bounces (walls lit by indirect volume emission) doubled the cost, so 1 bounce
  is used.
* 3M series: 675 frames, 46,900 node-s (13 node-h). Wall time 22:57-00:22 (85 min) on 4,
  then 8, 12 and 16 nodes, in follow mode during the solver run.
* 24M bonus (flame + combined, 450 frames): 46,600 node-s, 00:22-01:10 on 16 nodes.
* MP4 assembly: ~1 min per look on one node. Sizes: flame 3.0 MB, vortices 8.2 MB,
  combined 7.7 MB, 24M slow motion 1.7 MB (flame) and 4.7 MB (combined). The dark, denoised
  frames compress well at CRF 18.

## 5. Reproduce

```bash
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
bash $S/runs/DLRCJH/3M/run_xifoam.sh dyn renumber        # solver + VDB export (38 min)
FIRST=40 STEP=40 NFRAMES=225 EXTRA="--qrange 5e7 1e9" GEN_NODE=5275975/cn316 \
  bash $P/scripts/vis/dlrcjh/queue_gen.sh $S/runs/DLRCJH/3M/VDB_dyn $S/runs/DLRCJH/3M/logs/log.XiFoam.dyn \
  $S/renders/DLRCJH/dyn3M flame vortex combined &
for n in cn313 cn314 cn315 cn316; do srun --jobid=5275975 --overlap -N1 -n1 -c 128 -w $n \
  bash $P/scripts/vis/dlrcjh/worker.sh $S/renders/DLRCJH/dyn3M 1920x1080 32 flame vortex combined & done
```
