# Mesio (ESPRESO, branch `sc22`) with OpenVDB output: build notes and in-situ API

Status: 2026-10-26. Built and tested on Karolina (`cn356`/`cn357`, job 5270670) with
`foss/2025b` (GCC 14.3.0, OpenMPI 5.0.8), the same toolchain as OpenFOAM v2606.
Update 2026-10-26 evening: segfault fix in `MESIOInSituCommit` and the distributed VDB writer
(Sections 8 and 9), installed as the `dev` variant (`install/mesio-dev`).
Update 2026-10-26 night (job 5275975, cn317/cn318): production hardening, installed as the
**`next`** variant (`install/mesio-next`, in-situ API version 2, Section 10): no floating-point
exceptions (the wind-farm SIGFPE), error codes instead of `exit`, several contexts per process,
empty ranks, `MESIOInSituResetMesh` for topology changes, `cell` sampling, field metadata (units),
memory statistics.

## 1. Summary

* `src/espreso` is checked out on branch **`mjar/devel`** (based on `sc22`, the only branch with
  the OpenVDB writer). All changes are in the working tree (not committed here).
* We built OpenVDB 12.0.1, oneTBB 2021.13.0 and c-blosc 1.21.6 from source into
  `install/openvdb`; no foss/2025b modules exist for them. Boost 1.88 comes from a module.
* Mesio is built as shared libraries (`libnb*.so`, `libmesioapi.so`) plus the `mesio`
  executable, installed into `install/mesio` (production) or `install/mesio-<variant>`
  (`MESIO_VARIANT=dev|next|asan-next`, Section 2). `HAVE_OPENVDB` is enabled.
* **In-situ API (new):** `include/mesio_insitu.h` is implemented in `libmesioapi.so`. The caller
  passes the distributed OpenFOAM polyMesh and scalar cell fields from memory. Each export call
  writes **one `.vdb` file**: FloatGrids named after the fields, class fog volume, with a correct
  transform. See Section 6.
* Tests:
  * File-based `mesio` on a decomposed OpenFOAM case: 1-rank and 4-rank outputs are bitwise
    identical.
  * In-situ driver (`data/mesio_tests`): it checks world positions, fog class and time metadata.
    1-rank and 4-rank outputs are equal to float round-off (max |diff| about 1e-5); see Section 5.
  * A CyclesPhi render of an in-situ output works.
  * `next` (Section 10): all driver tests with trapped FP exceptions on 1-256 ranks, 14
    robustness cases x 3 writers (byte-identical files), 20 error-handling runs, ASan clean;
    OpenFOAM cavity3D 1M/8M with `FOAM_SIGFPE=true`: voxel values identical to `dev`.
* All ESPRESO changes are in the `src/espreso` working tree. `scripts/build_mesio.sh` builds the
  tree as it is; it does not apply patches any more (it only reports that the former
  `scripts/patches/*.patch` are already contained or superseded; the directory is obsolete).

## 2. Files, environment, build

| What | Path |
|---|---|
| Environment (modules, paths, HOME redirect) | `scripts/env_mesio.sh` |
| OpenVDB + TBB + Blosc build | `scripts/build_openvdb.sh` (log `build/logs/build_openvdb.log`) |
| Mesio build (waf) of the working tree | `scripts/build_mesio.sh` (log `build/logs/build_mesio[_<variant>].log`) |
| Former patches (obsolete, contained in the tree) | `scripts/patches/*.patch` |
| In-situ API header | `install/mesio/include/mesio_insitu.h` (source `src/espreso/include/mesio_insitu.h`) |
| In-situ test driver, build and test scripts | `data/mesio_tests/{insitu_driver.cpp,build.sh,run_tests.sh,run_writer_tests.sh,run_robustness_tests.sh}` |
| File-based test (OpenFOAM case, then `mesio`) | `scripts/make_mesio_testcase.sh`, `scripts/run_mesio_test.sh <np>`, `scripts/mesio_test.ecf` |
| Voxel-by-voxel VDB comparison | `scripts/tools/vdb_diff.cpp` (binary `build/tools/vdb_diff`) |
| OpenVDB install | `install/openvdb/{include,lib,bin/vdb_print}` |
| Mesio install | `install/mesio/{lib64,bin,include}` (production), `install/mesio-dev/...` (dev), `install/mesio-next/...` (next, API 2), `install/mesio-asan-next/...` (AddressSanitizer) |
| waf build tree | `build/espreso[-<variant>]` (the waf lock file stays in `src/espreso`: build one variant at a time) |

Build (always on the compute node):

```bash
srun --jobid=5270670 --overlap -N1 -n1 -c 64 -w cn357 bash scripts/build_openvdb.sh > build/logs/build_openvdb.log 2>&1
# production (install/mesio) -- do not rebuild while production runs use it
srun --jobid=5270670 --overlap -N1 -n1 -c 32 -w cn357 bash scripts/build_mesio.sh   > build/logs/build_mesio.log   2>&1
# development variant (install/mesio-dev, build/espreso-dev)
srun --jobid=5270670 --overlap -N1 -n1 -c 64 -w cn357 bash -c 'MESIO_VARIANT=dev NPROC=64 bash scripts/build_mesio.sh' > build/logs/build_mesio_dev.log 2>&1
# AddressSanitizer variant (install/mesio-asan), see Section 8
srun ... bash -c 'MESIO_VARIANT=asan MODE=devel CXXFLAGS_EXTRA="-fsanitize=address -fno-omit-frame-pointer" LINKFLAGS=-fsanitize=address bash scripts/build_mesio.sh'
# next variant (install/mesio-next, build/espreso-next) and its ASan twin, Section 10
srun --jobid=5275975 --overlap -N1 -n1 -c 64 -w cn317 bash -c 'MESIO_VARIANT=next NPROC=64 bash scripts/build_mesio.sh' > build/logs/build_mesio_next.log 2>&1
srun --jobid=5275975 --overlap -N1 -n1 -c 64 -w cn317 bash -c 'MESIO_VARIANT=asan-next MODE=devel NPROC=64 CXXFLAGS_EXTRA="-fsanitize=address -fno-omit-frame-pointer" LINKFLAGS=-fsanitize=address bash scripts/build_mesio.sh' > build/logs/build_mesio_asan_next.log 2>&1
```

What `build_mesio.sh` does:
1. Checks that the in-situ API is in the working tree and reports the state of the former patches
   (nothing is applied).
2. Runs `waf configure --out=build/espreso[-<variant>] --prefix=install/mesio[-<variant>]
   --mode=${MODE:-release} --intwidth=32 --cxx=g++ --mpicxx=mpic++` (plus `--cxxflags` from
   `CXXFLAGS_EXTRA`).
3. Runs `waf build install` (waf removes an installed file before copying the new one, so
   running processes keep their mapped libraries).
4. Copies `include/mesio.h` and `include/mesio_insitu.h` into the install tree.

