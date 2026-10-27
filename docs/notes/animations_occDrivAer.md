# occDrivAer (65M, simpleFoam RANS) animations: OpenFOAM v2606 + mesioVDB + CyclesPhi

Status: 2026-10-27, Slurm job 5275975, nodes cn001-cn005 (5 x 128 cores, Karolina CPU).
OpenFOAM v2606, mesioVDB dev build (`writer parallel`), CyclesPhi CPU build.
All data on scratch `$S = /scratch/project/eu-25-121/milanjaros/openfoam`; sources/scenes in the
workspace `$P = /mnt/proj2/eu-25-121/milanjaros/openfoam`. Scene and shader graphs:
`data/cyclesphi/scenes/occDrivAer/README.md`.

## Results

`$S/renders/occDrivAer/`:

| Output | Content |
|---|---|
| **`occDrivAer_orbit_1080p.mp4`** | 360 frames, 30 fps (12 s), 1920x1080, H.264 CRF 18 yuv420p, 4.0 MB: eased 360 deg orbit around the converged flow (hi-res 155M-voxel export of iteration 1001) |
| **`occDrivAer_converging_1080p.mp4`** | "solution converging": 45 in-situ exports (iterations 5 ... 1000, log-spaced), fixed rear 3/4 view, `ITERATION n` counter, 6 exports/s cross-faded to 30 fps (ffmpeg `framerate` blend) + 2 s hold, 7.5 s, 2.3 MB |
| `occDrivAer_orbit_contact.png` | 4-frame contact sheet of the orbit (frames 30, 120, 170, 255) |
| `stills/occDrivAer_front34_f0060.png`, `stills/occDrivAer_side_wake_f0120.png`, `stills/occDrivAer_rear34_f0255.png` | best stills (orbit frames 60, 120, 255) |
| `orbit/png/`, `orbit/xml/` | orbit frames and their per-frame scenes |
| `converge/png/`, `converge/labeled/`, `converge/xml/`, `converge/preview*` | converging-sequence frames (raw / with counter), scenes, 960x540 preview + contact sheet |
| `tests/` | look development (Section 3) |

Data: `$S/runs/occDrivAer/case/VDB_conv/drivaer_<it>.vdb` (88 exports, 20 GB),
`VDB_hires/drivaer_001001.vdb` (1.82 GB), `$S/runs/occDrivAer/geometry/` (car OBJ, car mesh include,
`walld_h014.vdb`, `walld_h007.vdb`), restart `processor*/1000` (and `300`).


## 1. Case setup

* Source `src/hpc/incompressible/simpleFoam/occDrivAerStaticMesh` copied with `cp -RL` to
  `$S/runs/occDrivAer/case` (`src/hpc` untouched).
* Mesh: Zenodo record 15012221, `polyMesh_65M.tar.gz` (3.24 GB, md5 checked), downloaded with
  curl on cn005 in 79 s into `$S/runs/downloads/occDrivAer/`, extracted with `pigz | tar` into
  `case/constant/polyMesh` in 44 s. Binary, 65,334,765 cells, 73.2M points, 203M faces,
  51 patches (47 car wall patches).
* Changes in the copy:
  * `system/include/caseDefinition`: `nCores 640`, `nHierarchical (16 8 5)` (hierarchical,
    102,085-102,089 cells per rank).
  * `system/fvSolution` = `fvSolution.fixedTol` (tolerance-based GAMG/smoothSolver; the case's
    RANS starting point for the software track).
  * `system/controlDict` (original in `controlDict.orig`): `endTime`/`writeInterval` per run (see 2),
    `purgeWrite 1`, functions `solverInfo`, `forceCoeffsAll` and `#include "functionsVis"`. Removed:
    the coded `FOwallClockTimeStatistics` (on-the-fly compilation), probes, `calc_cp`,
    `wallShearStress`, `fieldMinMax`.
  * `system/functionsVis` (+ `.conv`, `.hires`): `Q1`, `vorticity1`, `Cpt1` (function object
    `pressure`, `mode totalCoeff`, `pInf 0`, `UInf (38.889 0 0)`, `rho rhoInf; rhoInf 1`), all
    `writeControl none`, then `mesioVDB1` with `fields (U Cpt Q vorticity)` -> grids
    `U_mag Cpt Q vorticity_mag`, `box (-1.3 -1.5 -0.3176) (8.5 1.5 1.7)` (car + ~1 car length of
    wake), `writer parallel`, `outputPolicy standard` (forceCoeffs writes postProcessing).
