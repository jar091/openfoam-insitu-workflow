# ANARI-SDK + Barney build notes (CPU-only nodes, foss/2025b)

Status (2026-10-26): ANARI-SDK 0.17.0 and Barney 1.5.0 (Embree CPU backend, MPI)
are built and installed. Headless single-process and MPI data-parallel rendering
works on Karolina CPU nodes (AMD EPYC 7H12, no GPU). Tested on cn627/cn628.

## 1. Toolchain and environment

- Toolchain: `foss/2025b` (GCC 14.3.0, OpenMPI 5.0.8, MPI_THREAD_MULTIPLE available),
  `CMake/3.31.8-GCCcore-14.3.0`, `Python/3.13.5-GCCcore-14.3.0` (code generation).
  Same toolchain as OpenFOAM v2606, so the libraries can be linked into a function object.
- `source scripts/env_anari.sh`: loads modules, redirects `HOME`/`XDG_*` to
  `/scratch/project/eu-25-121/milanjaros/openfoam/fakehome`, sets `CMAKE_PREFIX_PATH`,
  `LD_LIBRARY_PATH`, `PATH` and the default `ANARI_LIBRARY=barney_cpu`.
- Builds run on a compute node (`srun --jobid=... --overlap -N1 -n1 -w cnXXX bash scripts/...`),
  logs in `build/logs/`.

## 2. ANARI-SDK (`src/ANARI-SDK`, branch mjar/devel @ 4238806, SDK 0.17.0)

- Script `scripts/build_anari.sh`: build dir `build/anari`, prefix `install/anari`
  (do not move it: other agents link against it).
- Options: `BUILD_HELIDE_DEVICE=ON BUILD_EXAMPLES=ON USE_MPI=ON BUILD_VIEWER=OFF
  BUILD_TESTING=OFF BUILD_HELIDE_GPU_DEVICE=OFF BUILD_REMOTE_DEVICE=OFF`.
  helide's Embree 4.3.3 is downloaded at configure time (compute nodes have internet).
- Installed: `lib64/libanari.so.0.17.0`, `libanari_library_{helide,debug,sink}.so`,
  `libanari_test_scenes.so`, `libhelium.a`, CMake package `lib64/cmake/anari-0.17.0`
  (`find_package(anari)` -> `anari::anari`, `anari::helium`),
  `bin/{anariInfo,anariTutorial,anariTutorialCpp,anariDistributedTutorial}`.

## 3. Barney (`src/barney`, branch mjar/devel)

### Source state: HEAD conflicts resolved in the working tree (uncommitted)
The branch HEAD `7f46b52 "update volume"` (merge of `5050e56` and `4d9b843`) contains
**committed, unresolved merge-conflict markers**. They are resolved in the `src/barney`
working tree (not committed, the user commits them to the fork); see section 3a.
`install/barney` was built earlier from a `git archive` snapshot of the clean commit
**`4d9b843` "fix embreePadding"** (`build/src_snapshots/barney-4d9b843`).
`scripts/build_barney.sh` now builds the **working tree by default**
(`BARNEY_COMMIT=<sha>` still builds a snapshot, `BARNEY_SRC=<dir>` any tree;
`BARNEY_PREFIX`/`BARNEY_BUILD_DIR` select install prefix/build dir,
`BARNEY_EXTRA_CMAKE_ARGS` adds CMake options; it refuses to build a tree with conflict
markers). Other local modifications: `git submodule update --init` for cuBQL, embree,
owl, and Embree's configure step rewriting
`submodules/embree/kernels/export.{linux,macosx}.map` for the `embree_for_barney` API
namespace (harmless; revert with `git -C src/barney/submodules/embree checkout -- kernels/`).

### CMake options that enable CPU rendering
```
-DBARNEY_BACKEND_CPU=ON      # Embree/CPU rtcore backend -> device library "barney_cpu"
-DBARNEY_BACKEND_OPTIX=OFF   # default is ON (needs CUDA+OptiX); disables silently if no nvcc
-DBARNEY_BACKEND_CUDA=OFF
-DBARNEY_MPI=ON              # MPIContext, DistFB, ray-queue cycling, ANARI device subtype "mpi"
-DEMBREE_ISA_SSE42=ON -DEMBREE_ISA_AVX2=OFF
```
- Embree 4.4.0 (barney submodule) is built statically inside the device
  (namespace `embree_for_barney`, internal tasking, no TBB/ISPC needed). No Embree
  module exists for GCCcore-14.3.0; an external `embree>=4.4` would be picked up by
  `find_package(embree)` if present.