`MESIO_VARIANT` is evaluated in `scripts/env_mesio.sh` (`MESIO_ROOT`, `ESPRESO_BUILD`); the
default (empty) is the production install.

The waf OpenVDB check (`src/wrappers/openvdb/wscript`) ignores `--openvdb=`, so `env_mesio.sh`
exports `CPATH`/`LIBRARY_PATH` pointing to `install/openvdb`. Only MPI, pthread and OpenVDB are
enabled; this avoids clashes with OpenFOAM's scotch/metis. `--intwidth=32` makes `esint=int`,
which must match OpenFOAM `label` (`WM_LABEL_SIZE=32`).

### Compile and link flags (e.g. OpenFOAM `Make/options`)

```make
EXE_INC  = -I$(MESIO_ROOT)/include -DMESIO_INT_WIDTH=32
LIB_LIBS = -L$(MESIO_ROOT)/lib64 -Wl,-rpath,$(MESIO_ROOT)/lib64 \
           -Wl,-rpath,$(OPENVDB_ROOT)/lib -Wl,-rpath-link,$(OPENVDB_ROOT)/lib \
           -lmesioapi
# MESIO_ROOT   = /mnt/proj2/eu-25-121/milanjaros/openfoam/install/mesio
# OPENVDB_ROOT = /mnt/proj2/eu-25-121/milanjaros/openfoam/install/openvdb
```

`libmesioapi.so` has `DT_NEEDED` entries for all `libnb*.so` libraries. Those libraries use
OpenMP (libgomp) and link `libopenvdb.so.12.0`, `libtbb.so.12` and `libblosc.so.1` from
`install/openvdb/lib`. The C header exposes no ESPRESO internals (no `esint` macros).

## 3. Source changes (working tree of `src/espreso`, branch `mjar/devel`)

The first three rows were the former patches (`scripts/patches/`, no longer applied); the
next two rows are the changes of 2026-10-26 evening, the last rows those of the `next`
variant (2026-10-26 night, Section 10).

| Change | Files | Purpose |
|---|---|---|
| `espreso-sc22-openvdb-store-balanced.patch` | `src/output/visualization/openvdb.cpp` | Commit 81b0aed4 sent the BALANCED path to the WIP `storeHierarchical()`, which `printf`s every voxel and writes only the first variable. The patch restores `storeBalanced()`. |
| `espreso-sc22-fix-elements-to-nodes-mpi.patch` | `src/input/builders/variables.cpp` | **Bug fix.** On more than 1 rank, the cell-to-point conversion produced wrong values at interface points (a constant 1 became 0.58 to 1.91). The cause: `nodes->elements` from `linkNodesAndElements(...,true)` is wrong for FVM-built meshes. The fix uses local connectivity only and exchanges `(count, partial sums)` of shared points sorted by global ID. |
| `espreso-sc22-insitu-api.patch` | new: `include/mesio_insitu.h`, `src/api/wrapper.mesio.insitu.cpp`, `src/input/parsers/memory/memoryfvm.{h,cpp}`; modified: `wscript`, `src/config/ecf/output.{h,cpp}`, `src/mesh/preprocessing/volume.cpp`, `src/mesh/mesh.cpp`, `src/wrappers/openvdb/w.openvdb.{h,cpp}` | The in-situ API (details below). |
| segfault fix | `src/mesh/mesh.cpp`, `src/mesh/preprocessing/pure.cpp`, `src/input/builders/variables.cpp` | `Mesh::preprocess` no longer calls `linkNodesAndElements(..., true)` (out-of-bounds read, Section 8); `linkNodesAndElements` fails with an error instead of reading out of bounds; bounds check in the element-to-node exchange. |
| distributed VDB writer | `src/api/wrapper.mesio.insitu.cpp`, `include/mesio_insitu.h`, `src/wrappers/openvdb/w.openvdb.{h,cpp}` | Leaf nodes built, merged and compressed on all ranks; writer options and detailed timings in the API (Section 9). |
| FPE fix (next) | `src/mesh/preprocessing/volume.cpp`, `src/mesh/preprocessing/meshpreprocessing.h`, `src/mesh/utils.h`, `src/input/builders/merging.cpp` | Inside test: no normalization of zero-length vectors (voxel centre on a mesh point, the wind-farm SIGFPE); grid computation `computeVolumeGrid` validates box/voxel size without overflowing divisions; guarded face normals and interpolation weights (Section 10.1). |
| voxelization speed-up (next) | `src/mesh/preprocessing/volume.cpp` | Exact pre-tests (outside the element bounding box, inside the element kernel) before the solid angle: setup and moving-mesh re-voxelization several times faster, identical voxels (Section 10.5). |
| error handling (next) | `src/esinfo/eslog.{h,cpp}`, `src/api/wrapper.mesio.insitu.cpp`, `include/mesio_insitu.h` | `eslog::errorHandler` hook: during API calls `globalerror` throws instead of `exit`; error codes and `MESIOInSituLastError`, consistent on all ranks (Section 10.2). |
| API 2 (next) | `include/mesio_insitu.h`, `src/api/wrapper.mesio.insitu.cpp`, `src/input/parsers/memory/memoryfvm.{h,cpp}`, `src/wrappers/openvdb/w.openvdb.{h,cpp}` | Several contexts, empty ranks, input validation, `ResetMesh`, `cell` sampling, field metadata, memory statistics (Section 10). |
| empty processes (next) | `src/mesh/mesh.{h,cpp}`, `src/input/builders/filler.cpp`, `src/mesh/preprocessing/clustered.cpp` | A small mesh on many ranks (e.g. 8000 cells on 256 ranks) leaves ranks without elements after the SFC redistribution: segfault in `outputOffset` (also in dev), now handled; `Mesh::allowEmptyProcesses` (set by the API) skips the "process without any elements" stop. |
| `-Wall` warnings (next) | `src/mesh/mesh.cpp` (`Mesh::load`), `src/input/builders/filler.cpp` (`fillNodes`) | `input` initialized, `default:` in the format switch, error for unsupported formats; no `std::merge` of a single `int` (`-Warray-bounds`). |

Details of the in-situ API patch:
* **API and input:** the C API, plus `InputMemoryFVM`, the OpenFOAM polyMesh reader pipeline
  fed from memory instead of files.
* **New ECF options:** `OUTPUT.VOLUME_VOXEL_SIZE`, `OUTPUT.VOLUME_BOX` and
  `VOLUME_BOX_{MIN,MAX}_{X,Y,Z}`.
* **Voxelization (`volume.cpp`):**
  * supports a voxel size and a sub-box;
  * clamps element bounding boxes to the grid;
  * uses a round-off-safe grid size;
  * takes the bounding box from the current coordinates, so moving meshes work.
