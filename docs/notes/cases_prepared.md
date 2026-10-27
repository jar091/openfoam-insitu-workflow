# Prepared OpenFOAM v2606 cases (restart-ready for visualization function objects)

Status: 2026-10-26. All cases run on Karolina inside job 5270670 with the v2606 build
(`docs/notes/openfoam_build.md`). Case data live only on scratch:
`/scratch/project/eu-25-121/milanjaros/openfoam/runs/`. Sources were copied from
`src/hpc` (unchanged) with `cp -R -L` / `rsync -aL`.

## Summary

| Case | Path (under `runs/`) | Cells | Ranks / nodes | s/step | Physical time reached | Restart time dir |
|---|---|---|---|---|---|---|
| pitzDaily3D 3M (XiFoam, validation only) | `pitzDaily3D/3M` | 3.32M | 128 / 1 (cn632) | 0.92 | 20 steps of 1e-9 s (benchmark setup) | `processor*/0` (non-initialised fields) |
| pitzDaily3D 62M (XiFoam LES flame) | `pitzDaily3D/62M` | 62.2M | 2048 / 16 (cn631-cn646) | 1.35-1.7 (1.52 avg) | t = 0.095401 s (restart 0.0932695 + 2.13 ms) | `processor*/0.095401` |
| HPC_motorbike Small (simpleFoam, kOmegaSST) | `HPC_motorbike/Small` | 8.77M | 512 / 4 (cn647-cn650) | 0.76 (default UCX) | 500 iterations | `processor*/500` |
| cavity3D 8M (icoFoam, Re=100) | `cavity3D/8M` | 8.0M | 512 / 4 (cn647-cn650) | 0.08 avg (0.2 at start) | t = 10 s (10000 steps; steady, p residual 8e-7) | `processor*/10` |

All solver output is decomposed (`processor*` directories, binary, uncollated). Each case
has an empty `case.foam` for ParaView-style readers (open with "Decomposed Case").

## Launch mechanics (important)

* **Fast launcher.** `scripts/cases/ofexec.sh <case> <app> [args]` sources
  `scripts/env_openfoam.sh` in every rank. With 128 ranks per node the Lmod
  `module purge/load` over NFS takes **~4 minutes per srun**. Use
  `scripts/cases/ofexec_fast.sh` instead: it sources a plain `export -p` dump
  (`runs/of_env_v2606.sh`, recipe in the script header) and starts in seconds.
  Regenerate the dump if `env_openfoam.sh` changes.
* **UCX transport.** OpenMPI 5.0.8 + UCX 1.19 defaults to the DC transport
  (`dc_mlx5`) between nodes. For these OpenFOAM runs it is much slower than UD:
  pitzDaily3D 62M 3.5 s/step (default) vs 1.33 s/step with `UCX_TLS=ud,sm,self`;
  cavity3D 8M 2.1 vs 0.5 s/step (GAMG). The run scripts export
  `UCX_TLS=ud,sm,self` (override by setting `UCX_TLS` before calling them).
  Raw latency test (`runs/perftest/mpibench/allred.c`, 512 ranks on 4 nodes):
  allreduce 41 us (DC) / 21 us (UD).
* Generic multi-node line (one MPI rank per srun task, PMIx):
  ```
  UCX_TLS=ud,sm,self srun --jobid=5270670 --overlap -N<n> -w <nodes> --ntasks-per-node=128 \
      --mpi=pmix --cpu-bind=cores \
      bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/cases/ofexec_fast.sh <caseDir> <app> -parallel > <caseDir>/log.<app> 2>&1
  ```
  `HOME` is set to `/scratch/project/eu-25-121/milanjaros/openfoam/fakehome` by both wrappers.
* Serial tools (blockMesh, decomposePar) run as a 1-task step, e.g.
  `srun --jobid=5270670 --overlap -N1 -n1 -c 128 -w <node> bash .../ofexec.sh <case> decomposePar`.

## 1. pitzDaily3D 62M (XiFoam) - main demo case

