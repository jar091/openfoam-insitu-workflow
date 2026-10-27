# mesioVDB: OpenFOAM v2606 function object for direct MPI-to-OpenVDB export

Status: 2026-10-26. Built and validated on Karolina (job 5270670, cn356 build, cn628 tests,
cn356-cn358 + cn628 for the 4-node test). Implements phases 1-4 of
`docs/mesio_openfoam_v2606_integration_proposal.md` and the configuration-audit part of
phase 5 (VDB-only policy, level 1/2, see Section 6).
Update 2026-10-26 evening: Mesio segfault fix and distributed VDB writer (option B of the
proposal, Section 10), available as the **dev** build (`install/mesio-dev` +
`install/openfoam-modules-mesio-dev/lib`); see Section 3.1 for switching production.
Update 2026-10-26 night: production hardening in the **next** build (`install/mesio-next` +
`install/openfoam-modules-mesio-next/lib`, Mesio in-situ API 2, Section 11): runs with
`FOAM_SIGFPE=true` (the wind-farm SIGFPE is fixed), Mesio errors become FatalError or a
warning (`onError`), several mesioVDB instances per run, `sampling cell`, units metadata,
memory report, topology changes without re-creating the context. The current sources in
`src/openfoam-insitu-modules/mesioFoam` require API 2 (they no longer build against `install/mesio`
or `install/mesio-dev`).

## 1. What it does

`mesioVDB` (library `libmesioFoam.so`) is a regular OpenFOAM function object. At every
export step all MPI ranks pass their local polyMesh and cell values **from memory** to the
Mesio in-situ API (`mesio_insitu.h`, see `docs/notes/mesio_build.md` Section 6). Mesio
redistributes the data, averages cell values to points, samples them at voxel centres and
writes **one `.vdb` file per export step** for all ranks (`<file>.tmp` renamed when complete;
dev build: OpenVDB leaf nodes are built, merged and compressed on all ranks and one writer
rank writes the file, Section 10). No per-rank field files are written or read.

* Native fields (`U`, `p`, `T`, ...) and derived fields computed by standard OpenFOAM
  function objects (`Q`, `vorticity`, `mag`, `grad`, ...) are looked up in the mesh
  `objectRegistry` and dispatched by type. OpenFOAM computes, Mesio converts and writes.
* Runs unmodified solvers (icoFoam, pimpleFoam tested) via `system/controlDict`.
* No OpenFOAM core file is modified.

## 2. Files

| What | Path |
|---|---|
| Module source (wmake) | `src/openfoam-insitu-modules/mesioFoam/` (`Make/{files,options}`, `Allwmake`, `mesioVDB/mesioVDB.{H,C}`, `mesioVDB/mesioVDBTemplates.C`) |
| Library (build output) | `$FOAM_USER_LIBBIN/libmesioFoam.so` = `/scratch/project/eu-25-121/milanjaros/openfoam/OpenFOAM-user/platforms/linux64GccDPInt32Opt/lib/libmesioFoam.so` |
| Object files | `src/openfoam-insitu-modules/mesioFoam/Make/linux64GccDPInt32Opt/` |
| Environment | `scripts/env_mesio_openfoam.sh` (= `env_openfoam.sh` + `MESIO_ROOT`, `OPENVDB_ROOT`, `OMP_NUM_THREADS=1`, `vdb_print` in `PATH`) |
| Build script | `scripts/build_mesio_openfoam.sh` (log `build/logs/mesio_openfoam_build[_dev].log`), `MESIO_VARIANT=dev` for the dev build |
| Dev build | `install/openfoam-modules-mesio-dev/lib/libmesioFoam.so` (objects in `build/openfoam-modules-mesio-dev/mesioFoam`, a copy of the sources) against `install/mesio-dev` |
| Launcher with the dev build | `scripts/cases/ofexec_vis_mesiodev.sh` (as `ofexec_vis.sh`) |
| Next build | `install/openfoam-modules-mesio-next/lib/libmesioFoam.so` (objects in `build/openfoam-modules-mesio-next/mesioFoam`) against `install/mesio-next` |
| Launcher with the next build | `scripts/cases/ofexec_vis_mesionext.sh` (as `ofexec_vis.sh`; `MESIO_NEXT_ROOT`/`MESIO_NEXT_FOLIB` override the directories) |
| Writer benchmark | `scripts/tests/bench_mesioVDB_writer.sh` (Section 10) |
| controlDict example | `data/openfoam/mesioVDB_controlDict_example` |
| Tests | `scripts/tests/test_mesioVDB_cavity.sh` (`SAMPLING=cell`), `test_mesioVDB_errors.sh`, `test_mesioVDB_reread.sh`, `test_mesioVDB_movingCone.sh`, `test_mesioVDB_refine.sh`, `run_mesioVDB_cavity3D.sh`, `test_mesioVDB_next.sh` (FPE/box/writers/two instances/onError on cavity3D 1M/8M), `compare_vdb_foam.py` |
| Test runs | `/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_fo/` |
| Renders | `/scratch/project/eu-25-121/milanjaros/openfoam/renders/mesio_fo/cavity3D_1M_v3/{U_mag,Q,p}/` |