* **Removed:** a duplicated voxelization call in `Mesh::computePersistentParameters`.
* **OpenVDB wrapper:**
  * `GRID_FOG_VOLUME` instead of level set;
  * index-to-world translation = centre of voxel 0, which removes the old −½ voxel shift;
  * `openvdb::initialize()` is called once;
  * cached accessor for inserts;
  * per-grid metadata (`time`) and an active-voxel count.

  These wrapper changes also apply to the file-based `mesio` OpenVDB output.

`git status` in `src/espreso` shows exactly these 22 paths as modified or new (complete list and
commit split in `docs/REPOSITORIES_TODO.md`, Section 1). Build by-products in the source tree
are `.lock-waf_linux_build` and `.waf3-2.0.27-*/` (waf); they are ignored by the repository's
`.gitignore` (pattern `.*`).

## 4. File-based test (OpenFOAM case, then `mesio`)

* Case: `/scratch/project/eu-25-121/milanjaros/openfoam/runs/mesio_test/cavity3d`. It is a 24³
  hex cavity solved with icoFoam, decomposed into 4, with 5 time steps.
* Run: `bash scripts/run_mesio_test.sh {1,4}`. Output goes to
  `runs/mesio_test/np{1,4}/last/PREPOSTDATA/mesio.000N.vdb`. Each file holds `p_in_nodes` and
  `U_in_nodes` (|U|) on a 48³ grid.
* Result: np1 and np4 are bitwise identical in all steps.
* Limitation: the OpenFOAM file reader works only for decomposed cases (`processor*`).

## 5. In-situ test (`data/mesio_tests`)

`bash data/mesio_tests/run_tests.sh` (from the login node; the work runs in the job on cn357).

**What the driver does** (`insitu_driver.cpp`):
* Calls `MPI_Init`, so the thread level is SINGLE, as in OpenFOAM.
* Builds a 40×20×10 hex mesh of [0,1]×[0,0.5]×[0,0.25] in the OpenFOAM layout:
  * block-decomposed 1×1 or 2×2;
  * internal faces first;
  * processor faces passed as boundary faces;
  * points duplicated on interfaces.
* Writes three fields:
  * `linear` = x+2y+3z+step;
  * `blob`, a moving Gaussian;
  * `vel`, dimension 3, written as its magnitude.
* On rank 0 it re-reads every file with OpenVDB and checks:
  * the grid class is fog volume;
  * the `time` metadata is present;
  * all active voxels lie in the domain or box;
  * for interior voxels, `linear(indexToWorld(ijk))` matches the analytic value.

| Case | Grid | Result (1 and 4 ranks) |
|---|---|---|
| `base`: voxel 0.01, 3 steps | 101×51×26, origin (0,0,0) | 128,054 active voxels; max error of `linear` at world positions 6e-6 (float); np1 vs np4 max \|diff\| 7e-6, 0 voxels above 1e-5 relative |
| `box`: voxel 0.005, box [0.2,0.7]×[0.1,0.4]×[0.05,0.2] | 101×61×31, origin = box min | 190,991 voxels, all inside the box, error 6e-6, np1 = np4 within 1e-5 |
| `move`: `movingMesh=1`, mesh shifted 1 cell per step | re-voxelized each write | error 6e-6 in moved world coordinates, np1 = np4 within 1e-5 |

Why the in-situ outputs are not bitwise identical: voxel centres that lie exactly on cell
faces, which happens because the test grid is aligned with the mesh, are claimed by two cells.
The cell that wins depends on the decomposition, so interpolation round-off differs (~1e-6).
Write timings on 4 ranks (130k voxels, 3 grids) are about 0.02 s convert, 0.02 s pack,
0.005 s gather and 0.04 s write; commit takes about 0.2 s.

**Rendering:**
`data/cyclesphi/render_vdb_series.sh '<out>/base_np4/step_*.vdb' blob <renders>/mesio_insitu 960x540 32`
with `SCENE_ARGS="--range 0 1 --colormap inferno --density 8 --alpha-min 0.05 --azimuth 35 --elevation 25 --up z"`.
This produced `/scratch/project/eu-25-121/milanjaros/openfoam/renders/mesio_insitu/step_000{0,1,2}.png`
(the earlier run of this command used the `np4` output, which is identical). They show the blob
moving across the box, and the world bbox read by CyclesPhi is [-0.005, 1.005] = voxel centres
± ½ voxel, as expected.

## 6. In-situ API (`include/mesio_insitu.h`, in `libmesioapi.so`)

```c
typedef struct MESIOInSituData* MESIOInSitu;
typedef struct {
    int    density;      /* voxels along the longest box edge (if voxelSize <= 0), default 100 */
    double voxelSize;    /* > 0: voxel size in world units */
    int    useBox;       /* 1: voxelize only [boxMin, boxMax]; 0: global mesh bbox */
    double boxMin[3], boxMax[3];
    int    movingMesh;   /* 1: UpdatePoints allowed (re-voxelization at each write) */
    int    writerRank;   /* rank writing the file, default 0 */
    int    verbosity;    /* 0 quiet, 1 progress on rank 0 */
} MESIOInSituSettings;

void MESIOInSituDefaultSettings(MESIOInSituSettings *s);
int  MESIOInSituCreate(MESIOInSitu *ctx, MPI_Comm comm, const MESIOInSituSettings *s);   /* collective */
int  MESIOInSituSetFVMesh(MESIOInSitu ctx, MESIOInt nPoints, const MESIOReal *points,
        MESIOInt nFaces, const MESIOInt *faceOffsets, const MESIOInt *faceNodes,
        const MESIOInt *owner, MESIOInt nInternalFaces, const MESIOInt *neighbour,
        MESIOInt nCells);                                                               /* local, once */
int  MESIOInSituAddCellField(MESIOInSitu ctx, const char *name, int dimension);       /* 1 (or 3 = magnitude) */
int  MESIOInSituCommit(MESIOInSitu ctx);                                               /* collective, once */
int  MESIOInSituSetCellField(MESIOInSitu ctx, const char *name, const MESIOReal *values); /* local */
int  MESIOInSituWriteVDB(MESIOInSitu ctx, double time, const char *filename);          /* collective */
int  MESIOInSituUpdatePoints(MESIOInSitu ctx, const MESIOReal *points);                /* local, movingMesh */
int  MESIOInSituGridInfo(MESIOInSitu ctx, int dims[3], double origin[3], double *voxelSize);
int  MESIOInSituLastWriteStats(MESIOInSitu ctx, double seconds[4], long long *activeVoxels, long long *fileBytes);
void MESIOInSituDestroy(MESIOInSitu ctx);                                              /* collective, before MPI_Finalize */

/* new (2026-10-26 evening, MESIO_INSITU_HAS_WRITER_OPTIONS; MESIOInSituSettings is unchanged = ABI compatible) */
int  MESIOInSituSetWriterOptions(MESIOInSitu ctx, int writer, int compression);       /* same values on all ranks */
     /* writer: MESIO_INSITU_WRITER_DISTRIBUTED (default) | _PARALLEL | _SINGLE (legacy)
        compression: MESIO_INSITU_COMPRESSION_BLOSC (default) | _NONE
        defaults also from the environment: MESIO_VDB_WRITER, MESIO_VDB_COMPRESSION (read in Create) */
int  MESIOInSituLastWriteTimings(MESIOInSitu ctx, double seconds[MESIO_INSITU_TIMINGS]);
     /* rank-local: CONVERT PLAN SAMPLE EXCHANGE MERGE GATHER WRITE TOTAL (MESIO_INSITU_TIME_*) */
```

