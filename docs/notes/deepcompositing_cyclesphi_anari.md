# deepCompositing (CPU) and cyclesphi-anari: build and usage notes

Status (2026-10-26): both are built for CPU with foss/2025b and tested on cn629/cn630
(job 5270670).

- **deepCompositing**: new host implementation (C++/OpenMP + plain MPI, CMake option
  `DC_CPU`), same public API as the CUDA version. The `ptc` ANARI wrapper device also
  builds and runs on CPU. 1-node and 2-node MPI tests pass. Composited images match
  single-rank renders: helide max error 4/255 (8-bit fragments), 2-node output is
  bit-identical to 1-node output.
- **cyclesphi-anari**: ANARI library `cycles` (CyclesPhi/Cycles path tracer, CPU with
  Embree + OIDN + OpenVDB/NanoVDB). Renders triangle meshes and structured-regular
  volumes headless. No source changes were needed.

## 1. Build and environment

| what | script | build dir | install prefix |
|---|---|---|---|
| env (modules, `HOME`→scratch, paths) | `scripts/env_cyclesphi_anari.sh` | – | – |
| deepCompositing CPU + `ptc` device + samples | `scripts/build_deepcompositing.sh` | `build/deepcompositing` | `install/deepcompositing` |
| cyclesphi-anari (CPU) | `scripts/build_cyclesphi_anari.sh` | `build/cyclesphi-anari/{src,build}` | `install/cyclesphi-anari` |
| MPI test runner (one srun task) | `scripts/run_deepcomp_tests.sh` | – | output in `renders/deepcomp_test` |

All builds run on a compute node, e.g.
`srun --jobid=5270670 --overlap -N1 -n1 -w cn629 bash scripts/build_cyclesphi_anari.sh > build/logs/cyclesphi_anari_build.log 2>&1`
(logs: `build/logs/{deepcompositing,cyclesphi_anari}_build.log`). cyclesphi-anari builds in
about 10 min with 100 jobs. deepCompositing builds in under a minute.

`source scripts/env_cyclesphi_anari.sh` loads foss/2025b + CMake + Python and puts
`install/{deepcompositing,cyclesphi-anari,barney,anari}/lib64` plus the Blender lib bundle
dirs on `LD_LIBRARY_PATH`, so `anariLoadLibrary("cycles" | "ptc" | "helide" | "barney_cpu")`
all work in one process. It reuses `install/anari` (SDK 0.17.0) and does not rebuild it.

**cyclesphi-anari specifics**
- The `cyclesphi` git submodule of `src/cyclesphi-anari` is not checked out. Its pinned
  commit (07cda529e) is the same as `src/cyclesphi`, so the build script assembles an
  overlay source tree in `build/cyclesphi-anari/src`: symlinks to `src/cyclesphi-anari/*`
  plus `cyclesphi -> src/cyclesphi`. Neither source tree is modified, and the other
  agent's `build/cyclesphi_cpu` is not touched.
- Third-party libraries come from the Blender precompiled bundle
  `install/cyclesphi_libs/linux_x64` (`WITH_LIBS_PRECOMPILED=ON`, `CYCLES_LIB_DIR`).
  The bundle library dirs are baked into the RPATH (`CMAKE_INSTALL_RPATH_USE_LINK_PATH`).
- Options: `ANARI_CYCLES_USE_OPTIX=OFF`, `ANARI_CYCLES_USE_OIDN=ON`,
  `WITH_CYCLES_EMBREE=ON`, `WITH_CYCLES_OPENVDB=ON`, `WITH_CYCLES_NANOVDB=ON`, with HIP,
  oneAPI, OSL, USD, Alembic and Hydra OFF.
- Installed: `lib64/libanari_library_cycles.so`, `lib64/cycles/anari/*.xml` (XML shader
  templates), `bin/anari_cycles_test`.

## 2. CPU changes to deepCompositing (`src/deepCompositing`)

Added:
- `deepCompositing_cpu.cpp`: host implementation of `dc::Compositor`. It uses the same
  algorithm and data layout as `deepCompositing.cu`: per-pixel fixed-size fragment lists,
  2/4-bit counter compaction, a prefix sum, `MPI_Alltoallv` of counters and fragments over
  image-space pixel ranges, per-pixel z-sort and front-to-back blending, and a gather on
  rank 0. CUDA kernels became OpenMP loops, cub scans became a two-pass parallel scan, and
  MPI works on host buffers, so CUDA-aware MPI is no longer needed.
- `dc_host_math.h`: host versions of `int2/float3/float4/make_*` and of the
  `__device__`/`__host__` qualifiers.
- `dcConfig.h.in`: generates `dcConfig.h` with `#define DC_CPU 0|1`. Consumers that do
  not use CMake (wmake) get the right mode just by including the header.
