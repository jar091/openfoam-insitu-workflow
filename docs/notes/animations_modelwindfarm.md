# Animations: MB12 model wind farm LES (OpenFOAM v2606 + mesioVDB + CyclesPhi)

Status: 2026-10-26. Jobs 5270670 (cn627-cn630, simulation + rendering) and 5275975
(cn317-cn321, rendering only). `$S = /scratch/project/eu-25-121/milanjaros/openfoam`,
`$P = /mnt/proj2/eu-25-121/milanjaros/openfoam`.

## 1. Case choice

| Candidate | Verdict |
|---|---|
| `LES/offshorewindpark` (35 NREL turbines, actuator lines) | Needs the external `turbinesFoam` fork compiled against v2606 (+ dynamic-code issues per README) and a long ABL spin-up (5000 steps of 0.5 s). Not feasible in ~2 h. |
| **`LES/modelwindfarm/windfarmmodel`** (MB12, Wu & Porte-Agel 2013) | 30 rotorDisk (actuator-disc) turbines in 10 x 3 rows, built-in `rotorDisk` fvOption, `blockMesh` 7.56M hex, synthetic DFM inflow. Everything is in the repo. **Chosen.** |

Domain 10.8 x 1.8 x 0.87 m (648 x 108 x 108 cells, 16.7 x 16.7 x 8 mm), D = 0.15 m, hub 0.125 m,
U_hub = 2.6 m/s, rotors at x = 3.0 + 0.75 i, y = 0.3 / 0.9 / 1.5 m.

## 2. Setup on v2606 (case `$S/runs/modelwindfarm/case`)

Copied with `rsync -aL` from `src/hpc/.../modelwindfarm/windfarmmodel` (symlinks to `common/`
resolved, `validation/` not copied). Changes in the copy:

* `system/decomposeParDict`: 512 subdomains, scotch (max 15,148 cells/rank, +2.6 %).
* `system/controlDict`: spin-up / production versions (below); `deltaT 0.002` instead of 0.001
  (Courant mean 0.35-0.37, max 0.55-0.68).
* The precursor `windtunnel_rough` (same domain, 5 s, then `mapFields`) was skipped: the run
  starts from the uniform `U = (3 0 0)` of `0.orig` and the turbulent DFM inflow
  (`turbulentDigitalFilterInlet`) fills the domain during the spin-up.
* v2606 compatibility: no dictionary changes were needed. The BC still accepts the case's entries
  (`variant` and `continuous` are legacy and ignored; v2606 defaults: digital filter, Gaussian
  kernel, `fsm false`). `rotorDisk` unchanged.
* **mesioVDB + FPE trap**: the first export crashed with SIGFPE in Mesio
  (`espreso::mesh::computeVolumeIndices` inside `MESIOInSituCommit`). OpenFOAM traps FP
  exceptions (`FOAM_SIGFPE`); the production runs below used `FOAM_SIGFPE=false` with the dev
  build; the exported grids were checked: no NaN, sane ranges (Section 4). Cause: the box
  `(2.70 0.005 0.0)` with `voxelSize 0.005` puts voxel centres exactly on mesh points (every
  third mesh plane), and Mesio's inside test divided by the zero distance (not specific to
  ranks outside the box). **Fixed in the next build** (`install/mesio-next`, launcher
  `ofexec_vis_mesionext.sh`, `docs/notes/mesio_build.md` Section 10.1): reproduced on this mesh
  with 256 ranks (copy `$S/runs/mesio_fix/windfarm256`, 10 steps from t = 0, exports every
  5 steps): dev with `FOAM_SIGFPE=true` stops with SIGFPE, next runs with trapping enabled and
  writes voxel-identical grids (52.4 M voxels; setup 1.1 s instead of 2.9 s). New runs:
  `LAUNCHER=ofexec_vis_mesionext.sh bash run_par.sh <tag> pimpleFoam` without `FOAM_SIGFPE=false`.

Scripts in the case: `run_pre.sh` (serial blockMesh 32 s + decomposePar 99 s on cn627),
`run_par.sh <tag> <app> [args]` (512 ranks on cn[627-630], `UCX_TLS=ud,sm,self`,
`LAUNCHER=ofexec_vis_mesiodev.sh` for mesioVDB runs). Then `renumberMesh -overwrite` and
`topoSet` (30 `cylinderToCell` sets) in parallel.