Path: `runs/pitzDaily3D/62M` (based on `62M/fixedTol`: physical deltaT 5e-7 s,
tolerance-based linear solvers, `crankNicolson 0.8`).

How it was prepared:
1. `run_blockMesh.sh`: `m4 -P system/blockMeshDict.m4 > system/blockMeshDict; blockMesh`
   (serial, 12 min, 71 GB RSS; blockMesh has no parallel mode). 62,205,108 cells.
2. Developed restart fields downloaded from DaRUS (doi:10.18419/darus-3744,
   `pitzDaily3D_62M_restartFields.tar.gz`, 12.8 GB, kept in
   `runs/downloads/pitzDaily3D/`). They are reconstructed ASCII fields of a run at
   **t = 0.0932695 s** (time index 186539, i.e. ~0.093 s of flame/LES development
   from ignition, combustion progress ~35%). Only the needed fields were extracted
   (U p T Tu b Xi Su St k nut alphat rho phi; old-time `*_0`/`ddt0*` and averages skipped,
   so the first restart step falls back to Euler for the old-time terms).
   They sit in the case root as `0.0932695/` (ASCII, serial).
3. `run_decompose.sh`: `decomposePar` for 2048 ranks (`multiLevel` scotch, domains
   `(16 2 64)` = nodes x sockets x cores/socket), fields written binary.
   Serial, 65 min, 40 GB RSS. Max 30,891 cells/rank (1.7% above average).
4. `bash run_xifoam.sh renumber`: `renumberMesh -overwrite -parallel` (CuthillMcKee) then XiFoam.

v2606 compatibility: no changes needed. The 3M benchmark (`3M/fixedIter`, incl. the coded
`wallClockTimeStatistics` function object) ran unchanged; 62M fixedTol dictionaries
ran unchanged (only `controlDict` and `decomposeParDict` edited, see below).

Validation: 20 steps from the restart, no warnings, Courant max 0.41, St-Courant 0.037,
p (DICPCG) 12-15 iterations. Logs in `logs_validation/`
(`log.XiFoam.validate_ucxDefault`: 3.5 s/step, `log.XiFoam.validate_ucxUD`: 1.33 s/step).

Production run: `log.XiFoam.20261026_1427`, planned 4800 steps (endTime 0.0956695).
It ran 4263 steps x 5e-7 s = 2.13 ms from t = 0.0932695 to **t = 0.095401 s** and was
stopped with `stopAt writeNow` to stay within the 2 h budget: 6617 s (1 h 50 min) clock
time on 16 nodes. Speed 1.35 s/step for the first ~2000 steps, ~1.7 s/step later
(1.52 s/step average; no change in the case, likely shared file-system/network load).
Courant max 0.29-0.41, combustion progress steady at ~35%, no warnings.
At U0 = 13.3 m/s, 2.1 ms convects the shear-layer structures ~28 mm (~14% of the
206 mm test section); the field itself was already developed from the DaRUS restart
(~0.093 s, i.e. ~4 flow-through times of test section + contraction).

`system/controlDict` (current):
```
startFrom latestTime; stopAt endTime; endTime 0.0956695; deltaT 5e-7;
writeControl runTime; writeInterval 0.0004; purgeWrite 1; writeFormat binary;
functions { }   // empty, ready for visualization function objects
```
Note: `writeControl runTime` counts intervals from the start time of the run, and the
end time is **not** written unless it is a write time; choose endTime = start + k*writeInterval.

Restart: `processor*/0.095401` (latestTime, ~14 MB/rank, ~28 GB total). Fields there:
`U p T Tu b Xi Su St k nut alphat rho phi` plus the old-time fields needed for an exact
crankNicolson restart (`*_0`, `ddt0(...)`, `ddtCorrDdt0(...)`).
Also still present (deleting directories was not permitted in this session; safe to remove):
`processor*/0.0932695` (the decomposed DaRUS start fields, ~10 GB; startFrom latestTime
ignores it), the serial ASCII copy `0.0932695/` (9.4 GB) and the empty `restart_raw/`.
The original restart is also kept as the tarball in `runs/downloads/pitzDaily3D/`.
For rendering: `T` (293 K unburnt, hot products downstream of the flame), `b` (regress variable, 1 unburnt /
0 burnt: flame front at b=0.5), `U` (shear-layer vortices; derive vorticity/Q with the
`vorticity`/`Q` function objects), `Xi`, `Su`, `St`, `k`, `p`, `rho`.

