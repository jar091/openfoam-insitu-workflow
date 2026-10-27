# anariVis: in-situ and in-transit ANARI rendering for OpenFOAM v2606 (CPU)

Status: 2026-10-26. Phases 1–3 of
`docs/openfoam_anari_barney_in_situ_in_transit_design.md` are implemented and
validated on Karolina CPU nodes (job 5270670). Everything runs on the CPU.

- The function object `anariVis` (`libanariVis.so`) extracts surfaces and
  volume samples in memory on every solver rank. There is no global gather
  and no intermediate files.
- In-situ mode: render ranks are a subset of the solver ranks.
- In-transit mode: render ranks run in a separate OpenFOAM world
  (`anariVisRender`, MPMD launch). Data goes over MPI and the solver only
  waits for its non-blocking sends.
- Renderers, selected at run time: `barney_cpu` (Barney `"mpi"`, data-parallel),
  `helide`, `cycles` (cyclesphi-anari), and `ptc` (deepCompositing wrapper).
  Direct sort-last compositing with `dc::Compositor` is also available.
- Output: one PNG per render step, written by render rank 0.

## 1. Code and build

```
src/openfoam-insitu-modules/anariVis/
  Allwmake, Allwclean, Make/{files,options}        wmake libso -> libanariVis.so
  functionObject/anariVis.{H,C}                    Foam::functionObjects::anariVis
  functionObject/anariVisSettingsIO.{H,C}          dictionary -> anariVis::RenderSettings
  functionObject/anariVisVolumeSampler.{H,C}       cell field -> structured grid points, brick routing
  functionObject/anariVisMPI.H                     UPstream::Communicator -> MPI_Comm, affinity helpers
  transport/anariVisTransport.{H,C}                MPI producer/consumer protocol (no OpenFOAM types)
  render/anariVisTypes.H, anariVisPacket.C         settings, packets, serialisation, bricks, colour maps
  render/anariVisScene.{H,C}                       packets -> local scene of one render rank
  render/anariVisRenderer.{H,C}                    ANARI scene + render + compositing (no OpenFOAM types)
  render/anariVisImage.C, stb_image_write.h        PNG output (stb, public domain)
  applications/anariVisRender/                     in-transit renderer (OpenFOAM application)
```

The OpenFOAM core is not modified. The render layer (`render/`, `transport/`)
uses only C++17, MPI and ANARI. Solver-specific types stay in
`functionObject/`, as the design proposes.

Build (on a compute node, about 1 min):

```
srun --jobid=5270670 --overlap -N1 -n1 -c 32 -w cn629 \
    bash scripts/build_anariVis.sh > build/logs/anariVis_build.log 2>&1
```

- `scripts/env_anari_openfoam.sh` sources `env_openfoam.sh` and sets
  `ANARI_ROOT`, `DEEPCOMP_ROOT`, `BARNEY_ROOT` and `CYCLES_ANARI_ROOT`. It also
  sets the install location and `LD_LIBRARY_PATH` for `anariLoadLibrary()`.
  The Blender bundle directories of the cycles device are appended last (the
  device needs `libopenjph` from there).
- Install location: `install/openfoam-modules/linux64GccDPInt32Opt/{lib/libanariVis.so,bin/anariVisRender}`.
- The library links `libanari` and `libdeepCompositing` with an RPATH, plus
  MPI (`$(PLIBS)`). The device libraries are loaded at run time:
  `libanari_library_{barney_cpu,helide,cycles,ptc}.so`.

## 2. Usage

Add an entry to `functions` in `controlDict`, after the function objects that
compute derived fields (`Q`, `mag`), because functions execute in dictionary
order. Examples:

- `data/openfoam/anariVis_snippets/inSitu.dict` and `inTransit.dict`: minimal
  annotated entries.