- `samples/testRenderer_cpu.cpp`: OpenMP version of the cube test renderer.
- `samples/dcAnariDataParallel.cpp`: the data-parallel ANARI + compositing test (§5).

Modified:
- `CMakeLists.txt`: option `DC_CPU` (defaults to ON when no CUDA compiler is found) and
  `DC_BUILD_SHARED`. In CPU mode it builds `libdeepCompositing.so`, links OpenMP, and
  installs headers plus a CMake package (`find_package(deepCompositing)` →
  `deepCompositing::deepCompositing`). New option `DC_BUILD_ANARI`.
- `deepCompositing.h`: includes `dcConfig.h` and the host types in CPU mode. The
  `pixelBegin()` product is now 64-bit (it overflowed for large frame buffers × many
  ranks). Two CPU-only helpers named `dc::writeImageFragments(...)` were added.
- `anari/CMakeLists.txt`: `FrameWrapper.cu` is compiled as C++ in CPU mode.
- `anari/FrameWrapper.{h,cu}`: new CPU path. The wrapped device always renders
  `FLOAT32_VEC4` (linear, premultiplied); the wrapper composites and converts the result
  to the requested `UFIXED8_VEC4`, `UFIXED8_RGBA_SRGB` or `FLOAT32_VEC4`. A new frame
  parameter `ptc.background` (float4) is blended under the composite on rank 0. Also
  fixed: a color-type change without a size change is no longer ignored.
- `anari/PTCDevice.{h,cpp}`: two new device parameters. `wrappedLibrary` (string) selects
  the wrapped library; otherwise `$PTC_ANARI_LIBRARY` is used, falling back to helide.
  `mpiCommunicator` (`ANARI_VOID_POINTER` whose value is `&comm`, read at commit) sets the
  compositing communicator; the default is `MPI_COMM_WORLD`.
- `samples/CMakeLists.txt`, `samples/testDeepOffline.cpp`: host buffers in CPU mode.

Compatibility: the CUDA configuration (`-DDC_CPU=OFF`) still compiles with CUDA 12.8
(compile-only check, in `build/deepcompositing_cudacheck`). One intended difference: in
the CPU version the alpha byte of the final pixels holds the accumulated coverage, while
the CUDA version always writes 255. Fully covered pixels are identical in both.

## 3. API for data-parallel compositing (what a rank hands over)

Semantics: every rank writes RGBA-z **fragments** for any pixels, up to
`maxFragsPerPixel` per pixel and rank (the default is 3; when a list is full the farthest
fragment is dropped). RGB is **premultiplied** by alpha. `z` is any depth measure that is
consistent across ranks, and a smaller `z` is closer. After `finish()`, rank 0 holds the
z-sorted, front-to-back alpha-blended image as RGBA8 (linear, premultiplied, A =
coverage), with row 0 at the bottom as in ANARI frames.

```cpp
#include <deepCompositing/deepCompositing.h>   // link deepCompositing::deepCompositing
dc::Compositor comp(/*maxFragsPerPixel*/1, renderComm);   // once
comp.resize(width, height);                                // when the size changes
// per frame, on every rank of renderComm (collective):
dc::DeviceInterface di = comp.prepare();
// a) from an image rendered locally (ANARI channel.color=FLOAT32_VEC4, channel.depth):
dc::writeImageFragments(di, rgbaPremultFloat4, depth);     // skips alpha==0 pixels
// b) or fragment by fragment (thread-safe across pixels, not within one pixel):
//    di.write(x, y, dc::Fragment(z, make_float4(r*a, g*a, b*a, a)));
comp.finish(rank == 0 ? rgba8Out : nullptr);               // collective: MPI_Alltoallv + gather
```

For an OpenFOAM function object rank (in-situ, CPU), each rank does this:
1. Build its local ANARI world from its local `sampledIsoSurface` triangles (positions,
   `uint32` index triplets, optional `vertex.attribute0` for a colormap). Use any CPU
   device: `helide` (fast raycaster), `cycles` (path tracer) or `barney_cpu`
   (`"default"` subtype).
2. Use the same camera, renderer and frame size on every rank, with a **transparent
   background** (`background = {0,0,0,0}`) and frame channels `FLOAT32_VEC4` color plus
   `FLOAT32` depth.
3. Render, map color and depth, call `dc::writeImageFragments` (or write fragments with
   your own depth), then `finish()`. Rank 0 blends the background and encodes or streams
   the image.

Alternatively, without any compositing code in the application: load the ANARI library
**`ptc`**, set device parameters `wrappedLibrary` ("helide", "cycles", ...) and optionally
`mpiCommunicator`. Every rank then builds its local world as usual. `anariRenderFrame` is
collective, and rank 0 maps the composited `channel.color`. Set the renderer background
to transparent and pass the real background through the frame parameter `ptc.background`.

