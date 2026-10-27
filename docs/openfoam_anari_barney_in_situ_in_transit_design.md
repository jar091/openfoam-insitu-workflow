# In-Situ / In-Transit Visualization for OpenFOAM v2606 Using ANARI-SDK and NVIDIA Barney

## 1. Objective

Develop a diskless visualization pipeline connecting **OpenFOAM v2606** (CPU-based CFD, optionally using MPI domain decomposition) to **ANARI-SDK** and the **NVIDIA Barney** distributed GPU renderer.

The pipeline should:

- Compute derived fields (e.g., Q-criterion) using OpenFOAM's existing field/function-object mechanisms.
- Extract isosurfaces and eventually other visualization primitives **in memory**, ideally on the MPI ranks that own the relevant CFD subdomains.
- Transfer the extracted data to the renderer **without intermediate files**.
- Render decomposed scenes across multiple NVIDIA GPUs and nodes, **without gathering all geometry on a single rank or GPU**.
- Display results interactively through a remote viewer, with camera interactions independent of the CFD time-step frequency.
- Support CPU-only CFD nodes and a separately allocated GPU rendering partition.

**Important distinction:** Distributed rendering avoids a global geometry gather, but does not eliminate the need for image compositing and coordinated rendering. The CFD-to-renderer data transport is a separate integration concern.

## 2. Architecture

### Preferred production architecture: in-situ extraction + in-transit rendering

```text
                  OpenFOAM v2606: CPU/MPI partition
          +----------------------------------------------+
          | rank 0        rank 1            rank N-1      |
          | local mesh    local mesh        local mesh    |
          | Q and fields  Q and fields      Q and fields  |
          | iso extraction on local data                 |
          +----------------------+-----------------------+
                                 |
                      in-memory surface packets
                                 |
                 MPI or another memory transport
                  (partition mapping / backpressure)
                                 |
          +----------------------+-----------------------+
          | GPU rendering partition: ANARI -> Barney     |
          | render rank 0   ...   render rank M-1        |
          | local scene fragments on distinct GPUs       |
          | distributed rendering and image composition  |
          +----------------------+-----------------------+
                                 |
                            framebuffer
                                 |
                     encode + network stream
                                 |
                       interactive web viewer
```

The number of OpenFOAM MPI ranks **does not need to equal** the number of render ranks. An explicit data redistribution layer is required when they differ.

### Deployment modes

| Mode | CFD placement | Renderer placement | Strengths | Limitations |
|---|---|---|---|---|
| In-situ | Same application/MPI job | Same ranks or tightly coupled GPU-capable ranks | Simple prototype; minimal transport | Competes with solver; GPU placement and MPI coordination can be restrictive |
| In-transit | CPU compute partition | Separate GPU partition | Independent resource scaling; clearer isolation | Transport, synchronization, and resource management |
| Hybrid (recommended) | Local extraction in solver ranks | Separate distributed Barney renderer | Avoids raw-field transfer; supports CPU-only compute nodes | Requires an in-memory data protocol |

## 3. OpenFOAM Integration

Implement an independent OpenFOAM **`functionObject`**, e.g., `anariInSitu`, packaged as `libanariInSituFoam.so`. Do **not** modify each CFD solver.

Responsibilities:

1. Run at configured CFD time-step intervals.
2. Obtain registered OpenFOAM fields, including derived quantities such as Q.
3. Extract specified geometric representations into host-memory buffers.
4. Attach metadata: time, source rank, field, isovalue, mesh/scene version.
5. Submit data through the selected transport backend.
6. Never write visualization intermediates unless explicitly requested.

### Extraction

Prefer OpenFOAM's native sampled-surface/isosurface infrastructure (including `sampledIsoSurface` where appropriate) rather than implementing an independent marching-cubes algorithm or routing geometry through VTK files.

Check the **exact v2606 C++ signatures and supported constructors** before implementation. Pay particular attention to how sampled surfaces access local fields, boundary data, triangulated faces, and scalar/vector interpolation.

Distributed extraction correctness must be tested at processor boundaries: independent subdomain extraction can produce missing or duplicated triangles and interpolation inconsistencies if processor boundaries are mishandled.

### Example `controlDict` interface (PROPOSED, NOT IMPLEMENTED)