* v2606 compatibility: no change needed (all dictionaries and the `libs` list load; `potentialFoam
  -initialiseUBCs`, `applyBoundaryLayer` unchanged).
* Car surface for the scene: `surfaceMeshExtract -constant -patches '("Body.*" "Closed.*" "CTRL.*"
  "Engine.*" "Exhaust.*" "Mirror.*" "Notchback.*" "OCDA.*" Powertrain "Wheel.*" "Rims.*" "Brake.*"
  "Tires.*")' $S/runs/occDrivAer/geometry/car.obj` (serial, 45 s; the regexes must be quoted inside
  the wordRes, unquoted they match literally: only `Powertrain` was extracted on the first try).
  5.8M points, 5.2M polygons, 47 groups. `make_car_mesh.py` converts it in 39 s to
  `geometry/car_mesh.xml` + `.xml.bin` (11.6M triangles, 267 MB, 7 material slots).

Scripts in the case directory: `run_decompose.sh`, `run_prep.sh`, `run_simple.sh <tag>`,
`run_hires.sh`. Launch line (as in `run_simple.sh`):
```
UCX_TLS=ud,sm,self srun --jobid=5275975 --overlap -N5 -w cn[001-005] --ntasks-per-node=128 \
    --mpi=pmix --cpu-bind=cores --kill-on-bad-exit=1 \
    bash $P/scripts/cases/ofexec_vis_mesiodev.sh $S/runs/occDrivAer/case simpleFoam -parallel \
    > logs/log.simpleFoam.<tag> 2>&1
```

| Step | Command | Time |
|---|---|---|
| decomposePar (serial, mesh only, 640 hierarchical) | `run_decompose.sh` (`decomposePar -constant -force`) | ~9 min |
| `0.orig` -> `processor*/0` | xargs -P 32 cp | < 1 s |
| renumberMesh -constant -overwrite (640 ranks) | `run_prep.sh` | 20 s |
| potentialFoam -initialiseUBCs | `run_prep.sh` | 33 s |
| applyBoundaryLayer -ybl 0.0450244 | `run_prep.sh` | 13 s |

(The prep steps run with `-noFunctionObjects`.)

## 2. Runs (simpleFoam, 640 ranks, kOmegaSST, fixedTol)

| Run | Iterations | Export | Wall | Notes |
|---|---|---|---|---|
| A `log.simpleFoam.A_0-300` | 0 -> 300 | every 5 its, 14 mm voxels (701 x 215 x 145 = 21.9M box, 19.5M active), `VDB_conv/` | 896 s | writes `processor*/300` |
| B `log.simpleFoam.B_300-1000` | 300 -> 1000 | every 25 its, same grid | 2222 s | writes `processor*/1000` |
| C `log.simpleFoam.C_hires_1001` | 1000 -> 1001 | 7 mm voxels (1401 x 429 x 289 = 174M box, **155M active**), `VDB_hires/drivaer_001001.vdb` (1.82 GB) | 59 s | no field write |

* Solver: 2.67 s per iteration without export (102k cells/rank; GAMG p 6-10 V-cycles, U 11
  sweeps). Cd 0.286 at 150, 0.267 at 1000 (reference plot of the case: ~0.27 for coarse; the
  plateau is reached after ~300 iterations). Total solver time 52 min for 1000 iterations.
* mesioVDB, 21.9M-voxel export (4 grids, 230 MB): first 2.1-3.1 s (includes the leaf plan),
  then **1.12-1.18 s mean** (fields 0.01, convert 0.43, sample 0.1-0.4, gather 0.1-2.4,
  write 0.4-0.5 s); context setup 5.9 s. Overhead: 8.4 % with an export every 5 iterations
  (run A), 1.6 % every 25 iterations (run B).
* mesioVDB, 155M-voxel export (4 grids, 1.82 GB): setup 29.6 s, export 5.6 s
  (sample 2.8, exchange 2.8, plan 1.0, file 1.6 s).
