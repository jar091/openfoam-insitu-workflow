# Mesio Integration into OpenFOAM v2606: Direct MPI-to-OpenVDB Export

**Status:** Technical design proposal  
**Target:** OpenFOAM v2606 (OpenCFD/OpenFOAM.com distribution)  
**Primary objective:** Export one consolidated OpenVDB (`.vdb`) file per selected simulation time without first writing per-rank OpenFOAM field files.

## 1. Executive summary

Implement a loadable OpenFOAM `functionObject` library, tentatively named `libmesioFoam.so`, that passes mesh geometry and simulation fields directly from the running OpenFOAM processes to the existing Mesio conversion and aggregation pipeline. Mesio performs distributed processing and creates **one VDB file per export time across all MPI ranks**.

The integration must support both:

- **Native fields** already maintained by the solver (e.g., `U`, `p`, `T`, `k`); and
- **Derived fields computed by existing OpenFOAM function objects or field-processing mechanisms** (e.g., `Q`, `vorticity`, `mag`, `grad`, `wallShearStress`, subject to output type and conversion support).

**OpenFOAM is responsible for computing derived quantities. Mesio is responsible for transporting, converting, aggregating and writing their values.** The integration must not reimplement OpenFOAM's derived-field calculations.

A strict *VDB-only output mode* is a separate engineering requirement. Loading a Mesio function object alone does **not** disable OpenFOAM's own output, logs, processor directories, mesh files, or other function-object files.

## 2. Goals and non-goals

### Goals

1. Configure the integration using `system/controlDict`, with no changes to individual solver source files.
2. Read native and registered derived fields **directly from memory** on each MPI rank.
3. Generate exactly **one final VDB file per selected export time**, containing requested supported fields and regions according to an explicit naming convention.
4. Support MPI runs without reconstructing or writing complete OpenFOAM time directories first.
5. Run OpenFOAM's standard derived-field calculations, not equivalent calculations within Mesio.
6. Support a configurable export interval independent of checkpoint/output frequency.
7. Provide an optional, explicitly tested *VDB-only* operation mode that suppresses unnecessary standard field output and other generated artifacts to the extent supported by the solver and runtime.
8. Retain an independently selectable OpenFOAM checkpoint policy for restarting a simulation.
9. Offer measurable performance, memory and correctness checks.

### Non-goals

- Replacing the OpenFOAM time integration or solving algorithms.
- Reimplementing OpenFOAM's `Q`, gradient, vorticity or other derived-field algorithms in Mesio.
- Promising bit-exact recovery of the original unstructured finite-volume mesh from a voxelized VDB representation.
- Treating a VDB file as an automatically complete restart checkpoint.
- Guaranteeing zero filesystem activity from arbitrary user-provided solvers, external libraries or other plugins without auditing and testing their output paths.

## 3. Proposed architecture

```text
                 OpenFOAM solver (MPI, N ranks)
                 ┌───────────────────────────┐
                 │ Native fields: U, p, T... │
                 │ OpenFOAM derived-field FOs │
                 │ Q, vorticity, grad, ...    │
                 └──────────────┬────────────┘
                                │ objectRegistry / fvMesh
                 ┌──────────────▼────────────┐
                 │ libmesioFoam.so           │
                 │ - scheduling / field list │
                 │ - field type dispatch     │
                 │ - local mesh/field views  │
                 │ - runtime validation      │
                 └──────────────┬────────────┘
                                │ in-memory data, all MPI ranks
                 ┌──────────────▼────────────┐
                 │ Mesio conversion / MPI    │
                 │ aggregation               │
                 └──────────────┬────────────┘
                                │
                 ┌──────────────▼────────────┐
                 │ VDB/<time>.vdb            │
                 │ one file per export time  │
                 └───────────────────────────┘
```

The plugin must be invoked collectively on all ranks when Mesio needs MPI communication. Restricting the function object's execution to rank 0 would break distributed export unless the adapter implements a corresponding collective communication protocol.

### 3.1 Components

| Component | Responsibility |
|---|---|
| OpenFOAM derived-field function objects | Compute and register derived values using standard OpenFOAM implementations |
| `mesioVDB` function object | Schedule export, discover and validate fields, provide local mesh/field access |
| Mesio in-memory adapter | Translate OpenFOAM types and MPI/local mesh metadata to Mesio inputs |
| Mesio converter/aggregator | Convert geometry and values, reconcile rank boundaries, build global sparse grids |
| VDB writer | Commit a single output file for a selected time |
| Output-control policy | Reduce/suppress non-VDB output and optionally retain sparse restart checkpoints |

## 4. Derived-field workflow (general, not limited to Q)

The exporter must support arbitrary **supported, registered OpenFOAM field objects**, including derived fields. Examples include `Q`, `vorticity`, `mag(U)`, `grad(U)` and `wallShearStress`; not all examples are volumetric scalar fields, so each requires type-aware handling.