Exact launch line (what `run_xifoam.sh` executes):
```
cd /scratch/project/eu-25-121/milanjaros/openfoam/runs/pitzDaily3D/62M
UCX_TLS=ud,sm,self srun --jobid=5270670 --overlap -N16 -w cn[631-646] --ntasks-per-node=128 \
    --mpi=pmix --cpu-bind=cores \
    bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/cases/ofexec_fast.sh \
    /scratch/project/eu-25-121/milanjaros/openfoam/runs/pitzDaily3D/62M XiFoam -parallel \
    > log.XiFoam.<tag> 2>&1
```
Start-up (srun launch + reading 62M fields on 2048 ranks) takes ~15-20 s before the first step.
Memory is not an issue at 128 ranks/node (~30k cells/rank).

### pitzDaily3D 3M (validation)
Path `runs/pitzDaily3D/3M` (`3M/fixedIter`, `decomposeParDict` 128 = `(1 2 64)`).
`run_pre.sh` (m4, blockMesh, `cp -r 0_orig 0`, decomposePar), then renumberMesh +
XiFoam on cn632: 20 steps of 1e-9 s, 0.92 s/step on 128 ranks (0.91 s/step on 2x64 ranks),
log `log.XiFoam.validate`. The first run compiles the coded function object
(`dynamicCode/`, ~5 min on NFS headers). Fields are non-initialised (benchmark setup);
not intended for rendering.

## 2. HPC_motorbike Small (simpleFoam)

Path: `runs/HPC_motorbike/Small` (from `Small/v1912`).
* `mesh_pre.sh`: blockMesh (50x20x20 background) + decomposePar (512, scotch).
* Parallel snappyHexMesh on 512 ranks (cn647-cn650): `snappyHexMesh -overwrite -parallel`,
  21 min, 8,771,003 cells, final load imbalance 1%, ~50 GB per node. `log.snappyHexMesh`.
* Because the snappy decomposition was already balanced, no reconstruct/re-decompose
  was done (`mesh_post.sh` is an unused alternative). `run_solve.sh` copies `0.org` into
  each `processor*/0`, then `checkMesh -parallel` (47 skewed faces, max skewness 11.6,
  as usual for this geometry), `potentialFoam -parallel -writephi`, `simpleFoam -parallel`.
* 500 iterations in 6.7 min (0.76 s/iter, run with the default UCX transport; UD
  would likely be faster). Final residuals: p 9e-3, Ux 9e-4, k 2e-3, omega 7e-5
  (typical plateau of this unsteady wake case; not converged further).
* Restart: `processor*/500` with `U p k omega nut phi`. `processor*/0` = initial fields (U/phi overwritten by potentialFoam).
* Launch line:
  ```
  cd /scratch/project/eu-25-121/milanjaros/openfoam/runs/HPC_motorbike/Small
  UCX_TLS=ud,sm,self srun --jobid=5270670 --overlap -N4 -w cn[647-650] --ntasks-per-node=128 \
      --mpi=pmix --cpu-bind=cores \
      bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/cases/ofexec_fast.sh \
      /scratch/project/eu-25-121/milanjaros/openfoam/runs/HPC_motorbike/Small simpleFoam -parallel \
      > log.simpleFoam.<tag> 2>&1
  ```
  `controlDict`: `startFrom latestTime; endTime 500; writeInterval 100; purgeWrite 1; binary`.
  For a further run raise `endTime` (e.g. 600); each iteration is one "frame".

## 3. cavity3D 8M (icoFoam)