* Grid statistics (`scripts/vis/occdrivaer/vdb_stats_drivaer.py`, iteration 1000/1001, hi-res and
  low-res agree): |U| median 38.5 m/s, max 66; total pressure loss 1 - Cpt 99th pct 1.12
  (separated regions Cpt < 0), > 0.2 in 20 % of the box; Q 99th pct 6.0e3, 99.9th 9.5e4,
  max 9e7 (near walls); |omega| 99.9th 7.6e3 1/s.

### Problem: runtime change of the mesioVDB settings crashes
The first run (`logs/failed_conv1/`) was meant to change the export cadence at runtime
(`runTimeModifiable`, editing `functionsVis`). At the re-read every non-master rank aborted in
`Foam::operator>>(Istream&, boundBox&)` <- `mesioVDB::read()` with `ITstream::readRaw ... Not
implemented`: the re-read dictionary reaches the other ranks as a binary token stream, and the
`box` entry is parsed with the binary `boundBox` reader. Work-around used here: no runtime edits;
the cadence change is done by restarting (runs A/B). Fix suggestion for `mesioVDB::read()`: read
the box as two points (`dict.get<point>`-style via `ITstream` token parsing, e.g.
`boundBox(dict.lookup("box"))` on an ASCII-formatted copy) or as `List<point>`.

## 3. Scene, look development

Scene generator, shaders, lights: `data/cyclesphi/scenes/occDrivAer/` (README with the node graphs).
Look development renders: `$S/renders/occDrivAer/tests/`:

* `car0/png/` car only (graphite and clay) - checks the mesh include, normals, lights.
* `look1/sheet_rear.png`, `sheet_front.png`: 8 variants (paints graphite/silver/midnight/white/
  clay/red, wake ramps ice/teal/white, vortex ramps ember/ice/plasma/turbo). Finding: Q > 2e3
  forms an orange staircase shell around the whole car (first voxel layers outside the walls);
  the 1 - Cpt wake was a dense slab.
* `look2/sheet.png`: 6 variants with a |U| mask for Q (did not remove the shell: U is already
  25-40 m/s there), softer wake (loss 0.25..1.3, gamma 1.5, density 3).
* `look3/sheet.png`: wall-distance mask (`vdb_walldist.py`, grid `walld`): shell gone with a fade
  over 5-10 cm from the car; the A-pillar, mirror, wheel and C-pillar/trunk vortices remain.
  `q_shell_probe.py`: Q > 3e3 voxels within 1 voxel of the wall have normalised Q 2Q/|omega|^2
  of median 0.05 (in the flow 0.23).
* `hires1-3`: high-resolution frames, timing tests (below), `preview/`: 30-frame previews of the
  orbit (`preview_path.mp4`: every 12th frame; `preview_consec.mp4`: frames 150-179, 30 fps),
  `preview2/`: camera fix for the rear views (higher, target pulled towards the car).

Final look: graphite metallic clear-coat car, ice-blue total-pressure-loss wake (scattering, weak
emission), Q filaments in an ember ramp coloured by |U|, dark studio with a key softbox (12 x 6 m),
cool rim strip, front fill, floor vignette.

### Render cost (1920x1080, CPU, 128 threads, OIDN)

| Setting | s/frame |
|---|---|
| step = voxel size (7 mm), 64 spp, 6 bounces | 425-564 |
| step x3, 32 spp, 4 bounces (glossy 2, diffuse 1) | 101-198 |
| step x5, max 384 steps, 24 spp | 57-106 |
| **step x5, max 384 steps, 20 spp (production)** | 65.5 mean (49-117) |
| step x5, 16 spp | 74 (worst view) |

Scene load (1.8 GB VDB + 267 MB car mesh + BVH) is ~12-14 s of each frame.
The 16/24/32 spp crops are indistinguishable after OIDN (`tests/hires3/crop_cmp.png`).

## 4. Production renders

* Orbit: `shots.sh orbit <hires.vdb> <walld_h007.vdb> $S/renders/occDrivAer/orbit/xml 360`, then
  `scripts/vis/occdrivaer/render_all_nodes.sh standard 1920x1080 20 orbit/png orbit/xml/frame_*.xml`
  on cn001-cn005 (one `cycles` process with 128 threads per node, shared claim queue):
  **65.5 s/frame** mean (49-117 s; rear views through the long wake are the slowest),
  360 frames in 79 min wall. MP4: `scripts/vis/make_mp4.sh orbit/png occDrivAer_orbit_1080p.mp4 30 'frame_*.png'`.
  Temporal check (`scripts/vis/v2/flicker.py` on the frames): mean |d1| 1.81, |d2| 2.23 (8-bit,
  bright pixels; camera motion dominates, no denoiser flicker visible).