1. The solver advances its fields.
2. OpenFOAM executes the configured derived-field producers.
3. The producer registers its result in the appropriate mesh/object registry.
4. The Mesio exporter locates each requested result **after it has been calculated for the current time**.
5. The exporter passes the in-memory field values and mesh association to Mesio.
6. Mesio produces the consolidated VDB file.

**Important:** A result existing in the registry is not enough: the exporter must ensure that it belongs to the *current* requested time, rather than silently exporting stale data.

### 4.1 Required execution ordering

OpenFOAM must compute any derived fields needed at an export step **before** Mesio reads them. Preferred options, to validate against v2606 implementation details:

- **Initial implementation:** Configure derived-field function objects before the Mesio exporter, and run their calculation phase at the export frequency. Verify actual execution order and freshness in integration tests.
- **More robust implementation:** Implement an explicit producer/export coordination layer that ensures required calculations are executed before export, independent of incidental dictionary ordering.

Avoid unnecessary derived-field calculations on non-export steps when those calculations are expensive and not used elsewhere.

### 4.2 No intermediate derived-field files

The desired workflow is:

```text
OpenFOAM computes Q / vorticity / other fields in memory
                     ↓
              objectRegistry
                     ↓
                  Mesio
                     ↓
                one .vdb
```

**Not:**

```text
OpenFOAM writes Q per rank → Mesio rereads Q files → Mesio creates VDB
```

Some stock derived-field function objects write their result during their own `write()` phase. This behavior must be verified for every configured producer. Changing `writeControl` alone is not a universal guarantee of calculation without a disk write. Where necessary, use a small OpenFOAM-specific wrapper or subclass that invokes the existing computation while suppressing its normal file-writing path, or add a validated no-write mode. Do **not** duplicate its scientific computation inside Mesio.

### 4.3 Supported types

The adapter should dispatch on the runtime type of the registered object:

| OpenFOAM object | Proposed handling |
|---|---|
| `volScalarField` | Scalar VDB grid |
| `volVectorField` | Vector VDB grid |
| `volTensorField`, `volSymmTensorField` | Explicit component mapping or documented supported tensor encoding |
| `surfaceScalarField`, `surfaceVectorField` | Initially reject unless a well-defined face-to-VDB mapping exists |
| `pointScalarField`, `pointVectorField` | Add only with documented interpolation/sampling semantics |
| Boundary patch values | Optional, separately specified conversion; not implicitly equivalent to cell values |
| Other registry objects | Reject with clear diagnostic unless explicitly supported |

Field names should be configurable and preserve useful dimensional metadata in the output or a documented accompanying convention, as far as OpenVDB and Mesio permit.

## 5. Configuration design

### 5.1 Illustrative `system/controlDict`

The example below combines **real OpenFOAM function-object concepts** with **proposed Mesio-specific keys**. It is a design specification, not a drop-in tested v2606 configuration.

```cpp
functions
{
    QField
    {
        type            Q;
        libs            (fieldFunctionObjects);
        field           U;
        result          Q;
        executeControl  timeStep;
        executeInterval 100;
        // Suppress ordinary result writes using a VERIFIED
        // no-write strategy in the chosen OpenFOAM v2606 build.
    }

    vorticityField
    {
        type            vorticity;
        libs            (fieldFunctionObjects);
        field           U;
        executeControl  timeStep;
        executeInterval 100;
        // Same no-write requirement as above.
    }

    mesioExport
    {
        type            mesioVDB;           // custom plugin
        libs            ("libmesioFoam.so");

        writeControl    timeStep;
        writeInterval   100;

        fields          (U p Q vorticity);
        missingField    error;              // proposed: error | warn | skip
        region          region0;
        outputDir       "VDB";              // proposed
        filePattern     "time_%TIME%.vdb"; // proposed
        parallelMode    distributed;        // proposed; only if supported by Mesio
        writerRank      0;                  // proposed, for final file commit
        outputPolicy    vdbOnly;            // proposed; see limitations
    }
}
```

The exact result names must match the producer objects in the target OpenFOAM build. Avoid relying on fixed dictionary ordering as the sole long-term dependency mechanism.

### 5.2 Export frequency versus calculation frequency

The requested `Q` / other derived fields must be computed in time for each Mesio export. If Mesio exports every 100 steps but derived calculations run every 200, half the exports may contain stale fields. A practical first version should require aligned schedules and fail with a useful diagnostic on missing or stale results.

## 6. MPI aggregation and one-file guarantee

Two designs are possible:

### A. Gather raw field/mesh data on rank 0

- Easier first implementation.
- May cause a major root-rank memory spike and high network traffic.
- Attractive only for limited problem sizes or when Mesio has no suitable distributed API.