- `data/openfoam/anariVis_cavity/{controlDict,anariVisDict}`: 2D cavity test.
- `data/openfoam/anariVis_cavity3D/{functions,anariVisDict}`: cavity3D test
  (Q, magU, two cutting planes, Q iso, transparent |U| iso, 128³ volume).

Main keys (full table in the Doxygen headers of `anariVis.H` and
`anariVisSettingsIO.H`):

| key | values (default) |
|---|---|
| `mode` | `inSitu` \| `inTransit` (`inSitu`) |
| `renderRanksPerNode` | in-situ render ranks per node, `-1` = all (`1`) |
| `synchronise` | in-situ: other ranks wait in a sleeping `MPI_Ibarrier` loop while rendering (`true`) |
| `renderAffinityAll` | in-situ: render calls run on all cores of the node, see §4 (`true`) |
| `dropPolicy` | in-transit: `drop` \| `block` (`drop`) |
| `surfaceRouting` | `auto` \| `node` \| `spatial` (`auto` = `spatial` for deep/ptc) |
| `library` | `barney_cpu` \| `barney` \| `helide` \| `cycles` \| `ptc` (`barney_cpu`) |
| `wrappedLibrary` | library wrapped by `ptc` (`helide`) |
| `compositing` | `auto` \| `none` \| `barney` \| `deep` \| `ptc` (`auto`: barney → Barney `"mpi"`, others → deep) |
| `resolution`, `pixelSamples`, `passes`, `background`, `ambientRadiance`, `denoise`, `threads` | image settings |
| `depthMode` | deep compositing fragment depth: `auto` \| `device` \| `brick` |
| `outputDir`, `prefix`, `writeImages` | `<case>/postProcessing/<name>/<prefix>_<timeIndex>.png` |
| `camera {position lookAt up viewDirection fov zoom}` | without `position` the camera is fitted to the global mesh bounds along `viewDirection` |
| `lights {<name> {type directional\|point; direction; position; colour; intensity; cameraRelative;}}` | default: one camera-relative key light |
| `surfaces {<name> {<any sampledSurface dict>; colourField; colour; colourMap; range; opacity; smoothNormals;}}` | `isoSurface`, `patch`, `cuttingPlane`, ... |
| `volumes {<name> {field; resolution; bounds; interpolationScheme; colourMap; opacity ((x a) ..); range; unitDistance;}}` | volScalarField, or the magnitude of a volVectorField |

Colour maps: `coolToWarm`, `viridis`, `inferno`, `jet`, `grey`, `blueWhiteRed`,
or a list `((x r g b) ...)`.

### In-situ launch (inside job 5270670, direct PMIx launch)

```
srun --jobid=5270670 --overlap --mpi=pmix -N1 -n128 -w cn627 \
    bash -c 'source <env>; cd <case>; icoFoam -parallel -mpi-threads'
```

### In-transit launch (Slurm heterogeneous step = one MPI_COMM_WORLD)

```
srun --jobid=5270670 --overlap --mpi=pmix \
     -N1 -n128 -w cn627 bash -c '...; icoFoam -parallel -world sim' \
   : -N2 -n2 --ntasks-per-node=1 -w cn651,cn652 \
     bash -c '...; cd <case>; anariVisRender -parallel -world render -mpi-threads'
```

`-world` is OpenFOAM's multi-world option. `UPstream::commGlobal()` spans both
worlds, and `anariVisRender` is an OpenFOAM application, so it takes part in
OpenFOAM's world split automatically. The renderer receives all render
settings from the solver (the `anariVis` dictionary text), so it needs no
configuration of its own. Option `-threads N` overrides the number of render
threads.

Scripts:

| script | purpose |
|---|---|
| `scripts/run_anariVis_cavity.sh` | `prepare`, `config`, `run` for the 2D cavity |
| `scripts/run_anariVis_cavity3D.sh` | `mkenv`, `prepare <case> 1M\|8M <np>`, `config`, `run`, `runsim`, `render` |
| `scripts/test_anariVis_cavity_matrix.sh` | 2D cavity test matrix, 8 ranks |
| `scripts/test_anariVis_cavity3D.sh` | cavity3D experiments, e.g. `inSitu:barney_cpu:auto:1:mt`, `inTransit:barney_cpu:auto:1:r2,block`, `inSitu:cycles:deep:1:2n`, `off` |