API version 2 (`MESIO_INSITU_VERSION 2`, `next` variant, ABI compatible: the settings struct and
all old functions are unchanged; Section 10):

```c
#define MESIO_INSITU_OK 0, MESIO_INSITU_ERROR_ARGUMENT 1, _MESIO 2, _IO 3, _STATE 4
const char* MESIOInSituLastError(MESIOInSitu ctx);          /* ctx NULL: error of Create */
int  MESIOInSituResetMesh(MESIOInSitu ctx);                  /* collective: topology change */
int  MESIOInSituSetSampling(MESIOInSitu ctx, int sampling);  /* MESIO_INSITU_SAMPLING_CELLPOINT | _CELL */
int  MESIOInSituSetFieldMetadata(MESIOInSitu ctx, const char *field, const char *key, const char *value);
int  MESIOInSituLastWriteMemory(MESIOInSitu ctx, long long bytes[MESIO_INSITU_MEMORY]); /* RSS PEAK BUFFERS */
int  MESIOInSituSetMemoryTracking(MESIOInSitu ctx, int enable); /* per-write peak RSS (resets VmHWM) */
```

All functions return `MESIO_INSITU_OK` (0) or an error code; `MESIOInSituLastError` gives the
message. Collective calls (Create, Commit, ResetMesh, WriteVDB) return the same code and message
on all ranks; MESIO never calls `exit` (dev and older: fatal errors called `MPI_Finalize` and
`exit`). Details in Section 10.2.

### Semantics

* **MPI:** the caller initializes MPI. `Create` duplicates `comm`, and MESIO runs all its
  communication on the duplicate. Any thread level works: the writer is synchronous and uses
  no threads (MPI is called from the calling thread only). API 2: several contexts per process
  (each has its own set of ESPRESO globals, activated at every call; calls must not run
  concurrently). Before (dev): one context per process.
* **Mesh input:**
  * Each rank passes its local OpenFOAM polyMesh as is: `points` (xyz, `mesh.points()`), faces as
    CSR (`faceOffsets[nFaces+1]`, `faceNodes`), `owner[nFaces]` and
    `neighbour[nInternalFaces]` (internal faces first).
  * Processor-patch faces are normal boundary faces (owner only), so no processor patch
    information is needed. Points duplicated on processor boundaries are merged geometrically
    (SFC plus duplicate search, as in the OpenFOAM reader).
  * Any polyhedra are allowed. The data is copied and validated (indices, finite coordinates).
    API 2: a rank may pass an empty mesh (the whole mesh needs at least as many cells as
    ranks), and ranks left without cells by MESIO's Hilbert redistribution (small meshes on
    many ranks) are handled; dev: every rank needs a cell, and e.g. 8000 cells on 256 ranks
    segfault in the builder (`outputOffset`).
* **Commit:**
  * MESIO redistributes the mesh along a Hilbert curve; its partition is not OpenFOAM's.
  * It voxelizes once. Voxel centres are tested for being inside cells: a convex test for tets,
    a solid-angle test for other cells.
  * Grid: the voxel size is `voxelSize`, or `1.0001*max(box extent)/density`, and voxels are
    cubic. The number of voxels per axis is `floor(extent/h)+1`, at most 32767. The grid is
    centred on the box (or on the global mesh bbox). API 2 checks the grid before the mesh is
    built (Create for a box, Commit for the bbox); a zero-extent box needs a `voxelSize`
    (it gives one voxel layer, a point box one voxel).
* **Per step:**
  * Call `SetCellField` for each field (values in the local cell order; dimension 3 is
    interleaved xyz), then `WriteVDB`. The mesh structures are reused; there is no rebuild.
  * `WriteVDB`, step by step:
    1. Redistributes the values: an all-to-all exchange, the mapping is computed once.
    2. Averages cell values to points across ranks.
    3. Interpolates inside each cell at voxel centres (static meshes: the interpolation
       weights are stored at the first write and reused). With `cell` sampling (API 2) the
       voxel gets the value of the cell containing its centre instead.
    4. Distributed writer (default, Section 9): stores the values directly in OpenVDB leaf
       nodes (8^3 voxels), sends partial leaves to their owner ranks, which merge and
       serialize/compress them; the writer rank writes the file from the received records.
       Single writer (legacy): packs the active voxels (bit-packed coordinates plus float
       values) and sends them to `writerRank`, which builds `openvdb::FloatGrid`s.
    5. Writes `<filename>.tmp` and renames it to `<filename>`; the parent directories are
       created.
    6. Returns on all ranks after the file is complete (status is broadcast).
* **Output file:**
  * One FloatGrid per field, with grid name = field name, class `GRID_FOG_VOLUME`,
    background 0, grid metadata `time`, the string metadata of `SetFieldMetadata` (API 2,
    e.g. `units`), and blosc compression. Values are clamped to the float range.
  * Active voxels are those whose centre lies inside the mesh (and the box).
  * Index-to-world is linear: `world(ijk) = origin + ijk*h`, where `origin` is the centre of
    voxel (0,0,0), as reported by `GridInfo`.
  * Vector fields are written as their magnitude. For CyclesPhi, pass scalars such as `U_mag`.
* **Moving mesh:**
  * With `movingMesh=1`, `UpdatePoints` takes new coordinates in the original local point order.
  * At the next write, the coordinates are redistributed and the grid is recomputed; with the
    default bbox mode, the grid follows the mesh.
  * The re-voxelization costs about 0.6 s on 1 rank for 8k cells in the test.
  * Topology changes: API 2 `MESIOInSituResetMesh` + `SetFVMesh` + `Commit` rebuild the mesh in
    the existing context (fields, options, communicators kept); dev: destroy and re-create.

### OpenFOAM side (function object sketch)