### B. Convert locally, aggregate only necessary VDB structures (preferred if Mesio supports it)

- Each rank prepares local field/geometry data and performs the available local conversion.
- Mesio combines voxel/tree data with deterministic ownership/overlap rules.
- One selected writer commits the final file.
- Must explicitly manage overlapping rank boundaries, ghost/halo cells and global voxel-coordinate consistency.

**Important trade-off:** OpenVDB's ordinary file writer should not be assumed to support safe concurrent writes from multiple MPI ranks to the same file. A single final writer or a deliberately engineered collective file format/write path is required.

The plugin should report per-step local conversion time, collective communication time, final write time, peak memory usage and output size.

## 7. VDB-only disk-output policy

**Requirement:** During the measured solver time loop, newly generated field output should consist only of the requested `.vdb` files, unless checkpointing or explicitly allowed metadata is enabled.

This requirement is **not** fulfilled merely by installing a `functionObject`.

The following output sources must be audited and controlled:

1. Normal solver time-directory writes (`Time::write` / registered `AUTO_WRITE` objects).
2. Derived-field function-object `write()` methods and other post-processing exports.
3. Mesh/topology writes, dynamic-mesh updates and region-specific outputs.
4. Logs, timing/profiling files, function-object state/properties and other runtime metadata.
5. MPI decomposition/preparation artifacts such as `processor*` directories and initial mesh/field files.
6. User-coded or third-party explicit file writes.

### 7.1 Recommended implementation levels

**Level 1 — Minimal disruption:**

- Set standard solver checkpoint/write intervals very infrequently.
- Use an in-memory Mesio export path.
- Disable unnecessary producers' file output using validated no-write behavior.
- Accept pre-existing input, decomposed mesh and runtime logs.

This greatly reduces filesystem pressure but is **not** a strict no-other-files guarantee.

**Level 2 — Audited VDB-only time-loop mode:**

- Introduce a narrowly scoped output policy, enabled explicitly.
- Suppress standard field writes while retaining in-memory registration and calculations.
- Ensure producer computations run without their default result files.
- Audit all targeted solvers, function objects, mesh events and runtime metadata.
- Keep an optional separate checkpoint interval.
- Define allowed pre-existing case and MPI preparation files clearly.

This can guarantee the stipulated output contract only for a documented, tested OpenFOAM/Mesio/solver configuration, not for arbitrary plugins.

**Level 3 — No intermediate processor files from startup:**

This is a separate, larger scope: conventional decomposed-case startup often expects on-disk processor mesh/initial conditions. Removing these requires a different startup/distribution strategy or an explicitly supported alternative I/O mechanism. Do not promise it as part of the basic exporter.

### 7.2 Suggested verification

Take a baseline filesystem snapshot after case preparation and before the timed solve. Then compare the tree after one or more export steps. Fail the VDB-only integration test if unexpected new or modified artifacts appear, excluding an explicit allowlist (e.g., a redirected stdout log if required).

### 7.3 Restart behavior

VDB is not assumed to preserve all finite-volume solver state or mesh metadata necessary for restart. Recommended policy: allow rare conventional OpenFOAM checkpoints separately from frequent VDB visualization/analysis exports; strict VDB-only operation means deliberately giving up conventional restart unless another checkpoint solution is provided.

## 8. API and lifecycle details

Proposed OpenFOAM class: `Foam::functionObjects::mesioVDB`, built using `wmake libso` against the exact OpenFOAM v2606 headers and linked to Mesio/OpenVDB as required.

Expected lifecycle:

- `read(dictionary)`: Parse field selection, schedule, output policy and Mesio configuration.
- `execute()`: Optional prefetch/validation; avoid expensive duplicate field copies.
- `write()`: Validate results, construct rank-local views, invoke collective Mesio export, commit one VDB file.
- `updateMesh(...)`, `movePoints(...)`: Invalidate/rebuild cached geometry and mappings after mesh changes.
- Destruction: Release Mesio resources; avoid invoking MPI after MPI finalization.

Use the mesh's `objectRegistry` to locate registered fields, and support standard field types without assuming every requested name is a scalar field. Register the function object with the normal OpenFOAM runtime-selection mechanism.

### 8.1 Approximate pseudocode (not compilable)

```cpp
bool mesioVDB::write()
{
    const fvMesh& mesh = resolveRegionMesh();

    // Verify derived-field producers have updated their fields.
    validateCurrentTimeFields(mesh, requestedFields_);

    auto views = collectRegisteredFieldViews(mesh, requestedFields_);
    auto localGeometry = makeMeshView(mesh);

    // Called collectively on every participating MPI rank.
    mesio_.exportCollective(
        localGeometry,
        views,
        mesh.time().value(),
        outputPathForCurrentTime()
    );

    return true;
}
```