Practical gotcha: sourcing the Lmod environment in each of 128 ranks takes
about 3.5 min per launch, because Lmod reads from NFS. `run_anariVis_cavity3D.sh mkenv`
writes `export -p` once to `runs/anariVis/env_cache.sh`, which the ranks then
source. With the cache, launch time drops to a few seconds.

## 3. Architecture and protocol

```
OpenFOAM ranks (producers)                         render ranks (consumers)
 sampledSurface::update() -> fan triangulation      Transport::receiveFrame()
 interpolate colour field to points (cellPoint)      assembleScene(): merge surfaces,
 volume: grid points inside local cells,                 fill own volume brick
   cellPointWeight cached, values per frame          Renderer::render():
 FramePacket per destination  --MPI_Issend-->          ANARI world -> render ->
                                                       Barney "mpi" | deep | ptc | none
                                                     render rank 0: PNG
```

- **Communicators**:
  - `visComm` is a duplicate of OpenFOAM's world communicator (in-situ) or of
    `commGlobal` (in-transit). The raw `MPI_Comm` comes from
    `UPstream::Communicator::lookup(...)`.
  - `renderComm` is `MPI_Comm_split` over the consumers. It is passed to Barney
    (`pointer_to_mpi_communicator`), to ptc (`mpiCommunicator`) and to
    `dc::Compositor`.
  - Set-up is collective: `MPI_Comm_dup`, `MPI_Comm_split_type` (node id),
    `MPI_Allgather` (roles), `MPI_Comm_split`, and finally
    `MPI_Reduce_scatter_block`, which tells each consumer how many packets it
    receives per frame. In-transit, the leader producer sends the settings
    text (tag 7301) between the split and the reduce-scatter.
- **Packets** (`FrameHeader` + surfaces + volume pieces, tag 7302):
  - Header: magic and version, frame index (time index), time, global bounds,
    stop flag, and the destination brick for spatial routing.
  - Surfaces: float xyz, per-point scalar, `uint32` triangles, and the global
    colour range (one `allreduce` min/max per field).
  - Volume pieces: global point index and value.
  - The serialisation format is documented in `anariVisPacket.C`.
- **Routing**:
  - Surfaces, `node` mode: a render rank on the same node, otherwise a block
    mapping of producers onto consumers.
  - Surfaces, `spatial` mode: each triangle goes, by its centroid, to the
    render rank whose convex brick contains it.
  - Volumes: the global point grid (128³ by default, over the global mesh
    bounds) is split into one brick per render rank. Neighbouring bricks share
    one point plane, so trilinear interpolation is seamless. Each producer
    samples only the grid points inside its own cells and sends them to the
    brick owner(s).
  - The destination set is static (static mesh). The leader producer always
    sends to every consumer.
- **Bounded memory and back-pressure (in-transit)**:
  - Producers use `MPI_Issend`, so a send completes only after the consumer
    has matched it. At the next render step every producer tests its sends
    (`MPI_Testall`), and the producers agree with one `returnReduceAnd` over
    the solver world.
  - If any send is still pending, the frame is dropped consistently on all
    producers (`drop`), or the producers wait (`block`).
  - So at most one frame per producer is in flight, and consumers always
    render complete frames. Consumers additionally buffer packets by frame
    index.
  - At the end (`functionObject::end()`), every producer sends a stop packet,
    and the renderer exits after the expected number of stop packets.
- **Rendering**: `anariRenderFrame` and the compositing are collective over
  `renderComm`. Render rank 0 maps the colour channel (sRGB8) or holds the
  composited deep image, then writes the PNG.

## 4. MPI thread level, FPE traps, CPU affinity