Path: `runs/cavity3D/8M` (from `8M/fixedIter`). 200^3 uniform hex, unit cube, lid
U = (1 0 0), nu = 0.01 (Re = 100).
* `run_pre.sh` on cn648: blockMesh + decomposePar (512, scotch, 15.6k cells/rank).
  `bash run_icofoam.sh renumber` did renumberMesh once.
* Changes vs benchmark: `deltaT 0.001` (Co mean 0.17-0.38, max ~1.97 in the lid-edge corner
  cells, stable), `endTime 10` (10 lid-driven turnover times), p solver GAMG
  (tolerance 1e-6, relTol 0.05; pFinal relTol 0) instead of fixed 116 PCG iterations,
  `writeControl runTime; writeInterval 1; purgeWrite 1; writeFormat binary`.
* Run: 0.20 s/step at the start, 0.081 s/step averaged over 10000 steps (p needs fewer
  GAMG iterations as the flow becomes steady) on 512 ranks with UD (default UCX: ~2 s/step), 14 min wall.
  Log `log.icoFoam.20261026_1428`; test logs in `old_logs/`.
* Restart: `processor*/10` with `U p phi`.
* Launch line:
  ```
  cd /scratch/project/eu-25-121/milanjaros/openfoam/runs/cavity3D/8M
  UCX_TLS=ud,sm,self srun --jobid=5270670 --overlap -N4 -w cn[647-650] --ntasks-per-node=128 \
      --mpi=pmix --cpu-bind=cores \
      bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/cases/ofexec_fast.sh \
      /scratch/project/eu-25-121/milanjaros/openfoam/runs/cavity3D/8M icoFoam -parallel \
      > log.icoFoam.<tag> 2>&1
  ```
  The flow at Re=100 is (nearly) steady; for an animation the interesting part is the
  start-up from rest (restart from `processor*/0` by `startFrom startTime; startTime 0`).

## Other files

* `scripts/cases/ofexec.sh`, `scripts/cases/ofexec_fast.sh`: rank wrappers (see above).
* Per case: `run_*.sh` scripts used for preparation and runs (in the case directories).
* `runs/perftest/`: MPI/launch tests (1M cavity, `mpibench/allred.c`); can be deleted.

## Restart run with a visualization function object

All three cases use `startFrom latestTime`, so a new run continues from the kept time.
1. Raise `endTime` in `system/controlDict` (e.g. 62M: `endTime` = latest + N*5e-7).
2. Append the function object inside the existing `functions { }` block, e.g.:
   ```
   functions
   {
       // derived fields for rendering (only computed, not written)
       vorticity1 { type vorticity; libs (fieldFunctionObjects); writeControl none; }
       Q1         { type Q;         libs (fieldFunctionObjects); writeControl none; }

       insitu
       {
           type            <yourFunctionObjectType>;   // e.g. the mesio/VDB export
           libs            (<yourLibrary>);            // libXXX.so in $FOAM_USER_LIBBIN
           executeControl  timeStep;
           executeInterval 10;                         // every 10 steps
           writeControl    timeStep;
           writeInterval   10;
           fields          (T b U p);                  // per case: see "Fields" above
       }
   }
   ```
   Function objects listed earlier run first, so `vorticity1`/`Q1` are available to
   `insitu` in the same step (`vorticity`, `Q` in the object registry).
   User libraries go to `$FOAM_USER_LIBBIN` =
   `/scratch/project/eu-25-121/milanjaros/openfoam/OpenFOAM-user/platforms/linux64GccDPInt32Opt/lib`.
3. To avoid writing full field time directories during a visualization run, set
   `writeControl timeStep; writeInterval 100000000;` (verified: the end time is not
   force-written), or keep `purgeWrite 1` so only the newest time survives.
4. `runTimeModifiable yes` is set, so a `functions` entry can also be added while a run
   is going (picked up at the next time step); `stopAt writeNow;` ends a run with a write.
5. Launch with the srun line of the case.