```cpp
// once (and again after topology changes): mesh + fields
const fvMesh& mesh = ...;
const pointField& P = mesh.points();
const faceList& F = mesh.faces();
labelList off(F.size() + 1, 0); DynamicList<label> fn;
forAll(F, f) { off[f + 1] = off[f] + F[f].size(); fn.append(F[f]); }
MESIOInSituSettings s; MESIOInSituDefaultSettings(&s); s.voxelSize = h; // or s.density, s.useBox...
MESIOInSituCreate(&ctx, PstreamGlobals::MPICommunicators_[UPstream::worldComm] /* or MPI_COMM_WORLD */, &s);
MESIOInSituSetFVMesh(ctx, P.size(), &P[0].x(), F.size(), off.cdata(), fn.cdata(),
                     mesh.faceOwner().cdata(), mesh.nInternalFaces(),
                     mesh.faceNeighbour().cdata(), mesh.nCells());
for (const word& name : fields_) MESIOInSituAddCellField(ctx, name.c_str(), 1);
MESIOInSituCommit(ctx);
// write(): for every field
MESIOInSituSetCellField(ctx, "p", p.primitiveField().cdata());
volScalarField Umag(mag(U));  MESIOInSituSetCellField(ctx, "U_mag", Umag.primitiveField().cdata());
MESIOInSituWriteVDB(ctx, mesh.time().value(), (outputDir/(mesh.time().timeName() + ".vdb")).c_str());
// destructor (before MPI_Finalize):
MESIOInSituDestroy(ctx);
```

## 7. Remaining issues and limitations

* **Value semantics:** `cellPoint` (default): cell → point averages, interpolated inside the
  cell; boundary cells are smoothed by the point averaging. `cell` sampling (API 2) writes exact
  cell values (piecewise constant, staircase at the voxel scale). There is no conservative
  resampling.
* **No bitwise reproducibility across decompositions:** voxels on cell faces get round-off-level
  differences (~1e-6 relative).
* **Writer rank memory:** distributed writer: the topology tree (~2.1 KB per leaf of 512
  voxels) plus the received file content; legacy single writer: the packed voxels of all ranks
  (about `voxels*(4*nFields+1)` bytes) plus the OpenVDB trees. Messages are split into 1 GB
  chunks (no 2 GB limit any more). Measured values: Section 10.5 (`MESIOInSituLastWriteMemory`).
* **File write bandwidth:** one client writes about 0.9 GB/s to `/scratch` (dd, independent of
  striping); for large files this is the remaining cost of an export (Section 9).
* **Errors** (API 2): returned as codes, consistent on all ranks. Not recoverable: an error that
  only some ranks detect while all ranks are inside MESIO's collective communication (memory
  exhaustion, a broken mesh that passes the input validation, an internal error); MESIO prints
  it and calls `MPI_Abort` instead of deadlocking (OpenFOAM's FatalError does the same in
  parallel). dev and older: every fatal error called `MPI_Finalize` and `exit`.
* **`linkNodesAndElements(..., true)`** assumes ESPRESO's clusterized node order and does not
  work for FVM-built meshes; it is no longer called from `Mesh::preprocess` (Section 8) and now
  stops with an error if its assumption fails. `nodes->elements` is therefore not available
  for FVM meshes (no Mesio/in-situ code uses it).
* **The voxel-inside test cost** grows with cells × voxels per cell bbox. Moving meshes pay it
  at every write.
* **Not supported:** tensor fields, point fields, surface fields and multiple regions (API 2: one
  context per region is possible, but untested).
* **Legacy file-based `mesio` output:** it still names grids `<field>_in_nodes`, writes into
  `<out>/<date>/PREPOSTDATA`, and its FILTERED path needs `MPI_THREAD_MULTIPLE`. The in-situ
  API does not use that writer.

## 8. Segfault in `MESIOInSituCommit` (fixed 2026-10-26)

**Symptom:** intermittent `SIGSEGV` at the first export, in
`espreso::mesh::linkNodesAndElements` (`pure.cpp:124-125`) <- `Mesh::preprocess` <-
`MESIOInSituCommit`, on 1-2 ranks (motorbike 512 ranks: 1 of 5 runs, pitzDaily 62M 2048 ranks:
5 of 5, cavity3D 8M 512 ranks: seen too). Logs:
`runs/HPC_motorbike/Small/logs_vis/log.vis.prod2b`, `runs/pitzDaily3D/62M/logs_vis/log.vis.test1`.

**Cause** (confirmed with AddressSanitizer, `install/mesio-asan`, driver on 4 ranks):
`Mesh::preprocess` called `linkNodesAndElements(elements, nodes, neighbors, true)` because the
in-situ path sets `convert_variables_to_nodes`. With `clusterizedNodes = true` the function
assumes that the nodes are ordered in groups by their lowest holder rank (ESPRESO's own
clustered builder). The FVM/Hilbert builder (`InputMemoryFVM`, also the OpenFOAM file reader)
orders nodes by global offset, so the number of node groups exceeds `neighbors.size() + 2`
and the loop `sBuffer[r].push_back(neighbors[g])` reads past the end of `neighbors`:

```
ERROR: AddressSanitizer: heap-buffer-overflow ... READ of size 4
  #3 espreso::mesh::linkNodesAndElements(...) src/mesh/preprocessing/pure.cpp:125
  #4 espreso::Mesh::preprocess() src/mesh/mesh.cpp:270
  #5 MESIOInSituCommit src/api/wrapper.mesio.insitu.cpp:197
```

The out-of-bounds read happens on every multi-rank run; it crashes only if it reaches an
unmapped page (depends on heap layout, more likely with more ranks), hence intermittent. The
result (`nodes->elements`) was also wrong (see the cell-to-point fix in Section 3), and since
that fix nothing in the Mesio/in-situ path uses it.

**Fix:** the call is removed from `Mesh::preprocess` (the element-to-node conversion uses local
connectivity and `nodes->ranks` only); `linkNodesAndElements` stops with an internal error
instead of reading out of bounds if the ordering assumption fails; the element-to-node exchange
checks that every sharing rank is a neighbour. The API/ABI is unchanged (the production
`libmesioFoam.so` also works with the fixed libraries).

**Verification:** ASan build (`MESIO_VARIANT=asan`, driver built with `-fsanitize=address`,
run with `LD_PRELOAD=libasan.so` and `OMPI_MCA_pml=ob1 OMPI_MCA_btl=self,vader`, because ASan
and the UCX memory hooks conflict): before the fix every multi-rank run reports the overflow;
after the fix 4, 16, 64 (box, ranks without voxels), 128 ranks, repeated setups
(`--setups 2`), moving mesh, both writers: no ASan error. icoFoam cavity3D 8M on 256 ranks
with the fixed build: all 16 runs (dev/wip builds, writers single/distributed/parallel,
32.8 M and 128 M voxels) reach `End`.

## 9. Distributed VDB writer (2026-10-26)

### Profile of the legacy single writer

cavity3D 8M, 256 ranks (cn356+cn357), 3 grids (`U_mag p Q`), 32.8 M voxels, per export
(`MESIO_VDB_WRITER=single`, phases from `MESIOInSituLastWriteTimings`):