- **MPI thread level**:
  - OpenFOAM's `UPstream::init` requests `MPI_THREAD_SINGLE` by default and
    `MPI_THREAD_MULTIPLE` with the option `-mpi-threads`. That option is the
    supported way to satisfy Barney.
  - Barney's ANARI layer requests `MULTIPLE` only if it initialises MPI
    itself. Its render path (`Frame::renderFrame` → `bnRender` → `RQSMPI`)
    makes all MPI calls synchronously from the thread that calls
    `anariRenderFrame`. Its CPU worker threads make no MPI calls. In practice
    `FUNNELED` is enough.
  - Tests ran with Open MPI 5.0.8 and Barney `"mpi"` on 4 render ranks. With
    `SINGLE` (no `-mpi-threads`) the runs worked, with visually identical
    images and the same timings as with `MULTIPLE`. The function object prints a warning when Barney `"mpi"` runs
    below `MULTIPLE`.
  - Recommendation: in-situ with Barney, use `-mpi-threads`. The in-transit
    renderer always runs with `-mpi-threads`, and the solver does not need it.
    deepCompositing needs only `FUNNELED`.
- **FPE traps**: OpenFOAM enables `FOAM_SIGFPE`, and Embree's SIMD BVH
  builder then crashed helide with SIGFPE. The renderer masks FP exceptions
  while it runs ANARI code (`FpeGuard`) and restores the solver's traps
  afterwards. Worker threads created inside the guard inherit the masked
  environment.
- **CPU affinity**:
  - `srun -n128` binds every rank to one core. A render rank would otherwise
    run its 128 render threads on that single core.
  - `AffinityScope` widens the affinity to the whole node during the
    renderer's constructor, `render()` and destructor, then restores the
    rank's own core.
  - An earlier version left the rank unbound. Rank 0 then floated onto cores
    of other solver ranks, which slowed the whole solver by 5–10 s after some
    frames.
- **Threads per render rank**:
  - Barney's CPU launch system always starts `std::thread::hardware_concurrency()`
    (128) workers per process. `BARNEY_MAX_CPU_THREADS` limits only Embree.
  - helide behaves similarly. So several render ranks per node oversubscribe
    the node: Barney "mpi" with 4 ranks per node took 10.9 s instead of
    4.9 s, and helide/ptc with 4 ranks per node varied between 1.3 and 12 s.
  - Use `renderRanksPerNode 1`, which is the default.

## 5. Validation

The 2D cavity (64×64×1) ran serial and on 8 ranks with every library and
compositing mode:

- helide, barney_cpu, and cycles with `none` compositing.
- barney `"mpi"` on 4 ranks.
- helide, cycles and barney with `deep` compositing.
- `ptc`(helide).

Images are in `/scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis/cav_serial/{images_helide,postProcessing/anariVis}`
and `.../cav_par8/images_*`.

cavity3D 1M (HPC committee case, `src/hpc/.../cavity3D/1M/fixedIter`) ran on
128 ranks with `endTime 0.2`, 200 steps, and a frame every 20 steps (10
frames). The image is 1280×960 at 16 spp. The scene has two cutting planes, a
Q iso-surface, a transparent |U| iso-surface (about 120–150k triangles) and a
128³ |U| volume. Images are in
`/scratch/project/eu-25-121/milanjaros/openfoam/runs/anariVis/c3d_1M/images_<mode>_<lib>_<comp>_...`:

- **Processor-boundary continuity, with a serial reference**:
  - Fields at t = 0.4 were reconstructed, and one step was rendered serially
    (`c3d_1M_serial/images_ref`) and on 128 ranks (`c3d_1M_tune/images_par_*`)
    with helide, which is deterministic.
  - helide with 1 render rank: mean |Δ| 0.001/255, max 31, and 0.001 % of
    pixels differ by more than 8.
  - deep compositing over 4 render ranks: mean 0.091, and 0.002 % of pixels
    differ by more than 8.
  - There are no seams or missing or duplicated triangles at processor
    boundaries. Iso-surfaces come from OpenFOAM's parallel-consistent
    `sampledIsoSurface` (topo) with cellPoint interpolation.