Install location choice: `$FOAM_USER_LIBBIN` (scratch, set by `WM_PROJECT_USER_DIR` in
`env_openfoam.sh`). It is on `LD_LIBRARY_PATH` of every OpenFOAM process, so
`libs (mesioFoam);` works without absolute paths, and nothing is written to `$HOME` or into
the OpenFOAM source tree. If scratch is purged, re-run the build script (about 1 min).
The library has RPATHs to `install/mesio/lib64`, `install/openvdb/lib` and OpenMPI.

## 3. Build

```bash
srun --jobid=5270670 --overlap -N1 -n1 -c 16 -w cn356 \
    bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/build_mesio_openfoam.sh \
    > /mnt/proj2/eu-25-121/milanjaros/openfoam/build/logs/mesio_openfoam_build.log 2>&1
```

The script sources `env_mesio_openfoam.sh` and runs `Allwmake` (= `wmake libso .` with checks
for `MESIO_ROOT`/`OPENVDB_ROOT`).

Dev build (does not touch `$FOAM_USER_LIBBIN` nor the production objects in
`src/openfoam-insitu-modules/mesioFoam/Make/linux64GccDPInt32Opt`):

```bash
srun --jobid=5270670 --overlap -N1 -n1 -c 64 -w cn357 bash -c 'MESIO_VARIANT=dev NPROC=64 bash scripts/build_mesio.sh' \
    > build/logs/build_mesio_dev.log 2>&1
srun --jobid=5270670 --overlap -N1 -n1 -c 16 -w cn356 bash -c 'MESIO_VARIANT=dev bash scripts/build_mesio_openfoam.sh' \
    > build/logs/mesio_openfoam_build_dev.log 2>&1
```

Next build (Mesio in-situ API 2; required by the current sources):

```bash
srun --jobid=5275975 --overlap -N1 -n1 -c 64 -w cn317 bash -c 'MESIO_VARIANT=next NPROC=64 bash scripts/build_mesio.sh' \
    > build/logs/build_mesio_next.log 2>&1
srun --jobid=5275975 --overlap -N1 -n1 -c 16 -w cn318 bash -c 'MESIO_VARIANT=next bash scripts/build_mesio_openfoam.sh' \
    > build/logs/mesio_openfoam_build_next.log 2>&1
```

`MESIO_VARIANT=dev` in `env_mesio_openfoam.sh` selects `MESIO_ROOT=install/mesio-dev` and puts
`install/openfoam-modules-mesio-dev/lib` first in `LD_LIBRARY_PATH`; the build script copies
the sources to `build/openfoam-modules-mesio-dev/mesioFoam` and builds there with
`FOAM_USER_LIBBIN` redirected.

### 3.1 Switching a run (or production) to the next build

Same mechanism as for dev below, with `next`:

* launcher: `scripts/cases/ofexec_vis_mesionext.sh` instead of `ofexec_vis.sh` /
  `ofexec_vis_mesiodev.sh` (same arguments; e.g. `LAUNCHER=ofexec_vis_mesionext.sh` in the
  wind-farm `run_par.sh`), and remove `FOAM_SIGFPE=false` workarounds;
* environment: `MESIO_VARIANT=next source scripts/env_mesio_openfoam.sh`;
* rebuild: `MESIO_VARIANT=next NPROC=64 bash scripts/build_mesio.sh`, then
  `MESIO_VARIANT=next bash scripts/build_mesio_openfoam.sh` (compute node, see Section 3).

Existing `controlDict`s work unchanged (all old keys keep their meaning). The next function
object needs the next Mesio libraries (API 2; a mismatch fails at link/load time, the
sources refuse to compile against an older header). To make next the default production build
(when no run uses the old one): `bash scripts/build_mesio.sh` and
`bash scripts/build_mesio_openfoam.sh` without `MESIO_VARIANT` (rebuild `install/mesio` first).

### 3.2 Switching a run (or production) to the dev build

`libs (mesioFoam);` loads the first `libmesioFoam.so` in `LD_LIBRARY_PATH`, and both the
function object and the Mesio libraries use RUNPATH, so the order of `LD_LIBRARY_PATH` decides:

* launcher: replace `scripts/cases/ofexec_vis.sh` by `scripts/cases/ofexec_vis_mesiodev.sh`
  (same arguments), or
* environment: `MESIO_VARIANT=dev source scripts/env_mesio_openfoam.sh`, or prepend
  `install/openfoam-modules-mesio-dev/lib:install/mesio-dev/lib64` to `LD_LIBRARY_PATH`
  after sourcing the production environment.

The C API is ABI compatible: the production `libmesioFoam.so` also runs with the dev Mesio
libraries (segfault fix + distributed writer by default), but only the dev function object
knows the `writer`/`compression` keys and prints the phase line. To make the dev build the
production build permanently (when no run uses the old one): run `scripts/build_mesio.sh` and
`scripts/build_mesio_openfoam.sh` without `MESIO_VARIANT` (rebuilds `install/mesio` and
`$FOAM_USER_LIBBIN/libmesioFoam.so` from the same working trees). Fall back at run time with
`MESIO_VDB_WRITER=single` (legacy writer) if needed. `Make/options` uses `$(GENERAL_RULES)/mpi-rules`
(`PFLAGS PINC PLIBS`), `-I$(MESIO_ROOT)/include -DMESIO_INT_WIDTH=32` and links
`-lfiniteVolume -lmeshTools -lmesioapi -lmpi`. Static asserts check `label` ==
`MESIOInt` (32 bit) and `scalar` == `double` (DP build). Same toolchain as OpenFOAM and
Mesio (foss/2025b, GCC 14.3, OpenMPI 5.0.8). The only compiler message is a harmless
`wmkdepend: could not open 'omp.h'` from the dependency scanner.