| Phase (legacy) | Time |
|---|---|
| sampling + bit packing (max over ranks) | 0.07 s |
| gather of packed voxels to the writer | 0.15-0.6 s |
| OpenVDB tree build on the writer (unpack + `accessor.setValue` per voxel and grid) | 3.1 s |
| file write with blosc (`openvdb::io::File`, compresses every leaf twice: delayed-load sizes + data) | 3.65 s |
| file write without compression | 1.35 s |
| **total** | **7.0 s** |

### Design (option B of the integration proposal)

* **Plan** (first write, again after each re-voxelization): every rank maps its sampled voxels
  to OpenVDB leaf nodes (8^3 voxels). Leaves are identified by a 36-bit key that sorts them in
  the order of `openvdb::FloatTree` (root -> internal 32^3 -> internal 16^3 -> leaf), which is
  the order of the leaf buffers in a file. The writer rank gathers (key, voxel count) pairs and
  splits the key range into contiguous owner ranges, one per rank, balanced by voxel count.
  Partial leaves (key, mask) are sent to their owners, which merge the masks; the owners send
  the merged masks to the writer rank, which builds the topology tree once (and its
  statistics metadata).
* **Per write:** sample directly into the local leaves (interpolation weights cached for static
  meshes) -> send the active values of each partial leaf to its owner (point-to-point) ->
  owners merge them **in ascending rank order** (a voxel sampled by several ranks/cells gets
  the value of the highest rank / last cell, exactly as in the single writer) -> owners
  serialize their leaves with `LeafNode::writeBuffers` (blosc) and compute the delayed-load
  metadata -> the writer rank receives the delayed-load metadata, then streams the records of
  every grid from all owners into the file while writing (header, grid descriptors, metadata,
  transform and topology are written by OpenVDB functions in a small `io::Archive` subclass
  that reproduces `Archive::write/writeGrid`).
* **Result:** the file is **byte-identical** to the one written by `openvdb::io::File` from
  the complete grids (legacy writer), except the random 16-byte UUID in the header (bytes
  22-57). Verified by `data/mesio_tests/run_writer_tests.sh` (1, 4, 16, 64 ranks incl. ranks
  without voxels, moving mesh, compression none, 256 ranks on 2 nodes with re-created
  contexts: 27 file comparisons) and by icoFoam cavity3D 8M (production build vs new build,
  all exports at 32.8 M and 128 M voxels identical).
* **Writer options** (API `MESIOInSituSetWriterOptions`, environment `MESIO_VDB_WRITER`,
  `MESIO_VDB_COMPRESSION`, function object keys `writer`, `compression`):
  `distributed` (default), `parallel` (as distributed, but one rank per node `pwrite`s the
  records of its node, a contiguous byte range per grid, into the same file; requires block
  rank placement), `single` (legacy); compression `blosc` (default) or `none`.
  `MESIO_VDB_TIMING=1` prints the skeleton/pwrite times of the parallel writer;
  `MESIO_VDB_WEIGHT_CACHE_MB` limits the interpolation-weight cache (default 1024 MB per rank,
  0 disables it).
* Threads: none; OpenVDB/TBB threading on the writer would not help in production because every
  rank is bound to one core (`--cpu-bind=cores`, 128 ranks per node).

### Benchmark (icoFoam cavity3D 8M, 256 ranks on cn356+cn357, 3 grids, export every 10 steps)

`scripts/tests/bench_mesioVDB_writer.sh <tag> <prod|dev> <density> [writer] [compression]`,
case `runs/mesio_dev/c3d8M_256` (blockMesh 200^3, scotch 256). Export time = wall time of
`mesioVDB::write` (max over ranks), mean of exports 2-4 (export 1 includes the plan: +0.2 s at
32.8 M, +0.9 s at 128 M voxels).

| Voxels | File | Old (production, single writer, blosc) | New distributed, blosc | New distributed, none | New parallel (2 nodes), blosc |
|---|---|---|---|---|---|
| 32.8 M (density 320) | 243-251 MB | 7.0 s (tree build 3.1 s + write 3.7 s) | **0.45 s** (sample 0.016, exchange 0.01, merge+compress 0.013, file 0.35) | 0.67 s (file 0.40 GB) | 0.59 s |
| 128 M (density 504) | 917 MB | 26.9 s | **1.5-1.8 s** (file 1.3-1.6 s) | - | 1.65-1.8 s |

Setup (context creation) is unchanged: 1.3-1.5 s at 32.8 M and 2.5 s at 128 M voxels.
At 128 M voxels the remaining cost is the single-client file write (917 MB at ~0.7 GB/s,
`dd` reaches 0.93 GB/s); the `parallel` writer did not help with 2 nodes (2 clients x
~0.45 GB/s, also with 8 OST stripes) but may help on more nodes (untested). Blosc reduces the
file by ~40 % here and is cheap when it runs on all ranks, so it stays the default.


## 10. Production hardening: the `next` variant (2026-10-26/27)

Install `install/mesio-next` (and `install/mesio-asan-next`), built from the `src/espreso`
working tree (22 paths, Section 3; commit split in `docs/REPOSITORIES_TODO.md` Section 1),
in-situ API version 2 (`MESIO_INSITU_VERSION 2`). The API stays ABI compatible (old function
objects run with the new libraries); the current mesioVDB sources require version 2. Function
object: `install/openfoam-modules-mesio-next/lib`, launcher `scripts/cases/ofexec_vis_mesionext.sh`
(`docs/notes/mesio_openfoam_functionobject.md` Sections 3.1 and 11).

```bash
# build (compute node; one waf build at a time: the lock file is in src/espreso)
srun --jobid=5275975 --overlap -N1 -n1 -c 64 -w cn317 bash -c 'MESIO_VARIANT=next NPROC=64 bash scripts/build_mesio.sh' > build/logs/build_mesio_next.log 2>&1
srun --jobid=5275975 --overlap -N1 -n1 -c 16 -w cn318 bash -c 'MESIO_VARIANT=next bash scripts/build_mesio_openfoam.sh' > build/logs/mesio_openfoam_build_next.log 2>&1
# tests (login node; the work runs in the job)
MESIO_VARIANT=next JOB=5275975 NODES=cn317,cn318 NPS="4 16 64 256" EXTRA_ARGS=--fpe bash data/mesio_tests/run_tests.sh
MESIO_VARIANT=next JOB=5275975 NODES=cn317,cn318 EXTRA_ARGS=--fpe bash data/mesio_tests/run_writer_tests.sh
MESIO_VARIANT=next REF_VARIANT=dev REF_DRIVER=$PWD/build/mesio_tests/insitu_driver-devref bash data/mesio_tests/run_robustness_tests.sh
MESIO_VARIANT=asan-next ASAN=1 bash data/mesio_tests/run_robustness_tests.sh   # driver: DRIVER_FLAGS=-fsanitize=address
```

### 10.1 Floating-point exceptions (the wind-farm SIGFPE)