These functions are conceptual adapter APIs. Their actual signatures depend on the existing Mesio interface and lifetime/ownership rules.

## 9. OpenVDB data semantics

Because OpenFOAM uses an unstructured finite-volume mesh and OpenVDB represents sparse spatial grids, the conversion must document:

- Voxel size and transform / origin / coordinate system.
- Interpolation or conservative resampling policy.
- Cell-centered versus face-centered versus point-based inputs.
- Boundary treatment and MPI partition overlap resolution.
- Handling of empty/outside cells and sparse background values.
- Scalar/vector/tensor mapping and dimensional information.
- Consistency of values across MPI partitions and for dynamic meshes.

If Mesio already defines these semantics, the adapter should preserve them rather than introduce an independent mapping.

## 10. Performance and failure handling

Performance criteria should be based on measured results, not assumed improvements:

- Compare current OpenFOAM native parallel output + Mesio offline conversion with direct in-memory export.
- Report export wall time, critical-path MPI time, peak RAM per rank, VDB file size and total filesystem operations.
- Test strong scaling at the expected MPI-rank counts.
- Avoid gathering the entire unstructured mesh on rank 0 if that would exceed available memory.
- Make conversion failure collective and visible; prevent some ranks from hanging inside MPI collectives.
- Write to a temporary output name and rename atomically after successful completion where filesystem semantics permit.
- Handle duplicate time names, restarts and overwritten output deterministically.
- Avoid concurrent timestep output unless Mesio explicitly supports it with safe buffer ownership and MPI threading rules.

## 11. Acceptance criteria

1. The plugin loads in an unmodified OpenFOAM v2606 solver via `system/controlDict`.
2. A serial case exports one VDB for each configured export step with native and derived fields.
3. A multi-rank case produces **one VDB per export step**, not one per MPI rank.
4. At least `U`, `p`, `Q` and `vorticity` are tested; additional supported registered fields work through generic type dispatch rather than hardcoded special cases.
5. `Q` and other derived values agree with their OpenFOAM-computed references within a documented tolerance accounting for VDB sampling/resampling.
6. Export never requires intermediate per-rank timestep field files.
7. The requested output cadence is respected and stale/missing derived fields are detected.
8. In audited VDB-only mode, filesystem snapshots reveal no unexpected writes during the tested solver time loop.
9. Dynamic-mesh changes, if supported, invalidate old mappings correctly; otherwise fail with a clear unsupported-feature error.
10. Memory and export performance are documented for representative HPC cases.

## 12. Proposed implementation phases

| Phase | Deliverable | Critical verification |
|---|---|---|
| 1 | Basic `mesioVDB` function object, serial in-memory fields | No intermediate timestep files required by Mesio |
| 2 | MPI collective export using existing Mesio capabilities | One valid VDB per time, correct rank-boundary handling |
| 3 | General derived-field registry integration | `Q`, `vorticity` and other outputs refreshed before export |
| 4 | No-write derived-field execution and output control | No unintended native OpenFOAM field writes |
| 5 | Audited VDB-only mode, checkpoint policy | File-tree validation and restart behavior |
| 6 | Performance/scaling and robustness | HPC-scale memory, throughput, failure handling |

## 13. Open implementation decisions

Before fixing the adapter API, inspect the current Mesio source to determine:

- Whether it reads OpenFOAM processor files or already accepts mesh/field data directly in memory.
- Whether MPI communication is handled inside Mesio, and what communicator/collective ordering it expects.
- Whether Mesio constructs local VDB grids before merging, or gathers unstructured data first.
- Whether it supports vector/tensor fields, mesh motion, multiple regions and field transforms.
- Whether final file creation is already single-writer and safe on a parallel filesystem.

Also confirm the exact no-disk behavior and lifetime of relevant built-in derived-field function objects in OpenFOAM **v2606**, as well as how often solver-owned `Time::write()` and function-object `write()` are invoked. These details decide whether a pure add-on plugin is sufficient for audited VDB-only operation or a small OpenFOAM I/O control extension is needed.

## 14. References

- OpenFOAM v2606 `functionObjectList` API: https://api.openfoam.com/2606/classFoam_1_1functionObjectList.html
- OpenFOAM v2606 `writeObjects` API (field write control): https://api.openfoam.com/2606/classFoam_1_1functionObjects_1_1writeObjects.html
- OpenFOAM function-object documentation: https://doc.openfoam.com/2212/tools/post-processing/function-objects/
- OpenFOAM `Q` function object description: https://doc.openfoam.com/2306/tools/post-processing/function-objects/field/Q/

**Note:** This is a technical architecture specification, not an assertion that the example configuration or pseudocode already compiles against v2606. Mesio's actual API and OpenFOAM's effective writing behavior must be verified in implementation.