## 4. Usage

Source the environment in every run (`OMP_NUM_THREADS=1` matters: Mesio uses OpenMP inside
every rank):

```bash
srun --jobid=5270670 --overlap -N1 -n128 -w cn628 --mpi=pmix bash -c '
  export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
  source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_mesio_openfoam.sh >/dev/null 2>&1
  cd <case> && exec icoFoam -parallel' > log.icoFoam 2>&1
```

Minimal `system/controlDict` (complete commented version:
`data/openfoam/mesioVDB_controlDict_example`):

```cpp
functions
{
    Q1                                  // derived field, BEFORE the exporter
    {
        type            Q;
        libs            (fieldFunctionObjects);
        field           U;
        result          Q;
        executeControl  timeStep;
        executeInterval 50;             // same cadence as the export
        writeControl    none;           // in memory only, never written
    }
    mesioVDB1
    {
        type            mesioVDB;
        libs            (mesioFoam);
        writeControl    timeStep;       // export cadence
        writeInterval   50;
        fields          (U p Q);        // -> grids U_mag, p, Q
        density         256;            // or voxelSize 0.0005;
        outputDir       "VDB";          // relative to the case
        outputPolicy    vdbOnly;
    }
}
```

### Settings

| Key | Default | Meaning |
|---|---|---|
| `fields` | (required) | Registered field names (exact names, e.g. `mag(U)`) |
| `vectorComponents` | `(mag)` | Grids per vector field: `mag` -> `<f>_mag` (magnitude formed by Mesio from interpolated components), `x y z` -> `<f>_x` ... |
| `tensorComponents` | `(mag)` | Grids per symmTensor/tensor: `mag` (local `mag()`), `xx xy ...` |
| `voxelSize` | 0 | Voxel size in world units, overrides `density` |
| `density` | 100 | Voxels along the longest edge of the box (`h = 1.0001*maxExtent/density`) |
| `box` | mesh bounds | `(x0 y0 z0) (x1 y1 z1)` (an OpenFOAM `boundBox`, no outer parentheses): voxelize only this box |
| `movingMesh` | false | Create the context in moving-mesh mode from the start (motion is detected automatically anyway) |
| `writerRank` | 0 | Rank that writes the file |
| `writer` | Mesio default (`distributed`) | dev build: `distributed`, `parallel` (one writer per node for the leaf data, same single file) or `single` (legacy) |
| `compression` | Mesio default (`blosc`) | dev build: `blosc` or `none` |
| `sampling` | Mesio default (`cellPoint`) | next build: `cellPoint` (cell values averaged to points, interpolated in the cells) or `cell` (value of the cell containing the voxel centre: exact cell values, no smoothing at walls) |
| `onError` | `error` | next build: Mesio error -> `error`: FatalError with the Mesio message; `warn`: warning, the export is skipped and retried at the next export (context rebuilt if Mesio failed internally) |
| `memoryTracking` | `false` | next build: `true` reports the peak RSS of every export (resets the process VmHWM at each export; otherwise the peak since the start is reported) |
| `verbosity` | 0 | 1 = Mesio progress output |
| `outputDir` | `VDB` | Relative to the (global) case directory; `$VAR` and `<case>` are expanded |
| `filePattern` | `%NAME%_%TIMEINDEX%.vdb` | Tokens `%NAME%` (function object), `%TIME%` (time name), `%TIMEINDEX%`, `%COUNT%` (zero padded to `indexWidth`, default 6) |
| `missingField` | `error` | `error`, `warn`, `skip` (field missing at the first export) |
| `staleField` | `warn` | `error`, `warn`, `ignore` (field not updated in the export step, see 5) |
| `outputPolicy` | `standard` | `vdbOnly`: start-up audit, see Section 6 |
| `policyAction` | `error` | `warn`: report vdbOnly violations without stopping |
| `writeControl`, `writeInterval`, `region`, `timeStart`, `timeEnd`, `log` | | standard function-object entries |

Supported types: `volScalarField`, `volVectorField`, `volSphericalTensorField`,
`volSymmTensorField`, `volTensorField` and their internal fields (`DimensionedField<Type,
volMesh>`). Surface and point fields and other objects are rejected with an error naming the
type (`object phi has unsupported type surfaceScalarField`).

Log output per export (rank 0):

```
mesioVDB mesioVDB1 write: ".../VDB/cavity3D_000300.vdb"
    voxels 8000000, size 68.741 MB
    time [s] 1.72231 (fields 0.000328, convert 0.026, sample 0.030, gather 0.039, write 1.630)
```

`time` is the wall time of the export (max over ranks); the phases are the per-phase maxima
over ranks from `MESIOInSituLastWriteStats` (convert = redistribution + cell-to-point,
sample = voxel sampling + packing, gather = transfer to the writer, write = OpenVDB grid
build + file write on the writer). The dev build reports the distributed writer as
`gather` = plan + exchange + merge/compression + transfer (the ranks wait here until the writer
has received their data) and `write` = file write, plus a second line:

```
    phases [s] (max over ranks): plan 1.3e-06, sample 0.0151, exchange 0.0104, merge+compress 0.0136, gather 0.39, file 0.353
```

The next build adds a memory line (writer rank and maximum over ranks; "Mesio buffers" = the
largest amount of Mesio write buffers held at the same time):