* Before the batch: 30-frame low-res previews (960x540, 16 spp, every 12th frame and frames
  150-179 consecutively, `tests/preview/preview_path.mp4`, `preview_consec.mp4`), which led to the
  rear-view camera fix (`--el-rear 14 --target-rear 1.2`) and the larger, dimmer key softbox
  (the windscreen was blown out in the front views).
* Converging sequence: iterations chosen log-spaced from the available exports (every 5 up to 300,
  every 25 after): 5 10 ... 60 70 75 80 85 95 105 110 120 135 145 155 170 185 200 220 240 260 285 300
  325 375 400 425 475 500 550 600 650 725 775 850 925 1000. The 960x540 preview (16 nodes, 61 s)
  was checked with `framediff.py`: every step changes 2-26 % of the pixels by > 4/255 (smallest at
  the first steps, 2.4 %; still 13-17 % at the end because the RANS wake keeps oscillating, as Cd
  does). Story: potential-flow start, A-pillar/wheel vortices grow first (it 15-40), a vortex
  burst fills the wake (60-120), then the total-pressure-loss wake develops and the vortex system
  settles (200-1000). Rendered at 1080p, 20 spp, step 2.5 x 14 mm on cn631-cn646 (job 5270670):
  49 s/frame, 45 frames in 197 s. Counter burned in with `label_frames.py` (built-in bitmap font:
  the bundled OIIO has no FreeType, the FFmpeg module no drawtext).

## 5. Timeline and node use

| Phase | Wall |
|---|---|
| download + extract | 2 min |
| decomposePar (serial) | 9 min |
| prep (renumber, potentialFoam, applyBoundaryLayer) | 1.1 min |
| failed run with runtime edit (39 its) | 2 min |
| simpleFoam A + B + C (1001 its, 89 exports) | 53 min |
| look development (3 rounds of contact sheets, hi-res tests, previews) | ~70 min (partly overlapping with run B) |
| orbit batch (5 nodes) | 79 min |
| converging sequence (preview + final, 16 nodes) | 4.5 min |

Nodes cn001-cn005 (job 5275975) throughout; cn631-cn646 (job 5270670) for the converging
sequence after they were released. The 65M case was not rerun on 2048 ranks: it had already
converged on 640 ranks when the extra nodes became available.

Look-dev renders on the solver nodes while simpleFoam runs are expensive for both: with 128
pinned MPI ranks per node a 128-thread render took 85-90 s instead of ~30 s and slowed the solver
from 2.7 to 3.2 s/iteration.

## 6. Reproduce

```bash
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
C=$S/runs/occDrivAer/case
bash $C/run_decompose.sh; bash $C/run_prep.sh
# run A: endTime 300, writeInterval 300, functionsVis cadence 5; run B: endTime 1000, cadence 25
bash $C/run_simple.sh A_0-300; bash $C/run_simple.sh B_300-1000
bash $C/run_hires.sh                         # 1 iteration, 7 mm export -> VDB_hires/
srun ... pyvdb.sh $P/scripts/vis/occdrivaer/vdb_walldist.py $C/VDB_hires/drivaer_001001.vdb $S/runs/occDrivAer/geometry/walld_h007.vdb 15
srun ... pyvdb.sh $P/scripts/vis/occdrivaer/vdb_walldist.py $C/VDB_conv/drivaer_000300.vdb $S/runs/occDrivAer/geometry/walld_h014.vdb 8
srun ... pyvdb.sh $P/data/cyclesphi/scenes/occDrivAer/make_car_mesh.py --obj $S/runs/occDrivAer/geometry/car.obj --outdir $S/runs/occDrivAer/geometry
srun ... bash $P/data/cyclesphi/scenes/occDrivAer/shots.sh orbit ... ; render_all_nodes.sh ...
EXTRA='--step-rate 2.5' shots.sh converge $S/runs/occDrivAer/geometry/walld_h014.vdb <out>/xml <vdb...>
```