**Cause.** The voxel inside test (`computeVolumeIndices`, solid angle of the face triangles)
normalized the vectors from the voxel centre to the triangle vertices in single precision.
When a voxel centre coincides with a mesh point the vector has length 0 and `normalize()`
computes `1.0f/0` (FE_DIVBYZERO, SIGFPE with OpenFOAM's `FOAM_SIGFPE`); without trapping the
angle became NaN, and the NaN test classified the voxel as inside. This happens whenever the
grid is aligned with the mesh: wind farm `box (2.70 0.005 0.0) ...`, `voxelSize 0.005`, cells
of 16.7 x 16.7 x 8 mm (every third mesh plane carries voxel centres), the cavity3D cases with a
box starting at a mesh plane and `h = cell/2`, and the driver's base case (voxel 0.01, cells
0.025). It is not specific to ranks outside the box (the earlier note); in the reproductions
every rank with such a voxel trapped.

**Reproduction with dev:** driver `--fpe` (4 ranks): SIGFPE in `computeVolumeIndices` <-
`Mesh::preprocess` <- `MESIOInSituCommit`; icoFoam cavity3D 1M (128 ranks) and 8M (256 ranks)
with `FOAM_SIGFPE=true` and an aligned box: the same stack as the wind-farm log on all ranks.

**Fix (next):**
* `solid_angle`: a zero-length vector (voxel centre on a triangle vertex) is reported, the
  voxel is inside (the former NaN result), no division.
* `computeVolumeGrid` (new, `meshpreprocessing.h`): box and voxel size are validated
  (finite, min <= max, zero extent only with a voxel size) and the grid size is checked
  without an overflowing division (tiny voxel sizes); used by `computeVolumeIndices` and by
  the API before the mesh is built.
* `mesh/utils.h`: zero-area face normals are 0 instead of NaN; the product of the face
  distances of the interpolation weights is bounded below (underflow for nodes in very many
  faces).
* `rotateNormalsOut` (builder): the orientation test uses the sign of the unnormalized triple
  product (degenerate elements divided by zero).
* Sampled values are clamped to the float range (FE_OVERFLOW in the double -> float conversion
  of huge values).

**Audit:** every driver test runs with `feenableexcept(FE_DIVBYZERO | FE_INVALID |
FE_OVERFLOW)` (`--fpe`, as OpenFOAM's `sigFpe`): all writers (distributed, parallel, single),
compression blosc/none, 1-256 ranks, empty ranks, ranks without cells in the box, boxes
smaller than a cell, one voxel, zero thickness, outside the mesh, constant fields, moving mesh,
cell sampling, two contexts, ResetMesh, all error paths. OpenFOAM with `FOAM_SIGFPE=true`:
cavity tutorial (serial, 4 ranks, both samplings), cavity3D 1M (128 ranks) and 8M (256 ranks)
with aligned partial boxes, all writers, two instances, movingCone (moving mesh), dynamic
refinement (polyhedra, ResetMesh), wind farm on 256 ranks (Section 10.6). No trap remains.

### 10.2 Error handling

* `eslog` got an optional error handler (`eslog::errorHandler`). During an API call
  `eslog::globalerror` (called by all ranks) throws an exception that becomes
  `MESIO_INSITU_ERROR_MESIO` on all ranks. A local error inside a collective MESIO phase (an
  internal failure, memory exhaustion) cannot be reported consistently, because the other
  ranks wait in a collective operation; the rank prints it and calls `MPI_Abort` (no
  deadlock, no silent `exit`). OpenFOAM's FatalError does the same in parallel.
* Checks run before any collective MESIO phase, so all foreseeable errors are consistent:
  settings (finite, positive, writer rank, box, grid size; equal on all ranks), mesh input
  (counts, CSR offsets, index ranges, finite coordinates), at least one cell per rank in the
  whole mesh, grid size of the mesh bbox (Commit, before the mesh build), call order, unknown
  fields, file name, time.
* Codes: `OK 0`, `ERROR_ARGUMENT 1` (context unchanged), `ERROR_MESIO 2` (the context failed:
  only `ResetMesh` or `Destroy`), `ERROR_IO 3` (the file was not written, `.tmp` removed, the
  context stays usable), `ERROR_STATE 4` (call on a failed context).
* Collective calls agree on the result on a separate duplicate of the communicator: the code
  and message of the lowest failing rank are returned on all ranks
  (`MESIOInSituLastError`). Local calls return their error immediately and keep it as pending;
  the next collective call reports it on all ranks (e.g. an invalid mesh on one rank makes
  Commit fail everywhere with `rank 15: SetFVMesh: owner of face 0 is outside [0, nCells).`).
* Tested error paths (1, 4, 16 ranks, all with `--fpe`): grid too large (Commit, before the
  mesh build), zero-extent box with density (Create), settings differing between ranks
  (Create), invalid mesh on one rank (Commit), unknown field on one rank (WriteVDB), unwritable
  output (WriteVDB, `ERROR_IO`, the next write in the same context succeeds), moving mesh
  growing beyond 32767 voxels (`ERROR_MESIO` inside MESIO, then `ERROR_STATE`, recovery by
  ResetMesh). After every error the process creates a new context and writes a correct file.

### 10.3 Several contexts per process

ESPRESO keeps its state in globals (`info::mpi`, `info::ecf`, `info::mesh`, `MPITools` groups
and operations, `eslog::logger`). Every context now owns a complete set; the set of the
context passed to a call is activated at the beginning of the call (calls must not run
concurrently). The element definitions (`Mesh::edata`) are initialized once per process
(they were re-initialized and leaked at every Create). Each context duplicates the
communicator twice (MESIO, error agreement) plus the `MPITools` groups. Tested: two contexts
with different boxes/voxel sizes written alternately, all writers (driver), two mesioVDB
instances in icoFoam (cavity tutorial, cavity3D 8M on 256 ranks): the first instance's files
are voxel-identical to a run without the second instance.

### 10.4 Other additions

* **Empty ranks:** `SetFVMesh` with zero cells/faces/points (the whole mesh needs at least as
  many cells as ranks). Offsets are computed in Commit, so `SetFVMesh` is purely local now.
  Ranks that the SFC redistribution of a small mesh leaves without nodes/elements (e.g. the
  8000-cell driver mesh on 256 ranks; dev segfaults in `builder::outputOffset`) are handled:
  `outputOffset` and `computeBaseMeshInfo` accept empty ranges and the API sets
  `Mesh::allowEmptyProcesses`.
* **`MESIOInSituResetMesh`** (topology changes): drops the mesh and voxelization, keeps the
  communicators, settings, writer options, fields and metadata; then `SetFVMesh` + `Commit`.
* **`MESIOInSituSetSampling(..., MESIO_INSITU_SAMPLING_CELL)`**: the voxel gets the value of
  the (MESIO-local) cell that contains its centre, taken from the redistributed cell values
  before the point averaging; a voxel centre on a face gets one of the cells' values (the
  highest rank / last cell, as for the interpolated values). All writers (the single writer
  uses an unpacked transfer for cell values). Default unchanged (`cellPoint`).