```cpp
functions
{
    Q
    {
        type            Q;
        libs            (fieldFunctionObjects);
        executeControl  timeStep;
        executeInterval 1;
        writeControl    none;
    }

    anariLive
    {
        type            anariInSitu;
        libs            ("libanariInSituFoam.so");
        enabled         true;

        executeControl  timeStep;
        executeInterval 20;
        writeControl    none;

        backend         barney;
        mode            inTransit;

        transport
        {
            type            mpi;
            asynchronous    true;
            maxQueuedFrames 1;
            dropPolicy      oldest;
        }

        renderer
        {
            device          mpi;
            gpuMode         distributed;
            samples         1;
        }

        surfaces
        {
            vortex
            {
                type        isoSurface;
                field       Q;
                values      (100 500 1000);
                triangulate true;
                colorField  U;
            }
        }

        viewer
        {
            type        streaming;
            port        8080;
        }
    }
}
```

All `anariLive` keys above are **design proposals**; they are not claimed to be existing OpenFOAM or Barney configuration options. The Q field must be available and correctly registered **before** extraction executes; validate ordering and field lifetime in the selected solver/function-object setup. `writeControl none` on a function object **does not disable general OpenFOAM solver field output, checkpoints, or logging**.

## 4. Geometry Representation and ANARI Mapping

Start with triangle-based isosurfaces. A minimal transport representation could be:

```cpp
struct DistributedSurface
{
    uint64_t timestep;
    int sourceRank;
    int surfaceId;

    std::vector<float> positions;   // xyz triplets
    std::vector<uint32_t> indices;   // three vertex indices per triangle
    std::vector<float> scalars;      // optional per-vertex/per-face data
};
```

This is **illustrative**, not a complete serialization format. A production schema also needs geometry versioning, buffer sizes, component types, field association (per-vertex versus per-primitive), bounding boxes, units, and unambiguous ownership/lifetime rules.

Map the data to ANARI conceptually:

```text
position array + triangle index array
                 |
        ANARI triangle geometry
                 |
          ANARI surface
                 |
    local ANARI world contribution
                 |
       Barney distributed renderer
```

Example of host-memory packing:

```cpp
for (const Foam::point& p : surface.points())
{
    positions.push_back(static_cast<float>(p.x()));
    positions.push_back(static_cast<float>(p.y()));
    positions.push_back(static_cast<float>(p.z()));
}
```

Confirm the actual geometry triangulation, index width, ANARI array creation API, parameter names, and array ownership semantics for the versions being compiled. Host buffers cannot be freed or overwritten prematurely if an ANARI device or transport path still references them.

### Data movement

```text
OpenFOAM host memory
  -> local extraction buffers
  -> MPI/network/shared-memory transport (in-transit only)
  -> rendering process host memory
  -> Barney/ANARI GPU upload
  -> NVIDIA GPU VRAM
```

There is **no disk I/O requirement** here. However, end-to-end zero-copy is **not** implied: host transfers, serialization/copying, and GPU uploads may still be necessary.

## 5. Distributed Barney Rendering

Barney's distributed/data-parallel rendering is attractive because individual GPUs can hold separate scene partitions. It does **not** require a single GPU to store the entire global CFD surface mesh.

For example:

- 256 CPU OpenFOAM MPI ranks extract local geometry.
- 4 GPU nodes with 4 NVIDIA GPUs each run 16 rendering ranks.
- A transport layer distributes the 256 local geometry fragments among 16 rendering ranks.
- Each rendering rank owns a subset of the scene.
- Barney coordinates distributed image generation/compositing.
- The viewer receives the resulting rendered image, not the raw mesh.

**Do not assume that the ANARI standard automatically maps 256 producer ranks onto 16 renderer ranks.** Such redistribution and ownership assignment belong to the integration layer.

Before committing to the HPC topology, verify Barney's current MPI device implementation and constraints, including:

- communicator creation and membership;
- collective calls and scene commit behavior;
- GPU assignment per render rank;
- supported distributed ANARI world/geometry semantics;
- CUDA-aware MPI and runtime dependencies;
- output framebuffer availability and compositing behavior.

Data parallelism principally improves total scene capacity. Rendering performance may not scale linearly with GPU count because of scene imbalance, interconnect traffic, synchronization, and compositing costs.

## 6. Interactive Viewing Without Intermediate Files

The renderer requires a separate **viewer service**; Barney is a rendering library rather than a full end-user visualization GUI.

Use three logically separate loops:

**Simulation loop**