- AVX2 does **not** work out of the box: with `-DEMBREE_ISA_AVX2=ON` the library builds but
  fails to load (`undefined symbol embree::CurveNi<8>::Type::name`), because
  `barney/rtcore/cpu/CMakeLists.txt` forces `EMBREE_GEOMETRY_CURVE OFF` as a normal variable.
  So the current build is SSE4.2-only Embree traversal (shading code is GCC-compiled C++).
- No OIDN denoiser on CPU (`BARNEY_OIDN_CPU` off; OIDN not available).
- Script `scripts/build_barney.sh`: build dir `build/barney_cpu`, prefix `install/barney`.

### Installed libraries / ANARI names
| file (`install/barney/lib64`) | `anariLoadLibrary()` name | notes |
|---|---|---|
| `libanari_library_barney_cpu.so` | `barney_cpu` | CPU backend only, recommended |
| `libanari_library_barney.so` | `barney` | multi-backend loader (optix > cuda > hip > cpu); here contains only CPU |

Both are linked against `libmpi.so.40` (OpenMPI 5.0.8). Device subtypes:
`"default"` (local, single process) and `"mpi"` (data-parallel over MPI).
There is no separate `barney_mpi` library in this revision; MPI is folded into the same
library. ANARI-SDK's `anariDistributedTutorial` asks for subtype `"distributed"`, which
barney does **not** map to MPI (falls back to a local device) — use `"mpi"`.

Supported on the CPU device (from `anariInfo -l barney_cpu`): geometry triangle, quad,
sphere, cylinder, cone, curve, **isosurface**; spatial fields structuredRegular,
**unstructured**, nanovdb, blockStructured; volumes transferFunction1D, principledVolume;
materials matte, physicallyBased; lights directional, point, spot, quad, hdri;
frame channels color, depth, primitive/object/instance id, normal; accumulation.

### Runtime knobs
- `BARNEY_MAX_CPU_THREADS=N`: Embree/worker threads per process (default: all cores).
  Set it when several ranks share a node (e.g. 128 / ranks-per-node).
- `BARNEY_CONFIG=key[=val]:...`, e.g. `LOG_CONFIG`, `LOG_TOPO`, `two-stage=1`, `all2all=1`
  (alternative global-trace schemes; default is ray-queue cycling `RQSMPI`).

## 3a. Resolution of the HEAD merge conflicts (2026-10-26)

Sides: "ours" = `5050e56` (user: principled-volume `colorRamp` mode, NanoVDB majorant
fix, `BARNEY_HAVE_NANOVDB` in the config header) on top of merge base `0b2c194`;
"theirs" = `4d9b843`, which contains upstream PR #84 (`ca4dbcd`, "Add principled volume
scattering and emission"). PR #84 deliberately **replaced** the old Cycles-style
principled model (density, scatter/absorption color, density threshold, emission color,
blackbody, temperature) by a **two-transfer-function model**: the regular color/opacity
TF gives tint and extinction, an optional `emissionMap` TF gives emission colour and mask,
scaled by `emissionStrength`. The non-conflicting parts of the merge (native
`volume/Volume.{h,cpp}`, `barney.h`, JSON, generated queries) already follow theirs; only
`principledColorRamp` from ours had been auto-merged into native `Volume.cpp`.

Resolved files (working tree of `src/barney`, uncommitted):

| file | resolution |
|---|---|
| `barney/barneyConfig.h.in` | keep both: ours' `#cmakedefine01 BARNEY_HAVE_NANOVDB` + theirs' `BARNEY_STRINGIFY/TOSTRING` (needed by `BARNEY_BACKEND_STRING`). The define has the same value as the `BARNEY_HAVE_NANOVDB=1` compile definition, so there is no redefinition conflict. |
| `barney/native/volume/NanoVDB.dev.cu` | theirs (identical closing braces, with namespace comments). |
| `barney/native/volume/PrincipledVolume.h` | theirs' two-TF model + ours' `colorRamp` flag (host + DD). The old helper functions (`principledSigmaS/A/T`, `principledEmission`, `principledMajorant`, blackbody) and the old parameters are dropped, as upstream did (nothing in HEAD uses them any more). `principledCollisionEmission()` gets the regular TF sample at the collision as an extra argument. Order: `emissionMap` set -> upstream behaviour; otherwise if `colorRamp` -> `emissionStrength * tf.rgb`; else no emission. |
| `barney/native/volume/MCAccelerator.h` | theirs (albedo 1, tint = TF colour, emission from `principledCollisionEmission`) + passes the Woodcock `sample` (= TF at the collision point). |
| `barney/anari/Volume.{h,cpp}` | theirs (`emissionMap`) + ours' `colorRamp` parameter (`bool`, default false) forwarded as `principledColorRamp`. The ANARI parameters `emissionColor`, `blackbodyIntensity`, `blackbodyTint`, `temperature` are **not** kept: the native side in HEAD no longer accepts them (would only produce "unknown parameter" warnings) and upstream removed them on purpose. |