- **Barney `"mpi"` (data-parallel)**:
  - The 4-rank image (`images_inSitu_barney_cpu_auto_rpn4_mt`) matches the
    1-rank image up to Monte Carlo noise.
  - So do the 2-node in-situ run (`..._rpn1_mt_2n`) and in-transit on 2 or 4
    nodes (`images_inTransit_barney_cpu_auto_rpn1_r2[_block]`, `_r4`).
  - Shadows and transparency are correct across ranks, because Barney traces
    rays across ranks.
- **Sort-last (deep, ptc)**:
  - With `node` routing, ordering errors are visible
    (`images_inSitu_helide_deep_rpn4_node` and the first cycles run).
    One RGBA-z fragment per rank cannot order data from non-convex subdomains.
  - With `spatial` routing (triangles by centroid to convex bricks, depth =
    brick-entry distance), the result matches the reference apart from a
    one-pixel seam at brick boundaries (`images_inSitu_cycles_deep_rpn1_2n`,
    `images_inTransit_cycles_deep_rpn1_r2_block`).
  - Shadows across bricks are missing, as expected for sort-last.
- **Triangle orientation**: vertex normals are area-weighted sums of the
  triangle normals, so they always agree with the winding. cycles renders all
  surfaces correctly, without black faces.

## 6. Performance (cavity3D 1M, 10 frames, 1280×960, 16 spp)

Baseline without function objects: 13 s for 200 steps on 128 ranks of one node
(0.065 s per step), and 14 s on 2 nodes (64 ranks per node).

| mode | renderer (render ranks) | solver wall clock | per frame on the solver | render per frame |
|---|---|---|---|---|
| in-situ | barney_cpu, 1 rank × 128 threads, `-mpi-threads` | 60 s | 4.99 s (extract 0.053, send 0.002) | 4.9 s (trace 4.5 + PNG 0.3) |
| in-situ | barney_cpu, 1 rank, MPI SINGLE | 65 s | 5.1 s | 5.0 s |
| in-situ | barney_cpu `"mpi"`, 4 ranks/node | 113 s | 10.9 s | 10.9 s (oversubscribed) |
| in-situ, 2 nodes | barney_cpu `"mpi"`, 2 ranks (1/node) | 60 s | 4.65 s | 4.56 s |
| in-situ | helide, 1 rank | 19 s | 0.60 s | 0.54 s |
| in-situ, 2 nodes | helide + deep, 2 ranks | 25 s | 0.80 s | 0.70 s |
| in-situ, 2 nodes | ptc(helide), 2 ranks | 23 s | 0.75 s | 0.68 s |
| in-situ, 2 nodes | cycles + deep, 2 ranks | 36 s | 2.06 s | 1.98 s |
| in-situ | cycles + deep, 4 ranks/node | 46 s | 3.4 s | 3.4 s |
| in-transit, drop | barney_cpu `"mpi"`, cn651+cn652 | **14 s** | 0.07 s (extract 0.064, send 0.043) | 4.0 s + 0.3 s PNG; 4 of 10 frames rendered |
| in-transit, block | barney_cpu `"mpi"`, cn651+cn652 | 34 s | 2.24 s (wait 2.19) | 4.0 s; 10/10 frames |
| in-transit, drop | barney_cpu `"mpi"`, cn651–cn654 | 14 s | 0.07 s | 3.6 s; 5/10 frames |
| in-transit, drop | helide + deep, cn651+cn652 | 15 s | 0.06 s | 0.21 s (+ 0.3 s PNG); 10/10 frames |
| in-transit, block | cycles + deep, cn651+cn652 | 21 s | 0.23 s | 1.2 s; 10/10 frames |