**Depth / ordering rules**
- Opaque surfaces (isosurfaces): the device depth channel is enough. This works with
  helide, cycles and barney.
- Volumes, or semi-transparent data split over ranks: one fragment per pixel and rank is
  only correct when the rank domains are **convex and disjoint** (bricks or slabs). Use
  the distance at which the pixel's camera ray **enters the rank's bounding box** as `z`
  (see `--depth brick` in `dcAnariDataParallel.cpp`: `PinholeCamera::rayDir` and
  `boxEntry`). helide's depth already equals the volume entry distance. **cycles writes
  depth 0 for volume-only pixels and for background pixels** (Cycles `PASS_DEPTH`
  semantics: camera z-depth at surface hits only), so with cycles you must use the brick
  depth. Because of this, the `ptc` wrapper with cycles is correct for surfaces only.
- OpenFOAM scotch/hierarchical subdomains are not convex. For volumes, resample them into
  per-rank bricks first. Opaque isosurfaces composite exactly with any decomposition.

## 4. cyclesphi-anari as an ANARI device

- Library `cycles` (`libanari_library_cycles.so`), device subtype `"default"`;
  renderers `default ao dpt raycast debug`. Compute backend selection: device parameter
  `computeDevice` (here only `cpu`).
- Object subtypes (from `anariInfo -l cycles`):
  - geometry: `triangle quad sphere cylinder cone curve isosurface`
  - spatial field: `structuredRegular` (tested), `nanovdb`, `unstructured`
    (tetra/hexa/wedge/pyramid, resampled on the CPU onto a regular grid; not tested here)
  - volume: `transferFunction1D` (tested), `principled`
  - material: `matte physicallyBased toon hair osl cyclesXml`
  - light: `directional point spot ring quad hdri sky`
  - camera: `perspective orthographic omnidirectional`
  - sampler: `image1D image2D image3D primitive transform`
- Useful renderer parameters: `pixelSamples`, `background` (alpha < 1 gives a transparent
  film), `ambientRadiance`, `denoise` (OIDN), `maxBounce`, `adaptiveSampling`. For offline
  or in-situ frames set **`interactiveScaling=false`**: the default renders the first frame
  after a change at reduced resolution. Set `runAsync=false` as well.
- Cost: 1024×768, 64 spp, mesh + 128³ volume takes about 1.7 s on one 128-core node
  (CPU path tracing). 256 spp of the volume alone takes about 2.6 s.
- Gotchas:
  - **Triangle winding must agree with `vertex.normal`**. With inconsistent winding the
    surface renders black in cycles, while helide does not care. OpenFOAM isosurface
    triangles and normals need to be oriented consistently.
  - IMPLEMENTATION_STATUS.md lists further known device defects, such as ambient light
    and attribute-driven colors.
  - `anari_cycles_test`: accumulated and first frame are identical, because the device
    resets accumulation on every frame. This was not investigated.

## 5. Test results (`/scratch/project/eu-25-121/milanjaros/openfoam/renders/`)

Test program `dcAnariDataParallel` (installed in `install/deepcompositing/bin`). Each rank
renders one x-slab of the unit cube: a brick of a 128³ Gaussian-blob field (sharing one
boundary point plane with its neighbor) plus the sphere triangles whose centroid lies in
the slab. The final image goes to rank 0. Image diffs use
`build/deepcompositing/tools/imgdiff`; mean and max are on 0–255 per channel.

| image (`deepcomp_test/`) | config | result |
|---|---|---|
| `cubes_4ranks.png`, `cubes_2nodes_4ranks.png` | `testDeepOffline`, 4 ranks, multi-fragment cubes | correct interleaved z/alpha order; 2-node bit-identical |
| `helide_4ranks_direct.png`, `helide_4ranks_ptc.png` | helide, 4 ranks, direct / ptc | sphere parts colored by rank, volume seamless |
| `helide_volume_{4ranks,4ranks_ptc,2nodes_8ranks}.png` | vs `helide_volume_1rank.png` | mean 0.04–0.07, max 4 |
| `cycles_4ranks_direct.png`, `cycles_2nodes_4ranks_direct.png` | cycles 64 spp, brick depth | matches `cycles_1rank_ref.png` |
| `cycles_volume_4ranks.png` | cycles 256 spp vs 1 rank | mean 0.21, max 10 (MC noise) |
| `cycles_volume_4ranks_devdepth.png` | cycles with device depth | wrong: 2.2 % pixels off, max 88 (depth 0 issue) |
| `cycles_4ranks_ptc_surface.png` | ptc wrapping cycles, surfaces | correct |
| `barney_4ranks_direct.png` | barney_cpu per rank + deepComp | plausible; no cross-rank shadows (vs `barney_1rank_ref.png`) |
| `helide_2nodes_4ranks_{direct,ptc}.png` | cn629+cn630, 2 ranks/node | bit-identical to 1-node |
| `../cyclesphi_anari_test/{cycles_mesh_volume_1rank,cycles_surface_1rank,accumulatedFrame}.png` | cycles single process | mesh + structured volume OK |