```
    memory [MB]: writer rank RSS 335.2, peak 477.3 (since start), Mesio buffers 141.1; max over ranks: peak 495.5, Mesio buffers 141.1
```

At the first export the context setup (mesh transfer, redistribution, voxelization) is reported
separately (`setup time`), and `end()` prints the total export time (and the number of exports
skipped after Mesio errors with `onError warn`).

Grid metadata (next build): every grid has `units` (SI units from the field dimensions, e.g.
`m s^-1`, `m^2 s^-2`, `s^-2`, `1` for dimensionless fields), `dimensions` (OpenFOAM dimension set
`[kg m s K mol A cd]`, e.g. `[0 1 -1 0 0 0 0]`), `field` (source field) and `component`
(`mag`, `x`, ...; absent for scalars), besides `time` (`vdb_print -l -m <file>`).

## 5. Derived fields, ordering and freshness

* OpenFOAM calls, per time step and in dictionary order, `execute()` and `write()` of every
  function object (`functionObjectList::execute`). Producers listed **before** `mesioVDB1`
  therefore update their result before the export in the same step (verified: `Q` exported
  from the vdbOnly run is bitwise identical to the run that also writes `Q` to disk).
* Use `executeControl timeStep; executeInterval N` on the producer with the same `N` as the
  exporter's `writeInterval` (or 1), and `writeControl none` so the producer never writes
  its result. With `writeControl none` `fieldExpression`-based objects (`Q`, `vorticity`,
  `mag`, `grad`, ...) keep the result only in the registry (`NO_WRITE`), so the solver's
  `Time::write` does not write it either.
* Freshness check: `mesioVDB::execute()` (every step) records an event marker of the mesh
  registry (`objectRegistry::getEvent()`); every non-const access to a field updates its
  `regIOobject::eventNo()`. At the export a field whose `eventNo` is not newer than the
  marker of the previous step is stale (not recomputed in this step) -> `staleField`
  action. Fields that are legitimately constant (e.g. read-only material fields) need
  `staleField ignore` (or `warn`).
* A field that does not exist at the first export is an error (`missingField error`), or is
  dropped for the whole run (`warn`/`skip`): the grid list is fixed when the Mesio context
  is created. If a committed field later disappears, `error` stops the run, otherwise the
  grid is written as zeros with a warning.
* Producers whose first execution is after the first export (e.g. `executeInterval 40`
  with export every 20) trigger the missing-field error at the first export.

## 6. VDB-only output policy (what is enforced)

`outputPolicy vdbOnly` audits the configuration at start-up (and after a runtime re-read)
and stops with a list of violations (`policyAction warn` only warns):

1. Solver output: `writeControl`/`writeInterval` of the controlDict must not produce a write
   time in `(startTime, endTime]` (`timeStep`: first multiple of the interval after the
   start index beyond the last step; `runTime`/`adjustableRunTime`: no multiple of the
   interval in the run; `clockTime`/`cpuTime` cannot be verified -> violation).
2. Every other enabled function object in `functions` must use `writeControl none`
   (next build: other `mesioVDB` entries are exempt, they only write `.vdb` files).

Verified by file-tree snapshots (`test_mesioVDB_cavity.sh`, snapshot of all files except
`log.*` before and after the solver): serial and 4-rank vdbOnly runs created **only** the
`.vdb` files; no time directories, no `uniform/`, no `postProcessing/`, no processor
time directories. The `standard` reference run writes `0.5/{U,p,phi,Q,vorticity,mag(U),uniform}`
as expected.

Not controlled (documented limits, proposal levels 2/3): stdout logs, pre-existing case files
and `processor*` directories from `decomposePar`, explicit writes by solvers
(`runTime.writeNow()`, `stopAt writeNow`), `foamJob`/profiling files if enabled, other
plugins. A restart checkpoint must be configured explicitly (rare `writeInterval` with
`outputPolicy standard`); a VDB is not a restart file.

## 7. Mesh changes

* `movePoints()` (deforming/moving mesh) marks the points dirty; the next export calls
  `MESIOInSituUpdatePoints` and Mesio re-voxelizes (grid follows the mesh bbox unless `box`
  is given). If the context was created as static, it is re-created once in moving mode.
* Run-time re-read of `controlDict` (`runTimeModifiable`), next build: all settings are
  parsed and validated before any of them changes. Changed grid/context settings (`fields`,
  `box`, `voxelSize`, `density`, component lists, `movingMesh`, `writerRank`, `writer`,
  `compression`) re-create the context at the next export on all ranks (log `settings
  changed, Mesio context is re-created at the next export`); `sampling`, `memoryTracking`,
  `onError` and the output/diagnostic entries apply immediately; invalid entries are reported
  (`invalid settings after the run-time re-read of the dictionary; settings not changed`) and
  the previous settings stay in effect (OpenFOAM does not trap errors of `read()` at a
  re-read, so an invalid entry used to stop the run). The dev/production builds crashed on
  every rank except 0 when a `box` was present (found on occDrivAer, 640 ranks): the master
  broadcasts the re-read dictionary as a binary-format stream, and the `boundBox` reader
  takes its raw binary path there (`ITstream::readRaw: Not implemented`); the box is now read
  as two points (token based). Test: `scripts/tests/test_mesioVDB_reread.sh` (Section 11.6).