```text
CFD step -> derived fields -> local surface extraction -> publish new scene version
```

**Rendering loop**

```text
accept most recent complete scene -> update ANARI objects -> Barney frame
-> read framebuffer -> image encode -> network stream
```

**Interaction loop**

```text
browser camera/material/visibility input -> renderer parameters update
-> redraw existing scene (without advancing CFD)
```

For an initial viewer, WebSocket control plus compressed image frames is sufficient. A browser-side mesh renderer is not required because the GPU-side Barney process produces the image. A later implementation may use a more efficient streaming/video transport.

A history of earlier CFD steps requires deliberate RAM/VRAM retention or persistence; without buffering, only the latest published scene is available. Changing an isovalue that was **not already extracted** generally requires new surface extraction from CFD data (or access to separately retained field data).

## 7. MPI, Synchronization, and Performance Risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| Processor-boundary artifacts | Local extraction may not match globally reconstructed surface | Verify interpolation and halo/processor boundaries; numerical/visual regression tests |
| Producer/consumer rank mismatch | OpenFOAM and renderer have different parallel layouts | Explicit scene-fragment distribution and load balancing |
| Blocking sends/collectives | Viewer stalls can slow CFD or deadlock MPI | Well-defined protocol; bounded queues; careful communicator usage |
| MPI threading | Background MPI calls may not be thread-safe | Check `MPI_Init_thread` support and required thread level; initially avoid background MPI calls |
| VRAM pressure | Large isosurfaces plus acceleration structures and retained steps | Partition geometry; memory limits; incremental scene replacement |
| Simulation faster than rendering | Unlimited frames would accumulate in memory | Latest-frame policy; backpressure; optional frame drops |
| Dynamic topology | New mesh data can require rebuilding acceleration structures | Reuse ANARI objects where supported; version buffers |
| Remote viewer disconnect | Should not cause the solver to fail | Independent connection lifecycle and timeout handling |
| Failure of render partition | Must not silently corrupt CFD progress | Failure policy and optional graceful disabling of visualization |

**Recommended first transport implementation:** synchronous communication at selected simulation checkpoints, with an explicit completion/acknowledgment protocol. Add asynchronous pipelining only after validating MPI threading, collective ordering, and cancellation/error paths.

For production, use double buffering and a bounded queue (often a single pending scene version). This keeps memory usage under control and prioritizes timely visualization over displaying every single simulation step.

## 8. Proposed Code Organization

```text
openfoam-anari/
├── foamPlugin/
│   ├── anariInSitu.H
│   ├── anariInSitu.C
│   ├── isoSurfaceExtractor.H
│   ├── isoSurfaceExtractor.C
│   └── Make/
├── transport/
│   ├── SurfacePacket.H
│   ├── MpiTransport.H
│   └── SceneDistribution.H
├── renderer/
│   ├── BarneyRenderer.H
│   ├── BarneyRenderer.C
│   ├── SceneManager.H
│   └── FrameStreamer.H
└── viewer/
    ├── server/
    └── web/
```

Design principles:

- Keep solver-specific OpenFOAM types inside the `foamPlugin` layer.
- Keep the transport protocol renderer-agnostic.
- Use ANARI as the renderer abstraction and isolate Barney-specific distributed/device setup.
- Keep browser/network code outside OpenFOAM processes.
- Make visualization optional so a disabled or disconnected viewer does not prevent CFD execution.

## 9. Build and Runtime Strategy

Build ANARI-SDK, Barney (with MPI support), the renderer service, and the OpenFOAM shared library with compatible compilers and MPI ABIs.

Illustrative CMake build outline:

```bash
cmake -S ANARI-SDK -B build-anari \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$HOME/anari-install"
cmake --build build-anari -j
cmake --install build-anari

cmake -S barney -B build-barney \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$HOME/anari-install" \
  -DCMAKE_PREFIX_PATH="$HOME/anari-install" \
  -DBARNEY_MPI=ON
cmake --build build-barney -j
cmake --install build-barney
```

These commands are **illustrative, not a validated build recipe**. Confirm actual CMake options, compiler requirements, CUDA/OptiX dependencies, ANARI version compatibility, and MPI/CUDA-aware MPI requirements against the checked-out Barney revision. Build the OpenFOAM plugin with `wmake libso` where compatible with the target OpenFOAM installation.