- Extraction costs about 0.05 s per frame: 4 sampled surfaces, 128³ volume
  samples, global ranges. Packing and posting the sends costs 0.002 s
  (in-situ) to 0.04 s (in-transit). The renderer receives about 9.5 MB per
  frame per render rank.
- First-frame set-up (communicators, volume sampling weights, device
  creation) takes 0.04–0.5 s. The cycles device takes 5.6 s on 4 ranks per
  node.
- CPU path tracing with Barney is the dominant cost: about 4–5 s per
  1.2 Mpix image at 16 spp on a 128-core node, without a denoiser. In-transit
  with `drop` keeps the solver overhead at about 0.07 s per frame, and the
  renderer shows the latest complete frame.

## 7. Limitations and open issues

- **Fixed 2026-10-26 (volume deadlock)**:
  - `cellPointWeight` triggers the lazy, collective `polyMesh::tetBasePtIs()`. Ranks with
    no sample point of a volume (subdomain outside `bounds`, or smaller than the grid
    spacing) never called it, so the other ranks hung at the first frame.
  - `anariVisVolumeSampler::setup()` now builds it on all ranks.
  - Found on HPC_motorbike (512 ranks), see `docs/notes/production_runs.md`.
- **Static mesh**: volume sampling weights and the routing destinations are
  computed once. `updateMesh` and `movePoints` only print a warning.
- **Sort-last modes** (`deep`, `ptc`): there is one fragment per pixel and
  rank, so shadows and transparency between render ranks are local only.
  `spatial` routing makes ordering exact for disjoint convex bricks, but
  triangles that straddle a brick boundary leave a one-pixel seam.
  - ptc uses the wrapped device's local depth, so volumes plus cycles inside
    ptc are wrong (cycles writes depth 0 for volumes). Use `deep`, which
    computes the brick-entry depth.
  - With `node` routing, use only opaque surfaces with `depthMode device`.
- **Device features**:
  - helide ignores the material `opacity`. The transparent |U| shell is
    opaque in helide images.
  - cycles needs `ambientRadiance > 0`, or its lights stay dark (known device
    issue).
  - Barney CPU has no denoiser, so images are noisy at 16 spp.
- **Barney CPU threading**: 128 worker threads per process regardless of
  `BARNEY_MAX_CPU_THREADS`, see §4. One render rank per node is recommended.
  Barney's source was not modified.
- **Mixed volume + surface ordering in deep mode** is exact only when both
  are spatially routed to the same bricks. This holds when surfaces use the
  bricks of the first volume, which is what the code does.
- **Packet size** is limited to 2 GB per message (`int` count), and the
  global grid to 2³² points.
- **Pending**:
  - Not tested: cavity3D 8M and multi-node in-transit with more than 4 render
    nodes.
  - Possible extensions: a GPU build of Barney (the code is renderer-agnostic
    and unchanged), unstructured spatial fields, and incremental ANARI object
    updates instead of rebuilding the world every frame.

## 8. Phase 4 / 5 status

- **Phase 4 (interactive service)**: not implemented. There is no viewer
  service, WebSocket or image streaming, and no camera interaction between
  CFD steps.
  - The building blocks exist: `anariVisRender` already holds the latest
    complete scene and the camera is a render setting. Phase 4 would add a
    control and stream thread to `anariVisRender` that re-renders the last
    scene on camera input, replacing the PNG writer with an encoder plus a
    WebSocket server. The solver side does not change.
- **Phase 5 (production hardening)**: partly done.
  - Done: multi-node runs (in-situ on 2 nodes; in-transit with 2 and 4
    render nodes), Slurm heterogeneous-step deployment, and a bounded
    drop/block policy.
  - Not done: failure recovery (with a dead renderer the solver drops every
    further frame, and it hangs in the final stop send), monitoring,
    authentication, long runs, and
    coexistence tests with the Mesio/OpenVDB function object. The design
    allows coexistence because both read the same registered fields.