```bash
cd $S/runs/modelwindfarm/case
bash run_pre.sh                                  # (srun -N1 -n1 -c 128 -w cn627)
bash run_par.sh pre renumberMesh -overwrite
bash run_par.sh pre topoSet
bash run_par.sh spinup pimpleFoam                # controlDict: endTime 4, writeInterval 1, purgeWrite 1
sed 's/ENDTIME/7/' system/controlDict.prod.tmpl > system/controlDict        # run 1 (functionsVis: every 5 steps, "VDB")
FOAM_SIGFPE=false LAUNCHER=ofexec_vis_mesiodev.sh bash run_par.sh prod pimpleFoam
sed 's/ENDTIME/13/' system/controlDict.prod.tmpl > system/controlDict       # run 2 (every 15 steps, "VDB_dt003")
FOAM_SIGFPE=false LAUNCHER=ofexec_vis_mesiodev.sh bash run_par.sh prod2 pimpleFoam
```

## 3. Runs and timings (512 ranks, cn627-cn630)

| Run | Steps | Wall | s/step | Notes |
|---|---|---|---|---|
| Spin-up t = 0 -> 4 s | 2000 | 646 s (Execution 617 s) | 0.31 | ~1 flow-through at U_hub; wakes of all 10 rows developed. Restart `processor*/4` (the only written time). |
| mesioVDB test (`mtest2`) | 10 | 20 s | - | 2 exports, setup 2.48 s (`VDB_test/`) |
| Run 1 t = 4 -> 7 s, export every 5 steps (0.01 s) | 1500 | 744 s (Execution 603 s) | 0.22 solver + 0.18 export | 300 VDBs in `VDB/` (2005..3500), export overhead 80 % |
| **Run 2** t = 4 -> 13 s, export every 15 steps (0.03 s) | 4500 | 1618 s (Execution 1460 s) | 0.265 solver + 0.06 export | **300 VDBs in `VDB_dt003/` (2010..6495), export overhead 23 %** |

Both runs start from `processor*/4` (vdbOnly, nothing else written). Export settings
(`system/functionsVis`, run 1 copy in `functionsVis.prod_dt001`, controlDict copies `controlDict.prod_dt001`):
`Q1` and `vorticity1` function objects (at the export cadence, `writeControl none`), `mesioVDB1` with
`fields (U Q vorticity)`, `box (2.70 0.005 0.0) (10.79 1.795 0.45)`, `voxelSize 0.005`
(1619 x 359 x 91 = **52.4M voxels**, 3 grids), `writer parallel`, `blosc`, `outputPolicy vdbOnly`.

* Export: 0.89-0.90 s mean (min 0.62, median 0.86-0.89, max 1.24-1.29 s) in both runs; file write
  0.54-1.18 s (median 0.76); setup 2.48 s once; 268-269 s for 300 exports. 538 MB per file,
  158 GB per run.
* Why run 2: in run 1 the flow moves 2.6 cm per frame = 0.32 % of the 8.1 m visualised farm
  length (convective time 8.1 m / 2.6 m/s = 3.1 s), i.e. the 300 frames cover 3 s = 0.96
  flow-through; the motion looks slow (cf. the pitzDaily3D lesson). Run 2 exports every 0.03 s:
  7.8 cm per frame = **0.96 % of the region per frame, 9 s = 2.9 flow-throughs** over the clip.
  Consecutive frames still overlap well (largest wake structures persist over 3-4 frames).
  Run 2 renders were started in follow mode on cn319-cn321 while the solver ran.

## 4. Grid statistics (frame 2010; `$S/renders/modelwindfarm/tmp/wf_stats.py`)

U_mag 1/50/99 %: 1.15 / 2.74 / 3.28 m/s; inflow profile at x = 2.75 m follows the log-law fit
of the inlet UMean `U = 0.3053 ln z + 3.179` within 2 % above z = 0.05 m (1.56 vs 1.77 m/s at 1 cm).
Q 99 / 99.9 % / max: 211 / 483 / 2600 1/s^2 (3.9 % of voxels above 100). vorticity_mag 99 %:
145 1/s (dominated by the floor and side-wall boundary layers). No NaN.

## 5. Scene and rendering

Scene, generator and full shader description: `data/cyclesphi/scenes/modelwindfarm/README.md`.
Three looks: **wake** (velocity deficit relative to the inflow log law, blue-white forward-scattering
volume), **vortex** (Q tubes, wake-gated, amber-to-white emission coloured by vorticity),
**combined** (both closures added). Turbine meshes (towers, nacelles, 30 instanced 3-blade rotors
from the rotorDisk blade table), sea ground, sky gradient, warm sun, slow dolly camera, OIDN.