* **`MESIOInSituSetFieldMetadata`**: string grid metadata per field (reserved OpenVDB/MESIO
  keys rejected), written by all writers.
* **`MESIOInSituLastWriteMemory`**: RSS before the write, peak RSS (per write with
  `MESIOInSituSetMemoryTracking(ctx, 1)` / `MESIO_VDB_MEMORY=1`, which resets the process
  VmHWM via `/proc/self/clear_refs`), and the largest amount of MESIO write buffers held at the
  same time on this rank.
* **Verbose timings:** with `verbosity 1` every MESIO progress line shows the time since the
  context creation and since the previous line.

* **Distributed writer, message order:** the small leaf metadata is now exchanged completely
  before the large record transfers to the writer rank are posted. With all transfers posted
  at once, Open MPI's ob1/vader transport (the configuration needed for ASan runs) stalled
  the metadata messages behind ~380 outstanding large transfers and the write hung at 128
  ranks (8 M voxels; UCX was not affected). Same data, same file.

### 10.5 Voxelization speed-up

Profile (`perf`, driver): the solid angle (`atan2f`, three normalizations per triangle, 24
triangles per hexahedron) was ~80 % of the setup; the candidate range of an element
(floor/ceil of its bounding box) also contains a layer of voxels outside the element. Two exact
pre-tests now classify most candidates before the solid angle: a voxel centre outside the
(epsilon-expanded) bounding box is outside; a voxel centre strictly on the same side of all
face-triangle planes lies in the kernel of the element and is inside. Only the remaining
voxels (near faces, non-convex cells) use the solid angle, computed exactly as before.
Results are byte-identical to dev in all comparisons (driver cases incl. moving mesh, slices,
tiny boxes; OpenFOAM cavity3D 1M/8M; voxel counts of movingCone and the refinement test).

| Case (ranks) | dev | next |
|---|---|---|
| driver, 64^3 cells, 262 k voxels (4) | 1.18 s | 0.40 s |
| driver, 64^3 cells, 2.1 M voxels (4) | 2.75 s | 0.42 s |
| icoFoam cavity3D 1M, aligned box, 0.72 M voxels (128) | 0.68 s | 0.38 s |
| icoFoam cavity3D 8M, aligned box, 7.7 M voxels (256) | 3.84 s | 1.87 s |
| icoFoam cavity3D 8M, whole mesh, 33 M voxels (256) | 1.67 s | 0.83 s |
| icoFoam cavity3D 8M, whole mesh, 126 M voxels (256) | 2.5 s (Section 9) | 1.65-1.99 s |
| dynamicRefineFvMesh rebuild after a topology change, 56-68 k cells, 2.1 M voxels (1) | 5.6-5.9 s | 0.67-0.73 s |
| the same (4) | 2.5-2.7 s (destroy + create) | 0.28-0.30 s (ResetMesh) |

Setup = Create + SetFVMesh + Commit (mesh build, redistribution, voxelization); the aligned
box keeps many voxel centres on faces, which still need the solid angle. Moving meshes
re-voxelize at every export and gain the same.

### 10.6 Test results

All with `--fpe` (driver) or `FOAM_SIGFPE=true` (OpenFOAM), final build, job 5275975;
logs under `runs/mesio_fix/` (`v3_verification.log` and the per-test directories).

| Test | Result |
|---|---|
| `run_robustness_tests.sh` (14 writer cases x 3 writers, 20 error runs) + byte comparison with dev for the 11 files of the cases the old API supports | all pass; 77 file comparisons identical (writers among themselves and next vs dev) |
| `run_tests.sh`, 1 vs 4, 16, 64, 256 ranks (base, box, moving mesh) | 15/15 runs pass; 1 vs N ranks: same active voxels, `linear`/`vel` equal within 1e-5, `blob` differs in at most 5 voxels per file by <= 1.8e-5 at 64/256 ranks (voxel centres on cell faces claimed by different cells; dev shows the same, e.g. 1.3e-5 at 64 ranks) |
| `run_writer_tests.sh` (6 cases up to 256 ranks on 2 nodes) | pass, files byte-identical between the writers |
| `run_robustness_tests.sh` with `ASAN=1` (`install/mesio-asan-next`, 62 runs) | no AddressSanitizer report, all pass, 66 file comparisons identical |
| driver 256 ranks with the 8000-cell mesh (ranks without cells after the redistribution) | pass, all writers identical (dev: segfault in `builder::outputOffset`) |
| distributed writer with Open MPI ob1/vader, 128 ranks, 8 M voxels | pass, identical to single/parallel (hung before the message-order fix) |
| icoFoam cavity3D 1M (128 ranks) / 8M (256 ranks), aligned partial box, 3 writers | End; writers byte-identical; voxel values identical to dev (dev with `FOAM_SIGFPE=true`: SIGFPE in `computeVolumeIndices`) |
| two mesioVDB instances (8M, 256 ranks) | both export; first instance identical to dev |
| dynamicRefineFvMesh (polyhedra, 1/4 ranks), movingCone (1/4 ranks) | End; np1 files voxel-identical to the earlier runs |
| `test_mesioVDB_errors.sh`, `test_mesioVDB_cavity.sh` (both samplings), `test_mesioVDB_reread.sh` | pass (Section 11 of the function-object notes) |

### 10.7 Writer-rank memory

`MESIOInSituLastWriteMemory` with memory tracking (peak RSS of the export), icoFoam cavity3D 8M
on 256 ranks, whole mesh, 3 grids (`U_mag p Q`), writer rank 0, second export:

| Voxels (file) | Writer | Export | Writer rank: RSS before -> peak during the export | MESIO buffers (writer) |
|---|---|---|---|---|
| 33 M (248 MB) | distributed | 0.46 s | 320 -> 728 MB | 383 MB |
| 33 M | single | 8.8 s | 325 -> 914 MB | 586 MB |
| 126 M (903 MB) | distributed | 1.53 s | 1814 -> 1854 MB (first export: 336 -> 1813 MB) | 1508 MB |
| 126 M | single | 36 s | 1893 -> 3043 MB | 2696 MB |

The writer rank has the maximum peak over all ranks in all cases. The
distributed writer needs ~40 % less memory on the writer rank than the single writer (it keeps
the topology tree, ~2 KB per leaf, and receives compressed records; the single writer holds the
packed voxels of all ranks plus the full OpenVDB grids). Between exports the writer keeps the
topology and the allocator keeps freed memory, so the RSS before the second export is close to
the peak of the first one. Rule of thumb for the writer rank: ~12 B per voxel (distributed,
3 grids, blosc) vs ~18-22 B per voxel (single).