* `updateMesh()` (topology change, e.g. `dynamicRefineFvMesh`): next build: the Mesio mesh is
  rebuilt in the existing context at the next export (`MESIOInSituResetMesh` + `SetFVMesh` +
  `Commit`; communicators, options, grids and metadata are kept; log line `mesh changed, Mesio
  mesh rebuilt (N cells) in T s`). dev build, and changed settings after a runtime re-read of
  `controlDict`: the context is destroyed (`MESIOInSituDestroy`) and re-created at the next
  export (collective; setup cost again).
* Serial runs: OpenFOAM does not initialize MPI without `-parallel`; the function object then
  calls `UPstream::initNull()` (MPI_Init, finalized by OpenFOAM at exit). In parallel the
  OpenFOAM world communicator of the mesh is passed to Mesio (Mesio duplicates it).
* The context is destroyed in the destructor of the function object, which runs before
  OpenFOAM finalizes MPI (Time is destroyed before argList); if MPI is already finalized the
  call is skipped.

## 8. Validation

### 8.1 icoFoam cavity tutorial, serial vs 4 ranks (`test_mesioVDB_cavity.sh`, cn628)

`fields (U p Q vorticity mag(U))`, `vectorComponents (mag x y)`, `density 200`
(200x200x20 voxels, h = 0.0005), export every 20 steps, 100 steps, `staleField error`.
Runs: `runs/mesio_fo/cavity/{np1,np4,ref}`.

* 5 exports per run, one file each (`VDB/cavity_0000{20..100}.vdb`), 9 grids
  (`U_mag U_x U_y p Q vorticity_mag vorticity_x vorticity_y mag(U)`), 800,000 active voxels,
  fog volumes with `time` metadata, 12.6 MB per file.
* np1 vs np4 (voxel by voxel, `build/tools/vdb_diff`): identical active voxel sets;
  `U_*`, `mag(U)` max |diff| < 6e-6 (solver tolerance, 0 voxels above 1e-5 relative),
  `Q` max |diff| 7e-3 of max |Q| 7565 (1e-6 relative), `vorticity_mag` 1e-4 of 150.
  `p` differs by a **constant** 0.04324 (std 1.9e-7): the pressure level of the cavity is
  fixed by `pRefCell 0`, which is a rank-local cell index, so the level depends on the
  decomposition (OpenFOAM behaviour, not an export error).
* vdbOnly vs standard policy: `Q` grids bitwise identical.
* VDB vs OpenFOAM reference (`compare_vdb_foam.py`: trilinear VDB sample at the 400 cell
  centres vs the fields written by the `ref` run at t = 0.5):

  | Field | all cells: max / RMS error (% of range), corr. | interior cells (2 outer layers excluded) |
  |---|---|---|
  | Q | 37 % / 3.0 %, 0.935 | 0.30 % / 0.07 %, 0.9988 |
  | p | 11 % / 0.8 %, 0.992 | 0.13 % / 0.02 %, 0.99998 |
  | mag(U) | 12 % / 2.7 %, 0.992 | 6.5 % / 1.4 %, 0.991 |

  The large boundary errors come from Mesio's cell-to-point averaging, which smooths the
  extreme values at the lid corners of this coarse 20x20 mesh (documented Mesio semantics).

### 8.2 Diagnostics (`test_mesioVDB_errors.sh`): all 7 cases pass

stale field `error` (stops: "field Q was not updated in the current time step 0.2") and
`warn` (continues), vdbOnly violation (producer without `writeControl none`), missing field
(error with list of available fields), `missingField skip` (runs to End), unsupported type
(`phi`), second mesioVDB instance (error). The script now expects the next build behaviour
(9 cases, Section 11.2): two instances run to End and write both outputs, `onError warn`
skips the failed exports, `onError error` stops with the Mesio message.

### 8.3 Moving mesh (`test_mesioVDB_movingCone.sh`, pimpleFoam movingCone, 1 and 4 ranks)

Context created in moving mode (`mesh.moving()`), points updated at each of the 6 exports,
active voxel count changes with the deforming mesh (264,886 / 265,064 / 265,294 ...);
np1 vs np4: same active voxels, max |diff| 2e-4 (U_mag, max 3.1) and 4e-4 (p, max 6.5),
i.e. solver tolerance. Export 0.80 s (1 rank) / 0.30 s (4 ranks), dominated by
re-voxelization (`convert` 0.67 / 0.22 s).

### 8.4 Topology changes (`test_mesioVDB_refine.sh`, 3D cavity, pimpleFoam + dynamicRefineFvMesh)

Refinement/unrefinement every 7 steps, export every 10 steps, `Q` derived field,
`staleField error`, vdbOnly. Serial and 4 ranks: the context is destroyed and re-created
after every topology change (4096 -> 69021 -> 56589 cells), 4 exports each, 128^3 voxels
written every time, run reaches End. Re-creation costs 1.8-2.7 s on 4 ranks
(voxelization of 2.1 M voxels). np1 and np4 refine different regions (p level, see 8.1),
so their files are not compared.

### 8.5 cavity3D 1M (OpenFOAM HPC TC, icoFoam fixedIter), 128 ranks on cn628

`run_mesioVDB_cavity3D.sh` (case `runs/mesio_fo/cavity3D_1M/case`, scotch 128 +
renumberMesh, 300 steps, deltaT 1e-3), `fields (U p Q)` (`Q` by the `Q` function object,
`writeControl none`), export every 30 steps, `staleField error`, vdbOnly.