Why `colorRamp` reduces to `emissionStrength * tf.rgb`: in ours, the ColorRamp mode used
emitted radiance per unit length `Le = strength * emissionColor * tf.rgb * tf.w` and the
collision estimator adds `Le / sigma_t`. In the upstream model `sigma_t = tf.w` (the
Woodcock sample already contains 1/unitDistance), so the per-collision emission is
`strength * tf.rgb` (with `emissionColor` = 1). This is the same form as upstream's
`strength * e.w * e.rgb`, i.e. `colorRamp` = "use the colour TF as emission TF with mask 1".
Behaviour differences vs. ours' old ColorRamp mode: no separate `emissionColor` tint (bake it
into `emissionMap` or the colour TF), scattering albedo is 1 and the tint is the TF colour
(upstream), instead of `scatterColor/absorptionColor`.
`colorRamp` is not declared in `anari/json/common/bn_volume_principled.json` (the
pre-generated query files would have to be regenerated); helium accepts it anyway.
Note: the principled emission path in `MCAccelerator.h` is only compiled with
`-DBARNEY_USE_MULTI_SCATTERING=ON` (default OFF); without it, `principledVolume` renders
like `transferFunction1D` (no emission).

Build/test of the working tree (cn630, 2026-10-26):
- `BARNEY_PREFIX=$PROJ_ROOT/install/barney-head BARNEY_BUILD_DIR=$PROJ_ROOT/build/barney-head bash scripts/build_barney.sh`
  (CPU + MPI, same options as `install/barney`): builds without warnings in barney code.
- `BARNEY_PREFIX=$PROJ_ROOT/install/barney-head ANARI_TEST_OUT=$SCRATCH_ROOT/renders/anari_test_head bash scripts/run_anari_tests.sh`
  plus the 2-rank MPI run: all images in `renders/anari_test_head/` are **bit-identical** to
  `install/barney` renders of the same test program (`barney_cpu_mesh_volume`, `barney_cpu_mpi2`
  directly vs. `renders/anari_test/`; `barney_cpu_mesh`, `barney_cpu_volume`,
  `barney_multi_mesh_volume` vs. re-renders in `renders/anari_test_head/ref_install_barney/`, because
  the old files in `renders/anari_test/` predate the last change of the test program).
  Timings unchanged (~0.30-0.34 s/frame single process, ~0.64 s/frame 2 ranks on one node).
- Conflict code path (principled emission) checked with a side build
  `BARNEY_EXTRA_CMAKE_ARGS=-DBARNEY_USE_MULTI_SCATTERING=ON` -> `build/barney-head-ms`,
  `install/barney-head-ms` (compiles without warnings) and a test variant
  (`build/anari_tests_principled/src`, env `TEST_VOLUME=principled`,
  `TEST_EMISSION=none|colorRamp|map`): images in `renders/anari_test_head/principled_ms/`.
  No emission = same as `transferFunction1D` (RMSE 0.25 %, MS noise), `colorRamp` emits
  in the TF colours, `emissionMap` emits in the map colour (orange), as intended.

## 4. Verification (images in `/scratch/project/eu-25-121/milanjaros/openfoam/renders/anari_test/`)

Test program: `data/anari_tests/anariBarneyTest.cpp` (+ `CMakeLists.txt`, built into
`build/anari_tests`, runner `scripts/run_anari_tests.sh`). Scene: torus triangle mesh +
ground quad + 64^3-per-rank `structuredRegular` float volume with `transferFunction1D`.

| image | config | time (800x600, 4 spp/frame) |
|---|---|---|
| `barney_cpu_mesh.png`, `barney_cpu_volume.png`, `barney_cpu_mesh_volume.png` | barney_cpu, 1 process, 128 threads | ~0.3 s/frame |
| `barney_multi_mesh_volume.png` | `barney` multi loader -> CPU | ~0.3 s/frame |
| `helide_mesh_volume.png` | helide reference | ~0.014 s/frame (ray casting, not path tracing) |
| `barney_cpu_mpi2.png` | `"mpi"`, 2 ranks x 64 threads on cn627 | ~0.59 s/frame |
| `barney_cpu_mpi2_2nodes.png` | `"mpi"`, 2 ranks on cn627+cn628 (32 thr each) | ~0.25 s/frame |
| `barney_cpu_mpi4.png` (1024x512) | `"mpi"`, 4 ranks x 32 threads on cn627 | ~0.69 s/frame |