Compositing time for 1024×768 with 4–8 ranks:
- helide: 0.1–0.3 s per frame.
- cycles: up to about 0.9 s per frame, almost all of it waiting for the slowest rank's
  render, since the measurement includes the load-imbalance wait.

Traffic is 1 fragment of 8 bytes per covered pixel, a few MB per rank.

Example run (2 nodes):
```
srun --jobid=5270670 --overlap --mpi=pmix -N2 -n4 --ntasks-per-node=2 -c64 -w cn629,cn630 \
  bash scripts/run_deepcomp_tests.sh dcAnariDataParallel --lib cycles --spp 64 -o out.png
```
(`--mpi=pmix` is required, otherwise srun starts singletons.)

## 6. Limitations

- Sort-last compositing only combines final pixels. Lighting effects that cross rank
  boundaries are lost: shadows cast by another rank's data, inter-reflections, volume
  shadowing. This is visible in the Barney comparison. Barney's own `"mpi"` device traces
  rays across ranks and does not have this problem.
- One ANARI frame gives one RGBA+depth per pixel. With non-convex or interleaved rank
  domains, semi-transparent data can be misordered. Multi-fragment input is only possible
  through the native `di.write()` API.
- Fragments are 8-bit RGBA (`SMALL_FRAGMENTS`), so quantization reaches about 4/255
  (float fragments: `#define SMALL_FRAGMENTS 0`, which doubles the traffic). Counts per
  MPI message are `int`, which gives a 2 GB per-rank exchange limit (checked).
- The `ptc` wrapper has these limits: the depth channel it returns is the local, not
  composited, depth; only rank 0 gets the image; MPI is initialized after the wrapped
  device is created (initialize MPI in the application first).
- cycles is a path tracer: it needs tens of spp for a clean image, the depth semantics
  are as described in §3, and lighting differs from helide (needs real lights).

## 7. How these fit the in-situ / in-transit design next to Barney

- **Barney `"mpi"`** remains the primary distributed renderer. It does correct global
  illumination across ranks, its own compositing, and scales scene capacity, and the same
  code runs later on GPUs.
- **deepCompositing (CPU)** is the renderer-agnostic sort-last fallback and in-situ path.
  Every solver rank, or a render sub-communicator, renders its local isosurface with any
  ANARI CPU device and composites with `dc::Compositor`. This does not require lock-step
  ray forwarding between ranks. Rendering is independent per rank, and only one
  `Alltoallv` and gather is collective. That makes it a good fit for a first in-situ
  prototype inside the OpenFOAM function object: no global gather, small images, exact
  for opaque isosurfaces. Keep the compositor's communicator separate from OpenFOAM's
  (`MPI_Comm_dup`).
- **cyclesphi-anari** is the high-quality CPU path tracer. Uses: (a) in-transit final or
  publication frames from the same ANARI scene description (triangles, structured or
  NanoVDB volumes, which fit the mesio/OpenVDB output), and (b) per-rank rendering behind
  deepCompositing when photoreal shading of local data is wanted (brick depth for
  volumes). It is too slow for interactive CPU use at full resolution unless spp and
  resolution are reduced.
- Suggested layering: the function object produces renderer-agnostic surface packets →
  `SceneManager` builds ANARI objects → backend choice `barney_cpu` (`mpi`) |
  `ptc`+`helide`/`cycles` | direct `dc::Compositor`. All of them already load through the
  same `anariLoadLibrary` call; only the device and compositing setup differ.

## 8. Open issues

- cycles depth channel: report 0 → +inf for background, and ideally provide a volume
  entry depth (device change in `FrameOutputDriver::extractDepthPass` / kernel). Until
  then use brick depth.
- `ptc`: optionally compute brick-entry depth itself from the world bounds and the camera.
  This would need the camera parameters, which the wrapper does not see.
- OpenFOAM integration: MPI thread level (`MPI_THREAD_FUNNELED` is enough for
  deepCompositing; Barney wants `MULTIPLE`), and a render sub-communicator per node to
  avoid oversubscribing the solver cores (set `OMP_NUM_THREADS`, `BARNEY_MAX_CPU_THREADS`).
- Not tested: cycles `unstructured` field and `isosurface` geometry, the OIDN `denoise`
  path, and the GPU (CUDA) build of deepCompositing at runtime (compile-only).