| Run | voxels | file | export wall time (mean, 10 exports) | setup | run ClockTime |
|---|---|---|---|---|---|
| baseline (no function objects) | - | - | - | - | 20 s (0.06 s/step) |
| `density 100` | 100^3 = 1 M | 9.2 MB | 0.30 s (write 0.29 s) | 0.17 s | 23 s |
| `density 200` | 200^3 = 8 M | 69 MB | 1.85 s (write 1.63 s, gather 0.04-0.68 s) | 0.36 s | 38 s |

So one export costs about 5 solver steps at 1 M voxels and about 30 steps at 8 M voxels for
this (very cheap, 7.8k cells/rank) case. Fields copy, cell-to-point conversion and sampling
are below 0.03 s; the single-writer OpenVDB build + blosc write is >85 % of the time.
`vdb_print`: grids `Q`, `U_mag`, `p`, fog volume, `time` metadata, 8,000,000 active voxels,
`blosc + active values`, voxel size 0.0005.

Renders (CyclesPhi CPU, cn628, `data/cyclesphi/render_vdb_series.sh`, 960x540, 64 spp,
5-12 s per frame), frames 30/150/300 of the density-200 series:

* `renders/mesio_fo/cavity3D_1M_v3/U_mag/cavity3D_000{030,150,300}.png` (viridis 0..0.4:
  lid layer and the jet turning down the downstream wall),
* `renders/mesio_fo/cavity3D_1M_v3/Q/...png` (inferno, Q 10..600: vortices along the two
  lid edges at the side walls),
* `renders/mesio_fo/cavity3D_1M_v3/p/...png` (coolwarm -2..2: high pressure in the
  downstream upper corner, low upstream).

All under `/scratch/project/eu-25-121/milanjaros/openfoam/`.

### 8.6 4 nodes, 512 ranks (cn356, cn357, cn358, cn628)

Same case re-decomposed to 512 subdomains (`BASE=.../runs/mesio_fo/cavity3D_1M_4n
NODE=cn356,cn357,cn358,cn628 NP=512 run_mesioVDB_cavity3D.sh ...`), `density 200`:

| Run | export wall time (mean of 10) | phases (typical) | setup | run ClockTime |
|---|---|---|---|---|
| baseline | - | - | - | 142 s (0.43 s/step: 2k cells/rank, the solver does not scale this far) |
| `density 200` | 2.4 s (first 3.8 s) | convert 0.37-1.4 s, sample 0.007 s, gather 0.03 s, write 1.64 s | 3.0 s | 154 s |

The all-to-all redistribution (`convert`) over 4 nodes is slower than on 1 node, the
writer cost is unchanged. Files are complete (8 M voxels, 69 MB). 128 vs 512 ranks at
step 300: same active voxels, `U_mag` max |diff| 3.6e-5 (of 0.95), `Q` 2.5 (of 1.6e5); `p`
offset 0.27 (pRefCell, see 8.1). Differences come from the decomposition-dependent
fixed-iteration solver (67 PCG iterations, DIC), not from the export.

### 8.7 Example snippet

`data/openfoam/mesioVDB_controlDict_example` was `#include`d into the cavity tutorial
controlDict (`runs/mesio_fo/example`): audit passed, grids `U_mag p Q vorticity_mag`,
2 exports, run reaches End, the case tree contains only `VDB/` as new output.

## 9. Limitations and open issues

* **Writer** (production build): OpenVDB grid construction and the blosc file write on
  `writerRank` are the bottleneck (about 15 M voxel values/s). Dev/next build: leaves are built
  and compressed on all ranks; the remaining cost is the file write of one client
  (~0.7-0.9 GB/s on `/scratch`), see Section 10. Writer memory: Section 11.4.
* **Value semantics** (Mesio, default `sampling cellPoint`): cell values -> point averages ->
  interpolation at voxel centres; extremes in boundary cells are smoothed (Section 8.1). Not
  conservative. Vector magnitudes are formed from the interpolated components. Next build:
  `sampling cell` writes exact cell values (piecewise constant; Section 11.3).
* **Floating-point exceptions**: production and dev builds raise SIGFPE with `FOAM_SIGFPE`
  when voxel centres coincide with mesh points (wind farm, cavity3D with an aligned grid);
  fixed in the next build (Section 11.1).