The MPI images show each rank's own torus/ground slab and a seamless volume across the
rank boundaries (one ghost sample layer per slab), identical between 1-node and 2-node runs.
Barney volumes are path traced (delta tracking, scattering), so they look darker/noisier
than helide's emission-absorption ray marcher at low sample counts.

## 5. MPI data-parallel usage (what the OpenFOAM side has to do)

1. Initialise MPI with `MPI_THREAD_MULTIPLE` (barney requests it if it has to init MPI itself).
2. `lib = anariLoadLibrary("barney_cpu", ...)`; `dev = anariNewDevice(lib, "mpi")`.
3. Optionally pass a communicator: `MPI_Comm comm = ...; uint64_t p = (uint64_t)&comm;`
   `anariSetParameter(dev, dev, "pointer_to_mpi_communicator", ANARI_UINT64, &p);`
   (otherwise barney uses `MPI_Comm_dup(MPI_COMM_WORLD)`; the `MPI_Comm` object must
   outlive the device). Optional `dataGroupID` (int): ranks with the same id hold the
   same (replicated) data; default = rank, i.e. pure data-parallel. Then commit the device.
4. **Each rank builds an ordinary ANARI world containing only its local data**
   (its own triangle arrays, volume brick, etc.). No global gather. For volumes add a
   one-cell ghost layer so trilinear interpolation is continuous across ranks.
5. Camera, renderer and frame parameters must be **identical on all ranks**;
   `anariRenderFrame`/`anariFrameReady` are **collective** over the communicator
   (every rank calls them every frame, also after scene updates).
6. Barney traces rays across all ranks (ray-queue cycling) and gathers the final tiles on
   **rank 0** of the communicator; only rank 0 should `anariMapFrame("channel.color")`
   (other ranks get black). Rank 0 then encodes/streams the image.

## 6. Limitations vs. GPU

- Performance: CPU path tracing at ~0.3 s for 0.5 Mpix x 4 spp on a full 128-core node
  (SSE4.2 Embree) — interactive only at low resolution/spp; no denoiser on CPU.
- Data-parallel mode adds ray-forwarding cost; on one node it is slower than one process
  (0.59-0.69 s vs 0.3 s/frame). It scales scene capacity, not speed.
- No GPU-specific features (OptiX denoiser/upscaler, CUDA frame buffers).
- MPI scheme assumes ranks render collectively in lock-step; a rank that stops calling
  render blocks all others.
- A rank without data ("passive" display/viewer rank, native `dataRank=-1`) is not reachable
  through the ANARI `dataGroupID` parameter (-1 means "default = rank"); needs checking.

## 7. Recommendations for the OpenFOAM integration on CPU-only nodes

- Use ANARI device `barney_cpu` with subtype `"mpi"`; link the function object against
  `anari::anari` only (load barney at runtime via `ANARI_LIBRARY`/`anariLoadLibrary`).
- In-situ prototype (Phase 1/2) is feasible on CPU right now: every OpenFOAM rank (or a
  sub-communicator of render ranks) feeds its local `sampledIsoSurface` triangles directly
  to its local ANARI world; rank 0 receives the composited frame.
- Do not run barney with 128 threads inside every solver rank: create a render
  sub-communicator (e.g. one render rank per node or per socket, via
  `pointer_to_mpi_communicator`), forward local surface packets intra-node to it, and set
  `BARNEY_MAX_CPU_THREADS` so rendering does not oversubscribe the solver cores; or run
  the render ranks in-transit on separate CPU nodes.
- Barney's CPU device also supports `unstructured` spatial fields and an `isosurface`
  geometry, so isosurfaces/volumes could alternatively be rendered directly from cell data
  (src/umesh contains an offline `foam2umesh` converter useful for test data).
- Keep the scene/transport layer renderer-agnostic: the same code then runs on the GPU
  build (`BARNEY_BACKEND_OPTIX=ON`) unchanged on a GPU partition.
- Open: commit the conflict resolution (section 3a) to the fork; AVX2 Embree fix; OpenFOAM's MPI thread
  level (Pstream) vs. barney's `MPI_THREAD_MULTIPLE` requirement.