The initial architecture should not force CUDA or Barney initialization on OpenFOAM's CPU-only ranks. Place those dependencies on the renderer side for the in-transit mode.

## 10. Diskless Operation and Mesio/OpenVDB Coexistence

| Activity | Diskless possible? | Qualification |
|---|---|---|
| Derived field calculation, including Q | Yes | Computed and retained in memory as needed |
| Isosurface extraction | Yes | Direct geometry buffers |
| CFD-to-renderer transfer | Yes | MPI/shared-memory/network transport |
| ANARI scene creation and GPU rendering | Yes | RAM/VRAM allocations still required |
| Interactive remote display | Yes | Framebuffer streamed over network |
| Recent-step history | Yes | Bounded by available RAM/VRAM |
| OpenFOAM standard field writing | Not automatically disabled | Separate solver `writeControl` configuration required |
| Checkpoints/logs/diagnostics | Not automatically disabled | Must be configured individually |

If Mesio is also integrated for persistent OpenVDB output, keep the roles separate:

- **Mesio → OpenVDB:** persistent storage of selected volume/field data.
- **ANARI → Barney:** interactive rendering of selected visualizations without intermediate files.

For triangle isosurfaces, passing geometry directly to ANARI is simpler than serializing to OpenVDB and importing it again. Both components can consume the same OpenFOAM fields without requiring a filesystem intermediate.

## 11. Implementation Roadmap and Acceptance Criteria

### Phase 1 — Single-rank proof of concept

- One OpenFOAM CPU process and one NVIDIA GPU.
- Extract one isosurface from a native OpenFOAM field.
- Create triangle geometry through ANARI and render with Barney.
- No intermediate visualization files.
- **Acceptance:** image agrees visually with a reference surface; no CFD file round-trip.

### Phase 2 — Distributed in-situ proof of concept

- Multiple CFD MPI ranks and a compatible distributed Barney configuration.
- Each producer contributes its local scene fragment.
- Verify no global geometry gather and correct cross-domain surface continuity.
- **Acceptance:** match the reconstructed reference; measure per-rank memory and render scalability.

### Phase 3 — Separate in-transit renderer

- CPU-only OpenFOAM ranks and independent GPU render ranks.
- Implement producer-to-consumer rank mapping and in-memory transport.
- Add bounded buffering, state IDs, failure handling, and a safe update protocol.
- **Acceptance:** different producer/consumer rank counts; bounded memory; solver makes progress during visualization according to the selected synchronization policy.

### Phase 4 — Interactive service

- Remote image streaming and input controls.
- Camera changes without requesting a new CFD step.
- Field and isosurface visibility controls.
- Optional queued requests for new isovalues.
- **Acceptance:** camera interaction works on the latest published scene and does not require disk I/O.

### Phase 5 — Production hardening

- Large-scene and multi-node profiling.
- Mesio/OpenVDB coexistence tests.
- HPC scheduler deployment (including separate CPU/GPU partitions where supported).
- Recovery, monitoring, permissions, and viewer authentication.
- **Acceptance:** stable long-running distributed cases with documented throughput, bandwidth, memory, and rendering latency.

## 12. Key Design Decisions

1. **Integrate through an OpenFOAM function object**, not solver modifications.
2. **Extract geometry in situ**, as close to the CFD field ownership as possible.
3. **Transport native geometry in memory**, not via files or OpenVDB intermediates.
4. **Render using ANARI and Barney distributed scene partitions**; avoid global geometry gathering.
5. **Separate CFD ranks from GPU render ranks** in the production in-transit design.
6. **Stream rendered images to the viewer**, not large transient meshes.
7. **Decouple simulation updates from interactive camera rendering**.
8. **Validate processor-boundary extraction and MPI semantics early**; they are the greatest correctness/integration risks.

## 13. References

- NVIDIA Barney: https://github.com/NVIDIA/barney
- Khronos ANARI-SDK: https://github.com/KhronosGroup/ANARI-SDK
- OpenFOAM v2606 `sampledIsoSurface` API: https://api.openfoam.com/2606/classFoam_1_1sampledIsoSurface.html
- OpenFOAM v2606 `sampledSurfaces` API: https://api.openfoam.com/2606/classFoam_1_1sampledSurfaces.html

> **Status:** Architecture and implementation proposal, not a claim that the custom function object, transport backend, renderer service, or viewer already exist. Validate release-specific interfaces against source code before implementation.