* **Several instances** need the next build (production/dev: one mesioVDB entry per run).
* **Empty ranks**: production/dev: every rank must own a cell; next: allowed.
* **Mesio errors**: production/dev: `MPI_Finalize` + `exit` inside the library; next: error
  codes -> FatalError or warning (`onError`). Errors that only some ranks detect inside
  Mesio's collective phases (memory exhaustion, internal errors) still end the job
  (`MPI_Abort`, as OpenFOAM's FatalError in parallel).
* **Intermittent segfault in `MESIOInSituCommit`** (production build, out-of-bounds read in
  `linkNodesAndElements`): fixed in the dev and next builds, see `mesio_build.md` Section 8.
* **Topology changes** rebuild the Mesio mesh and voxelization (next: in the same context,
  Section 11.5; the voxelization dominates); moving meshes re-voxelize at every export.
* **Freshness** is based on registry events; a field modified only by a later function
  object in the same step counts as fresh in the next step.
* **Not supported**: surface/point fields, boundary values, multiple regions in one run,
  single precision builds, `WM_LABEL_SIZE=64` (Mesio would need `--intwidth=64`).
* **vdbOnly** is a configuration audit, not a write interception (Section 6).
* Restarts: file names use the time index (deterministic, existing files are overwritten
  atomically via `.tmp` + rename); `%COUNT%` restarts at 0.

## 10. Distributed writer and segfault fix (dev build, 2026-10-26)

Details in `docs/notes/mesio_build.md` Sections 8 (segfault) and 9 (writer design, profile).

* **Segfault** at the first export in `MESIOInSituCommit` -> `linkNodesAndElements`
  (motorbike 512 ranks, pitzDaily 62M 2048 ranks, cavity3D 512 ranks): an out-of-bounds read
  (confirmed with AddressSanitizer) in a mesh-linking step that assumes ESPRESO's own node
  ordering and whose result the in-situ path does not use. The step is skipped now.
* **Writer**: every rank builds the OpenVDB leaf nodes of its voxels; leaves are merged on
  owner ranks (contiguous ranges of the file order) and compressed there in parallel; the
  writer rank only writes header/topology/metadata and the received leaf records. Same file
  as before (byte-identical except the random UUID; checked for all exports of the runs below).

Benchmark: icoFoam cavity3D 8M (200^3 hex), 256 ranks on cn356+cn357 (`--cpu-bind=cores`,
`UCX_TLS=ud,sm,self`), `fields (U p Q)` -> 3 grids, export every 10 steps, mean of exports 2-4
(`scripts/tests/bench_mesioVDB_writer.sh`, case `runs/mesio_dev/c3d8M_256`, logs
`log.icoFoam.<tag>`):

| Voxels (density) | File | Production build | Dev build (distributed, blosc) | Speed-up |
|---|---|---|---|---|
| 32.8 M (320) | 243-251 MB | 7.0 s (gather 0.15, write 6.75) | 0.45 s | 15x |
| 128 M (504) | 917 MB | 26.9 s (gather 0.5, write 26.1) | 1.5-1.8 s | 15-18x |

The first export of a run additionally computes the leaf layout (0.2 s at 32.8 M, 0.9 s at
128 M voxels). Setup times are unchanged (1.3-1.5 s and 2.5 s). For HPC_motorbike Small
(32.5 M voxels, 4 grids, 395 MB, 9.8 s per export with the production build, of which
8.85 s in the writer) the expected export time is about 1 s plus the sampling of the slowest
rank (0.72 s there, reduced by the weight cache from the second export on); the 512-rank case
was not rerun here (nodes cn356/cn357 only).


## 11. Next build: FPE fix, error handling, several instances, cell sampling (2026-10-27)

Build `install/openfoam-modules-mesio-next/lib/libmesioFoam.so` against `install/mesio-next`
(Mesio in-situ API 2, `docs/notes/mesio_build.md` Section 10), launcher
`scripts/cases/ofexec_vis_mesionext.sh`; switching: Section 3.1. All tests below ran with
`FOAM_SIGFPE=true` (`trapFpe` enabled) on cn317/cn318 (job 5275975); test runs in
`/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_fix/`.

### 11.1 Floating-point exceptions

The wind-farm SIGFPE (`computeVolumeIndices` <- `MESIOInSituCommit`, `FOAM_SIGFPE=false`
workaround in production) happens whenever voxel centres coincide with mesh points (box
aligned with mesh planes and the voxel size dividing the cell size), not only on ranks outside
the box. Reproduced with the dev build on icoFoam cavity3D 1M (128 ranks) and 8M (256 ranks)
with an aligned box, and on the wind-farm mesh on 256 ranks; fixed in Mesio (next). Runs:

| Case (ranks) | dev, `FOAM_SIGFPE=true` | next, `FOAM_SIGFPE=true` | next vs dev (`FOAM_SIGFPE=false`) |
|---|---|---|---|
| wind farm MB12 mesh, production box and voxel size 0.005 (52.4 M voxels, `U Q vorticity`), pimpleFoam from t = 0, exports at steps 5 and 10, copy `runs/mesio_fix/windfarm256` (256, cn317+cn318) | SIGFPE in `computeVolumeIndices` on all ranks | End; setup 1.11 s (dev 2.89 s), export 0.85 s | voxel values identical |
| icoFoam cavity3D 1M, box (0 0 0) (0.03 0.03 0.1), voxel 0.0005 (0.72 M voxels; most ranks without cells in the box) (128) | SIGFPE | End, 3 writers byte-identical | identical |
| icoFoam cavity3D 8M, box (0 0 0) (0.04 0.03 0.1), voxel 0.00025 (7.7 M voxels) (256) | SIGFPE | End, 3 writers byte-identical; setup 1.87 s (dev 3.84 s) | identical |

Production: switch the wind-farm (and every other) mesioVDB run to the next build and drop
`FOAM_SIGFPE=false` (Section 3.1).

### 11.2 Mesio errors (`onError`)

Mesio returns error codes and a message (identical on all ranks for the collective calls).
`onError error` (default): FatalError on all ranks, e.g.

```
--> FOAM FATAL ERROR: (openfoam-2606)
Function object mesioVDB1: MESIOInSituWriteVDB failed (Mesio error 3):
    rank 0: cannot write '/proc/mesio_no_such_dir/cavity3D_000010.vdb': filesystem error: cannot create directories: ...
    Use 'onError warn' to skip failed exports instead.
```

`onError warn`: a warning, the export is skipped, the run continues; `end()` reports the number
of skipped exports. After an internal Mesio error the Mesio mesh is rebuilt at the next export.
Rank-local calls (`SetCellField`, `UpdatePoints`, metadata) that fail are reported on their
rank (`Pout`) and by the following collective call on all ranks. Errors that only some ranks
detect inside Mesio's collective phases still end the job (`MPI_Abort`). Tests: cavity3D 8M
on 256 ranks (unwritable output: `error` stops all ranks with the message above, `warn` skips
both exports, a second instance writes normally), `test_mesioVDB_errors.sh` (9 cases).

### 11.3 Sampling: `cellPoint` vs `cell` (accuracy at walls)

`test_mesioVDB_cavity.sh` (cavity tutorial, 400 cells, VDB sampled trilinearly at the cell
centres vs the OpenFOAM fields, t = 0.5), next build:

| Field | `sampling cellPoint` (default): all cells max / RMS (% of range) | interior cells | `sampling cell`: all cells max / RMS |
|---|---|---|---|
| Q | 37 % / 3.0 % (corr. 0.935) | 0.30 % / 0.07 % | 0.00005 % / 0.000004 % (corr. 1.00000) |
| p | 11 % / 0.8 % | 0.13 % / 0.02 % | 0.00005 % / 0.000008 % |
| mag(U) | 12 % / 2.7 % | 6.5 % / 1.4 % | 0.00006 % / 0.00003 % |

With `cell` the VDB reproduces the OpenFOAM cell values (float round-off; the trilinear
sample at a cell centre only sees voxels of the same cell here) and the extremes at the walls
(VDB range of Q = OpenFOAM range [-7896, 359] instead of [-4845, 249]). The price is a
piecewise constant field (staircase at the cell size, visible in close-ups and in derived
quantities such as gradients computed from the grid); `cellPoint` stays the default. np1 vs np4
with `cell`: identical active voxels, the same round-off-level differences as with `cellPoint`
(and the `pRefCell` offset of p, Section 8.1).

### 11.4 Memory (writer rank)

Log line `memory [MB]` (Section 4). With `memoryTracking true`, cavity3D 8M on 256 ranks,
whole mesh, 3 grids, second export (details in `mesio_build.md` Section 10.7):

| Voxels (file) | Writer | Export | Writer rank peak (RSS before) | Mesio buffers on the writer |
|---|---|---|---|---|
| 33 M (248 MB) | distributed | 0.46 s | 728 MB (320 MB) | 383 MB |
| 33 M | single | 8.8 s | 914 MB (325 MB) | 586 MB |
| 126 M (903 MB) | distributed | 1.53 s | 1854 MB (1814 MB) | 1508 MB |
| 126 M | single | 36 s | 3043 MB (1893 MB) | 2696 MB |

The writer rank is the maximum over the ranks. Plan for ~12 B per voxel (distributed) or
~18-22 B per voxel (single) on the writer rank (3 grids), on top of the solver.

### 11.5 Topology changes and setup time

Topology changes (`test_mesioVDB_refine.sh`, dynamicRefineFvMesh, 56-68 k cells, 2.1 M voxels):
the next build rebuilds the Mesio mesh in the existing context (`MESIOInSituResetMesh`); with the
faster voxelization the rebuild takes 0.67-0.73 s on 1 rank (dev: 5.6-5.9 s) and 0.28-0.30 s
on 4 ranks (dev, destroy + create: 2.5-2.7 s). The files are voxel-identical to the earlier
runs. Initial setup: cavity3D 8M with the aligned box 3.84 s (dev) -> 1.87 s, 1M 0.68 s ->
0.38 s; moving meshes re-voxelize at every export and gain the same.

### 11.6 Other checks

* Grid metadata: `units`, `dimensions`, `field`, `component` per grid (`vdb_print -l -m`), e.g.
  `U_mag: units m s^-1, dimensions [0 1 -1 0 0 0 0], field U, component mag`;
  `p: m^2 s^-2` (kinematic pressure), `Q: s^-2`.
* Two instances (box with `cellPoint`, coarse whole-mesh grid with `sampling cell` and
  `memoryTracking true`, cavity3D 8M, 256 ranks): both write every export; the files of the
  first instance are voxel-identical to the dev build without the second instance. The vdbOnly
  audit no longer flags the other mesioVDB entry (it only writes `.vdb` files; the first
  attempt failed because OpenFOAM disabled both function objects after the audit error).
* movingCone (pimpleFoam, 1 and 4 ranks) and dynamic refinement (1 and 4 ranks): see the
  table in 11.5; voxel counts and values as with the earlier builds.
* Run-time re-read (`test_mesioVDB_reread.sh`, cavity on 4 ranks, controlDict edited after
  the first export): `touch` (no change), changed `box`, `voxelSize`, `fields` (context
  re-created with the new grid at the next export: 161x161x21 -> 121x121x21 / 81x81x11, grids
  `(U_mag p)` -> `(U_mag)`), changed `sampling` (applied, no re-creation) and an invalid box
  (warning, previous settings kept): all runs reach End on all ranks with 20 exports. With the
  previous `box` reading (as in the dev/production builds) the `box` case stopped ranks 1-3
  with `ITstream::readRaw: Not implemented`. Run the script on a compute node (see its header).
* Build: no compiler warnings with OpenFOAM's `-Wall -Wextra -Wold-style-cast`.