Look development: ~60 test renders (contact sheets `$S/renders/modelwindfarm/tests/v*/contact*.png`).
Key findings:

* Volume ray marching (`volume_ray_marching true`) cost 180-250 s per 1080p frame (32 spp);
  null scattering (`false`) gives the same image in 10-22 s (64 spp). All final renders use it.
* Lmod in every render start took up to 4 min on loaded nodes: the renderer environment is
  sourced from a plain dump `$S/renders/modelwindfarm/env_cyclesphi_ffmpeg.sh`
  (env_cyclesphi.sh + FFmpeg module, `export -p`).
* OCIO `config_standard.ocio` (view "standard") for vivid colours; filmic/AgX greyed the scene.
* Mesh positions in the CyclesPhi `.bin` are packed float3 (12 B), not 16 B like colour arrays.
* A vorticity-driven opacity shows the wind-tunnel side-wall sheets; Q with a wake gate is cleaner.

Final renders (1920x1080, OIDN, OCIO standard): `render_series.sh` workers with a shared claim queue,
one `cycles` process (128 threads) per node. Run 1: cn627-cn630 + cn317-cn321 (launchers
`$S/renders/modelwindfarm/run_final.sh`, `run_final_extra.sh`). Run 2: follow mode on cn319-cn321
(job 5275975) while the solver ran, cn627-cn630 joined after the solver ended
(`run_final_dt003.sh <job> <nodes...>`).

| Look | spp | s/frame (mean / max, one node) | Run 2 wall for 300 frames |
|---|---|---|---|
| combined | 64 | 23.0 / 28.7 | 22:52-23:24 (follow mode, 3 nodes until 23:18, then 7) |
| wake | 48 | 13.2 / 14.0 | 23:24-23:33 (7 nodes) |
| vortex | 48 | 15.1 / 16.4 | 23:33-23:44 (7 nodes) |

Per frame: ~3 s scene load (538 MB VDB, 3 grids) + path tracing + OIDN. Run 1 had identical timings
(combined 22.9, wake 13.3, vortex 15.1 s/frame; 300 combined frames in 15 min on 4-9 nodes).

MP4s (`data/cyclesphi/scenes/modelwindfarm/finish_movies.sh`: H.264, 30 fps, CRF 18, yuv420p,
`-preset slow`, faststart; 300 frames = 10 s each):

| Movie | Physical time | Size |
|---|---|---|
| **`$S/renders/modelwindfarm/modelwindfarm_combined_dt003.mp4`** | 9 s (2.9 flow-throughs) | 11 MB |
| **`$S/renders/modelwindfarm/modelwindfarm_wake_dt003.mp4`** | 9 s | 8.0 MB |
| **`$S/renders/modelwindfarm/modelwindfarm_vortex_dt003.mp4`** | 9 s | 11 MB |
| `modelwindfarm_{combined,wake,vortex}_dt001.mp4` (run 1) | 3 s (0.96 flow-through, slower motion) | 6-9 MB |

Contact sheets (frames 1/100/200/300 of the combined look, 2x2 at 960x540):
`modelwindfarm_contact_sheet_dt003.png`, `modelwindfarm_contact_sheet_dt001.png`.

Best stills: `$S/renders/modelwindfarm/combined_dt003/wf_005010.png`,
`wake_dt003/wf_006495.png`, `vortex_dt003/wf_006495.png`.

## 6. Paths

| What | Path |
|---|---|
| Case, logs, scripts | `$S/runs/modelwindfarm/case` |
| VDB series | run 2: `$S/runs/modelwindfarm/case/VDB_dt003/wf_*.vdb`, run 1: `.../VDB/wf_*.vdb` (300 x 538 MB = 158 GB each; delete when no longer needed) |
| Frames | `$S/renders/modelwindfarm/{combined,wake,vortex}_dt003/wf_*.png` (run 2), `{combined,wake,vortex}/` (run 1); per-frame scene XMLs in `scene/`, logs in `log/` |
| Movies, contact sheets | `$S/renders/modelwindfarm/modelwindfarm_*.mp4`, `modelwindfarm_contact_sheet_*.png` |
| Look-dev tests, preview | `$S/renders/modelwindfarm/tests/`, `$S/renders/modelwindfarm/preview_combined/` |
| Scene + generator | `$P/data/cyclesphi/scenes/modelwindfarm/` |
