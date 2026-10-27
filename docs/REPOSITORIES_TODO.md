# Moving all work into git repositories: checklist

Owner: Milan Jaros. State inspected on 2026-10-26 (read-only: `git status`, `git diff --stat`,
`git log`, `git submodule status`, `du`, `grep`). Nothing has been committed, pushed or deleted.
You do every git operation and deletion below yourself.

Rule for this workspace: **no patch files**. Every change lives as a commit in a repository
you own (your forks on github.com/jar091 or your namespace on code.it4i.cz). Build scripts
build checked-out commits, never a working tree with uncommitted changes or a patch.

Every commit message below ends with the line
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

Abbreviation: `$W=/mnt/proj2/eu-25-121/milanjaros/openfoam`.

---

## 0. Overview

| Repo (`src/...`) | origin | branch | HEAD | local state | action |
|---|---|---|---|---|---|
| `espreso` | `git@code.it4i.cz:blender/espreso.git` (**not yours**) | `mjar/devel` (= `origin/sc22`, no upstream) | `08eac5d9` | 18 modified, 4 new paths | create your own repo, 6 commits, push (section 1) |
| `deepCompositing` | `github.com/jar091/deepCompositing` | `mjar/devel` (local only, = `origin/master`) | `7864a71` | 9 modified, 5 new | 1 commit, first push (section 2) |
| `barney` | `github.com/jar091/barney` | `mjar/devel` (= `origin/mjar/devel`) | `7f46b52` | 6 modified + dirty `submodules/embree` | 1 commit, push; do not commit the embree change (section 3) |
| `ANARI-SDK` | `github.com/jar091/ANARI-SDK` | `mjar/devel` | `42388069` | clean, pushed | nothing |
| `umesh` | `github.com/jar091/umesh` | `mj/converters` | `c16a306e` | clean, pushed | nothing |
| `cyclesphi` | `github.com/It4innovations/cyclesphi` | `develop` | `07cda529` | clean (`lib/*` submodules not initialised) | nothing; pin hash |
| `cyclesphi-anari` | `github.com/It4innovations/cyclesphi-anari` | `cyclesphi_dev` | `d053b1ae` | clean; submodule `cyclesphi` not checked out (empty dir) | nothing; pin hash (section 4) |
| `hpc` | `develop.openfoam.com/committees/hpc` | `develop` | `a0b4ec82` | clean | nothing; pin hash |
| `OpenFOAM-v2606` | `gitlab.com/openfoam/core/openfoam` | detached at tag `OpenFOAM-v2606` | `481094fd` | only untracked `log.linux64GccDPInt32Opt` | no fork needed (section 4) |
| `openfoam-modules` | none (not a git repo) | | | mesioFoam + anariVis sources | **new repo** (section 5) |
| `$W` itself (`scripts/`, `data/`, `docs/`) | none | | | workflow | **new repo** (section 6) |

Unchanged repos owned by others (cyclesphi, cyclesphi-anari, hpc, OpenFOAM) need no fork:
they are pinned by commit hash (section 7). Fork them only if you change them later.

---

## 1. `src/espreso`: create your own repository, commit, push

### 1.1 Create your own repository (choose one)
- [ ] **Option A, code.it4i.cz (recommended: keeps the GitLab fork relation to `blender/espreso`):**
      in the web UI open `blender/espreso` → *Fork* → your personal namespace, visibility *Private*.
      URL: `git@code.it4i.cz:<your-namespace>/espreso.git`.
- [ ] **Option B, GitHub:** create an empty **private** repo `jar091/espreso` (no README, no
      license). URL: `git@github.com:jar091/espreso.git`.
      ESPRESO is BSD-licensed (`LICENCE`, (c) IT4Innovations), so a mirror is allowed. Keep it
      private until the ESPRESO team agrees to a public copy.

### 1.2 Changes in the working tree
State 2026-10-26 night (after the `next` hardening, `docs/notes/mesio_build.md` Section 10).
`git status --short -uall` lists exactly these **22 paths** (18 modified, 4 new):

```
 M src/config/ecf/output.cpp
 M src/config/ecf/output.h
 M src/esinfo/eslog.cpp
 M src/esinfo/eslog.h
 M src/input/builders/filler.cpp
 M src/input/builders/merging.cpp
 M src/input/builders/variables.cpp
 M src/mesh/mesh.cpp
 M src/mesh/mesh.h
 M src/mesh/preprocessing/clustered.cpp
 M src/mesh/preprocessing/meshpreprocessing.h
 M src/mesh/preprocessing/pure.cpp
 M src/mesh/preprocessing/volume.cpp
 M src/mesh/utils.h
 M src/output/visualization/openvdb.cpp
 M src/wrappers/openvdb/w.openvdb.cpp
 M src/wrappers/openvdb/w.openvdb.h
 M wscript
?? include/mesio_insitu.h
?? src/api/wrapper.mesio.insitu.cpp
?? src/input/parsers/memory/memoryfvm.cpp
?? src/input/parsers/memory/memoryfvm.h
```

Build by-products inside `src/espreso`: `.lock-waf_linux_build` and `.waf3-2.0.27-*/` (waf lock
file and unpacked waf library). The repository's own `.gitignore` ignores them (pattern `.*`;
`git status --ignored` shows them as `!!`), so nothing needs to change there. All other build
output goes to `$W/build/espreso*`.

| Commit | Logical change | Files |
|---|---|---|
| (a) | restore `storeBalanced()` for the BALANCED OpenVDB path (formerly `espreso-sc22-openvdb-store-balanced.patch`) | `src/output/visualization/openvdb.cpp` |
| (b) | MPI-correct cell-to-point conversion + segfault fix (formerly `espreso-sc22-fix-elements-to-nodes-mpi.patch`, plus the 2026-10-26 segfault fix) + processes left without elements by the redistribution (`Mesh::allowEmptyProcesses`) + no division in the orientation test of `rotateNormalsOut` + `-Wall` fixes in `Mesh::load` and `fillNodes` | `src/input/builders/variables.cpp`, `src/input/builders/merging.cpp`, `src/input/builders/filler.cpp`, `src/mesh/preprocessing/pure.cpp`, `src/mesh/preprocessing/clustered.cpp`, `src/mesh/mesh.h`, `src/mesh/mesh.cpp` **hunks 1-4** (`Mesh::load` x2, `Mesh::preprocess`, `Mesh::Mesh`) |
| (c) | OpenVDB wrapper: fog volume, voxel-centre transform, metadata (also per-grid string metadata), compression option, distributed leaf serialisation (`OpenVDBLeaves`, `OpenVDBDistributedFile`), memory usage | `src/wrappers/openvdb/w.openvdb.h`, `src/wrappers/openvdb/w.openvdb.cpp` |
| (d) | voxelisation: `VOLUME_VOXEL_SIZE`, `VOLUME_BOX*`, round-off-safe grid, moving meshes, no double voxelisation; inside test without FP exceptions and with exact pre-tests (several times faster), grid validation (`computeVolumeGrid`), guarded face normals and interpolation weights | `src/config/ecf/output.h`, `src/config/ecf/output.cpp`, `src/mesh/preprocessing/volume.cpp`, `src/mesh/preprocessing/meshpreprocessing.h`, `src/mesh/utils.h`, `src/mesh/mesh.cpp` **hunk 5** (`computePersistentParameters`) |
| (e) | eslog: optional error handler instead of `exit` | `src/esinfo/eslog.h`, `src/esinfo/eslog.cpp` |
| (f) | in-situ C API (version 2) + in-memory FVM input + distributed VDB writer front end | new `include/mesio_insitu.h`, new `src/api/wrapper.mesio.insitu.cpp`, new `src/input/parsers/memory/memoryfvm.h`, new `src/input/parsers/memory/memoryfvm.cpp`, `wscript` |

Notes:
- `mesh.cpp` has five hunks: in commit (b) `git add -p src/mesh/mesh.cpp` answers `y y y y n`
  (two `Mesh::load` hunks, `Mesh::preprocess`, `Mesh::Mesh`; not `computePersistentParameters`);
  commit (d) takes the rest. If you prefer not to split, put the whole file into (b).
- The FPE fix in `volume.cpp` is interleaved with the voxelisation changes of the same function,
  so it goes into (d) (one file, one commit).
- The distributed writer and the API 2 features are spread over the new API file (f) and the
  wrapper (c); they cannot be separated without hand-editing new files.
- Intermediate commits were not build-tested one by one; only the final tree is tested
  (`docs/notes/mesio_build.md` Sections 9-10). (c), (d) and (e) only add code that (f) uses; if
  you want every commit to build for sure, squash (c)-(f) into one commit.
- `install/mesio-next` and `install/mesio-asan-next` were built from exactly this tree.

### 1.3 Commands
```bash
cd $W/src/espreso
git status --short -uall                # expect the 22 paths above, nothing else

# (a)
git add src/output/visualization/openvdb.cpp
git commit -F- <<'EOF'
FIX: OpenVDB BALANCED output uses storeBalanced() again

Commit 81b0aed4 routed the BALANCED path to the WIP storeHierarchical(),
which prints every voxel and writes only the first variable.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF

# (b)
git add src/input/builders/variables.cpp src/input/builders/merging.cpp src/input/builders/filler.cpp \
        src/mesh/preprocessing/pure.cpp src/mesh/preprocessing/clustered.cpp src/mesh/mesh.h
git add -p src/mesh/mesh.cpp            # y y y y n: Mesh::load (2 hunks), Mesh::preprocess, Mesh::Mesh; not computePersistentParameters
git commit -F- <<'EOF'
FIX: MPI-correct element-to-node conversion, no out-of-bounds read, empty processes

reorderVariables averaged cell values to nodes through nodes->elements,
which is wrong for FVM-built meshes on more than one rank (interface
values off by up to 2x). It now uses the local element-node connectivity
and exchanges (count, partial sums) of shared nodes sorted by global ID.
Mesh::preprocess no longer calls linkNodesAndElements(..., true), which
read past the end of 'neighbors' for non-clusterized node orderings
(intermittent segfault); linkNodesAndElements now fails with an error in
that case. Processes that the SFC redistribution of a small mesh leaves
without nodes or elements are handled (outputOffset, computeBaseMeshInfo)
and allowed with Mesh::allowEmptyProcesses (set by the in-situ API).
rotateNormalsOut tests the orientation by the sign of the unnormalized
triple product (no division by zero for degenerate elements).
Mesh::load: no uninitialized input pointer, unsupported formats are
reported; fillNodes: no std::merge on a single int (-Wall warnings).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF

# (c)
git add src/wrappers/openvdb/w.openvdb.h src/wrappers/openvdb/w.openvdb.cpp
git commit -F- <<'EOF'
ENH: OpenVDB wrapper: fog volumes, metadata, distributed leaf writer

- GRID_FOG_VOLUME instead of level set, index-to-world = centre of voxel 0
- openvdb::initialize() once, cached accessor, per-grid 'time' and string
  metadata, active voxel count, memory usage, selectable compression
  (none / blosc)
- OpenVDBLeaves / OpenVDBSerializeLeaves / OpenVDBDistributedFile: leaves
  built and compressed on all ranks, concatenated by the writer rank into
  a file identical to openvdb::io::File output

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF

# (d)
git add src/config/ecf/output.h src/config/ecf/output.cpp src/mesh/preprocessing/volume.cpp \
        src/mesh/preprocessing/meshpreprocessing.h src/mesh/utils.h src/mesh/mesh.cpp
git commit -F- <<'EOF'
ENH: volume output: voxel size, sub-box, moving meshes, no FP exceptions

New ECF options OUTPUT.VOLUME_VOXEL_SIZE, VOLUME_BOX and
VOLUME_BOX_{MIN,MAX}_{X,Y,Z}. Element boxes are clamped to the grid, the
grid size is round-off safe, the bounding box is taken from the current
coordinates. The duplicated voxelization in computePersistentParameters
is removed.

The inside test no longer normalizes zero-length vectors when a voxel
centre coincides with a mesh point (division by zero, SIGFPE with
trapped FP exceptions, e.g. OpenFOAM FOAM_SIGFPE); such voxels stay
inside as before. Exact pre-tests (outside the element bounding box,
inside the element kernel) skip most solid-angle evaluations: the
voxelization is several times faster with identical results.
computeVolumeGrid validates the box and the voxel size without
overflowing divisions; degenerate face normals and vanishing
interpolation weight products are guarded.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF

# (e)
git add src/esinfo/eslog.h src/esinfo/eslog.cpp
git commit -F- <<'EOF'
ENH: eslog: optional error handler instead of exit

eslog::errorHandler, if set, is called by failure, internalFailure,
error and globalerror instead of terminating the process (used by the
in-situ API to turn MESIO errors into error codes).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF

# (f)
git add include/mesio_insitu.h src/api/wrapper.mesio.insitu.cpp src/input/parsers/memory/ wscript
git commit -F- <<'EOF'
ENH: Mesio in-situ C API (mesio_insitu.h, version 2)

C API for in-situ coupling (OpenFOAM function object): the mesh and
cell fields are passed from memory (InputMemoryFVM, OpenFOAM polyMesh
pipeline without files), converted to nodes and written as OpenVDB fog
volumes by a distributed, parallel or single writer.

Version 2: error codes and MESIOInSituLastError, consistent on all ranks
(no exit); several contexts per process; empty ranks; validated input;
MESIOInSituResetMesh for topology changes; cell sampling; per-grid
string metadata (units); memory statistics; no FP exceptions.
libmesioapi now also builds wrapper.mesio.insitu.cpp.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF

git status --short                      # must be empty
git log --oneline -7

# push to YOUR repository; keep blender/espreso as 'upstream'
git remote rename origin upstream
git remote add origin git@code.it4i.cz:<your-namespace>/espreso.git   # or git@github.com:jar091/espreso.git
git push -u origin mjar/devel
git push origin sc22                    # optional: base branch, for reference
```
- [ ] commits (a)-(f) done, `git status` clean
- [ ] own repo created, `mjar/devel` pushed, upstream tracking set
- [ ] then delete `$W/scripts/patches/` (section 9)

---

## 2. `src/deepCompositing` (github jar091): CPU port

Changes (all belong together; see `docs/notes/deepcompositing_cyclesphi_anari.md` §2):

| Kind | Files |
|---|---|
| new | `dcConfig.h.in`, `dc_host_math.h`, `deepCompositing_cpu.cpp`, `samples/testRenderer_cpu.cpp`, `samples/dcAnariDataParallel.cpp` |
| modified | `CMakeLists.txt`, `deepCompositing.h`, `anari/CMakeLists.txt`, `anari/FrameWrapper.cu`, `anari/FrameWrapper.h`, `anari/PTCDevice.cpp`, `anari/PTCDevice.h`, `samples/CMakeLists.txt`, `samples/testDeepOffline.cpp` |

One commit: the pieces depend on each other (the root `CMakeLists.txt` adds `anari/` and
`samples/` by default, and `samples/CMakeLists.txt` references both new sample files), so a
split would leave commits that do not configure. No build artefacts in the tree
(build dirs are `$W/build/deepcompositing*`).

```bash
cd $W/src/deepCompositing
git add dcConfig.h.in dc_host_math.h deepCompositing_cpu.cpp deepCompositing.h CMakeLists.txt \
        anari/CMakeLists.txt anari/FrameWrapper.cu anari/FrameWrapper.h anari/PTCDevice.cpp anari/PTCDevice.h \
        samples/CMakeLists.txt samples/testDeepOffline.cpp samples/testRenderer_cpu.cpp samples/dcAnariDataParallel.cpp
git commit -F- <<'EOF'
CPU (OpenMP + host MPI) implementation of the deep compositor

- deepCompositing_cpu.cpp: host dc::Compositor with the same algorithm and
  data layout as the CUDA version (fragment lists, counter compaction,
  prefix sum, MPI_Alltoallv, z-sort, front-to-back blend, gather on rank 0);
  no CUDA-aware MPI needed
- CMake options DC_CPU (default ON without a CUDA compiler), DC_BUILD_SHARED,
  DC_BUILD_ANARI; installs headers and a CMake package
- dcConfig.h (DC_CPU) and dc_host_math.h for non-CMake consumers (wmake)
- 64-bit pixelBegin() product (overflow with large frames x many ranks)
- ptc ANARI device: CPU path, 'wrappedLibrary' and 'mpiCommunicator'
  parameters, 'ptc.background', colour-type change fix
- samples: CPU cube renderer, dcAnariDataParallel test
The CUDA configuration (-DDC_CPU=OFF) still compiles (CUDA 12.8).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git status --short                      # must be empty
git push -u origin mjar/devel           # branch does not exist on origin yet
git branch -d mjar/develop              # optional: stale local duplicate (same commit 7864a71 as master)
```
- [ ] committed and pushed, upstream set

---

## 3. `src/barney` (github jar091): resolution of the committed merge conflict

Surprise to be aware of: the pushed HEAD `7f46b52 "update volume"` (merge of `5050e56` and
`4d9b843`) **contains conflict markers** in 6 files (`git grep -l '^<<<<<<<' HEAD`). The
working tree has them resolved (`docs/notes/anari_barney_build.md` §3a). The fix goes in as a
normal commit on top (no history rewrite, the branch is already public).

| Commit | Files |
|---|---|
| resolve conflicts | `barney/barneyConfig.h.in`, `barney/anari/Volume.cpp`, `barney/anari/Volume.h`, `barney/native/volume/MCAccelerator.h`, `barney/native/volume/NanoVDB.dev.cu`, `barney/native/volume/PrincipledVolume.h` |
| **do not commit** | `submodules/embree` (shown as modified: dirty submodule content, the recorded commit `e9b8633e` is unchanged) |

The embree change is a side-effect of Embree's CMake configure step, which rewrites
`kernels/export.linux.map` and `kernels/export.macosx.map` for the `embree_for_barney`
namespace. It is harmless and reappears at every configure. Do not `git add submodules/embree`
and never commit inside the submodule. To clean it (optional, it comes back on the next build):
```bash
git -C $W/src/barney/submodules/embree checkout -- kernels/export.linux.map kernels/export.macosx.map
# or hide it permanently (local config only):
git -C $W/src/barney config submodule.submodules/embree.ignore dirty
```

```bash
cd $W/src/barney
git grep -l '^<<<<<<< ' -- barney       # must print nothing
git add barney/barneyConfig.h.in barney/anari/Volume.cpp barney/anari/Volume.h \
        barney/native/volume/MCAccelerator.h barney/native/volume/NanoVDB.dev.cu \
        barney/native/volume/PrincipledVolume.h
git commit -F- <<'EOF'
Resolve merge conflicts committed in 7f46b52

Keep upstream's two-transfer-function principled volume (PR #84:
emissionMap + emissionStrength) and add the 'colorRamp' flag: without an
emission map, colorRamp uses the regular colour TF as emission
(emissionStrength * tf.rgb). barneyConfig.h.in keeps both
BARNEY_HAVE_NANOVDB and BARNEY_STRINGIFY/TOSTRING. The old ANARI
parameters emissionColor, blackbodyIntensity, blackbodyTint and
temperature are dropped, as upstream did.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git status --short                      # only ' M submodules/embree' may remain (see above)
git push origin mjar/devel
```
- [ ] committed and pushed
- [ ] optional follow-up commit: declare `colorRamp` in `anari/json/common/bn_volume_principled.json` and regenerate the query files (§3a of the barney notes)
- [ ] optional follow-up commit: AVX2 Embree fix in `barney/rtcore/cpu/CMakeLists.txt` (curves forced OFF)

---

## 4. Repositories without changes

- [ ] `ANARI-SDK` (`mjar/devel`), `umesh` (`mj/converters`): clean, nothing ahead of origin. Nothing to do.
- [ ] `cyclesphi` (It4innovations, `develop`): clean. No fork needed; pin `07cda529`.
- [ ] `cyclesphi-anari` (It4innovations, `cyclesphi_dev`): clean. Its submodule `cyclesphi` is
      not initialised (empty directory); the pinned commit `07cda529` equals `src/cyclesphi`
      HEAD, which is why `scripts/build_cyclesphi_anari.sh` builds through a symlink overlay
      (section 8). No fork needed; pin `d053b1ae`.
- [ ] `hpc` (OpenFOAM HPC committee, `develop`): clean. No fork needed; pin `a0b4ec82`.
- [ ] `OpenFOAM-v2606`: detached at tag `OpenFOAM-v2606` (`481094fd`); `git status` shows only
      the untracked build log `log.linux64GccDPInt32Opt`; the rest are ignored build outputs
      (`lnInclude/`, `platforms/`, `META-INFO/build-info`). **The core is unchanged, so no
      OpenFOAM fork is needed.** The site configuration lives in `scripts/openfoam-etc/`
      (used via `FOAM_CONFIG_ETC`, `scripts/env_openfoam.sh:46`) and goes into the workflow
      repo (section 6). Move or remove the log:
      ```bash
      mv $W/src/OpenFOAM-v2606/log.linux64GccDPInt32Opt $W/build/logs/openfoam_wmake_v2606.log
      # or: echo log.linux64GccDPInt32Opt >> $W/src/OpenFOAM-v2606/.git/info/exclude
      ```

---

## 5. New repository: OpenFOAM modules (`src/openfoam-insitu-modules`)

### 5.1 Name and host (choose one)
- [ ] GitHub: `jar091/openfoam-insitu-modules` (or `jar091/openfoam-anari-mesio`)
- [ ] code.it4i.cz: `<your-namespace>/openfoam-insitu-modules`

### 5.2 Contents (from `find`, 30 source files, 3.3 MB including build outputs)
State 2026-10-27: `mesioFoam` is the hardened version (mesioVDB with `onError`, `sampling`,
`memoryTracking`, units metadata, several instances, `MESIOInSituResetMesh` on topology
changes, safe run-time re-read of the settings; `Make/options` comment updated). It requires the Mesio in-situ API **version 2**
(espreso commit (f) of section 1; `install/mesio-next`) and refuses to compile against an older
`mesio_insitu.h` (`#error`). Changed files since the first inventory: `mesioFoam/Make/options`,
`mesioFoam/mesioVDB/{mesioVDB.C,mesioVDB.H,mesioVDBTemplates.C}`; `anariVis` unchanged.
Include:
```
mesioFoam/Allwmake
mesioFoam/Make/{files,options}
mesioFoam/mesioVDB/{mesioVDB.C,mesioVDB.H,mesioVDBTemplates.C}
anariVis/{Allwmake,Allwclean}
anariVis/Make/{files,options}
anariVis/functionObject/{anariVis.C,anariVis.H,anariVisMPI.H,anariVisSettingsIO.C,anariVisSettingsIO.H,anariVisVolumeSampler.C,anariVisVolumeSampler.H}
anariVis/render/{anariVisImage.C,anariVisPacket.C,anariVisRenderer.C,anariVisRenderer.H,anariVisScene.C,anariVisScene.H,anariVisTypes.H,stb_image_write.h}
anariVis/transport/{anariVisTransport.C,anariVisTransport.H}
anariVis/applications/anariVisRender/{anariVisRender.C,Make/files,Make/options}
```
Exclude (build outputs): `*/lnInclude/`, `*/Make/linux64*/` (wmake objects), any `*.so`, `log.*`.
No absolute paths in the sources (`MESIO_ROOT`, `OPENVDB_ROOT`, `ANARI_ROOT`, `DEEPCOMP_ROOT`,
`ANARIVIS_LIBBIN` come from the environment).

`.gitignore` (gitignore has no trailing comments; the `Make/*/` line ignores every
`Make/<WM_OPTIONS>/` object directory, while `Make/files` and `Make/options` stay tracked):
```
lnInclude/
Make/*/
*.o
*.so
*.dep
log.*
```

### 5.3 License
- OpenFOAM modules link against OpenFOAM (GPLv3+) and must be **GPLv3-compatible**. The headers
  already carry the GPLv3-or-later text. Add a `COPYING` file with the GPLv3 text.
- [ ] Unify copyright lines: `mesioFoam/*` says "Copyright (C) 2026 OpenFOAM-Mesio integration
      project" (placeholder), `anariVis/*` says "IT4Innovations, VSB-TU Ostrava". Pick the real holder.
- `anariVis/render/stb_image_write.h` is third-party (public domain / MIT dual licence): mention it in the README.

### 5.4 README outline
1. What: `mesioFoam` (function object `mesioVDB`: in-situ OpenVDB export through the Mesio
   in-situ API) and `anariVis` (function object + `anariVisRender`: in-situ / in-transit ANARI
   rendering with deep compositing).
2. Requirements: OpenFOAM v2606 (tested; `WM_LABEL_SIZE=32`), Mesio from your espreso fork
   branch `mjar/devel` (built with `--intwidth=32`; in-situ API version 2, i.e. at least
   commit (f) of section 1), OpenVDB 12, ANARI-SDK (jar091 fork),
   deepCompositing CPU build (jar091 fork), an ANARI device (barney_cpu, cyclesphi-anari, helide).
3. Build: environment variables needed by `Make/options`; `./Allwmake` in each module;
   output locations (`FOAM_USER_LIBBIN` / `ANARIVIS_LIBBIN`, `ANARIVIS_BINDIR`).
4. Usage: `functions` dictionary snippets (copy from `data/openfoam/mesioVDB_controlDict_example`,
   `data/openfoam/anariVis_*`).
5. Pointers to the workflow repo docs (`docs/notes/mesio_openfoam_functionobject.md`,
   `docs/notes/anari_openfoam_insitu_intransit.md`).
6. License: GPLv3+, third-party `stb_image_write.h`.

### 5.5 Commands (init in place, so all build scripts keep working unchanged)
```bash
cd $W/src/openfoam-insitu-modules
git init -b main
# write .gitignore (5.2), README.md (5.4), COPYING (GPLv3 text)
git add .gitignore README.md COPYING
git commit -F- <<'EOF'
Repository skeleton: README, license, .gitignore

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF

git add mesioFoam
git status --short --ignored mesioFoam  # check: no lnInclude/, no Make/linux64*/ staged
git commit -F- <<'EOF'
mesioFoam: mesioVDB function object (OpenVDB export through Mesio)

Exports registered volume fields (scalars, vector/tensor magnitudes or
components, derived fields of other function objects) as OpenVDB fog
volumes through the Mesio in-situ API (version 2), one file per export
step for all ranks. Freshness check of derived fields, vdbOnly output
policy audit, moving meshes, topology changes (MESIOInSituResetMesh),
several instances per run, writer/compression/sampling options
(sampling cell: exact cell values), units metadata per grid, memory
report, Mesio errors as FatalError or warning (onError error|warn),
safe run-time re-read of the settings (invalid entries are rejected,
changed grid settings re-create the context collectively).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF

git add anariVis
git status --short --ignored anariVis   # check: no lnInclude/, no Make/linux64*/ staged
git commit -F- <<'EOF'
anariVis: in-situ / in-transit ANARI rendering

Function object and anariVisRender application for in-situ and
in-transit rendering of OpenFOAM data with ANARI devices (barney,
cyclesphi-anari, helide) and deep compositing.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git log --oneline
git remote add origin git@github.com:jar091/openfoam-insitu-modules.git   # or code.it4i.cz
git push -u origin main
```
- [ ] repo created (empty, private), pushed
- [ ] verify: a fresh `git clone` into `$W/build/tmp_clone_check` contains only sources
- [ ] `src/openfoam-insitu-modules` is now the working copy of the new repo (no separate clone needed);
      if you prefer a clean clone: move the old directory away, `git clone` to the same path, rebuild.

---

## 6. New repository: workflow (`scripts/`, `data/`, `docs/` of `$W`)

### 6.1 Name and host (choose one)
- [ ] GitHub: `jar091/openfoam-insitu-workflow`
- [ ] code.it4i.cz: `<your-namespace>/openfoam-insitu-workflow`

Init the repo **in `$W` itself** with a whitelist `.gitignore`, so the scripts keep their paths
and `build/`, `install/`, `src/` (other repos) are never picked up.

### 6.2 Contents and sizes
| Path | Size | Decision |
|---|---|---|
| `scripts/` (build/env/run/test/vis scripts, `openfoam-etc/`, `cases/`, `tests/`, `tools/vdb_diff.cpp`) | 351 KB | include |
| `scripts/patches/` (3 obsolete espreso patches) | 49 KB | **exclude, then delete** (section 9) |
| `docs/` (design docs + `notes/`, including this file) | 770 KB | include |
| `data/anari_tests/`, `data/mesio_tests/`, `data/openfoam/` | < 150 KB | include |
| `data/cyclesphi/*.py, *.sh, template_vdb_volume.xml(.bin)`, `ppam2026_scripts_orig/` | small | include |
| `data/cyclesphi/scenes_ppam2026/` | 20 MB: two identical 9.8 MB `openfoam_ofstore.*.xml.bin` (git stores them once), 2 EXR (450 KB) | include (needed: the reader requires `scene.xml.bin` next to `scene.xml`); Git LFS optional |
| `data/cyclesphi/colormanagement/` | ~21 MB (Blender OCIO config, LUTs, ICC) | include (needed for rendering); third-party (Blender), state origin in README |
| `data/cyclesphi/colormanagement/config.ocio.old` | 60 KB, byte-identical to `config.ocio` | exclude (or delete) |
| `a.out` (workspace root, stray static test binary, 8.7 KB) | | exclude / delete |
| `build/` 3.9 GB, `install/` 4.0 GB, `src/` | | exclude (build trees, installs, separate repos) |
| scratch `/scratch/project/eu-25-121/milanjaros/openfoam/` (`runs/`, `renders/`, `fakehome/`) | | not under `$W`, never in git |

All files are below GitHub's 100 MB limit; total ~41 MB of data.

### 6.3 `.gitignore` (whitelist)
```
# ignore everything at the top level ...
/*
# ... except the workflow parts
!/.gitignore
!/README.md
!/scripts/
!/data/
!/docs/
# excluded inside the whitelisted parts
/scripts/patches/
/data/cyclesphi/colormanagement/config.ocio.old
*.log
log.*
__pycache__/
*.pyc
```

### 6.4 Hard-coded absolute paths (do not block the first commit; parameterise later)
`grep` found `/mnt/proj2/eu-25-121/milanjaros/openfoam` (project root) and
`/scratch/project/eu-25-121/milanjaros/openfoam` (scratch root, `fakehome`) in:

- env scripts (define the roots; make them the **only** place): `scripts/env_openfoam.sh` (`OF_SCRATCH`, l.13),
  `scripts/env_mesio.sh` (l.9-12), `scripts/env_anari.sh` (l.10-14), `scripts/env_cyclesphi_anari.sh` (l.15-19),
  `scripts/env_anari_openfoam.sh` (l.13), `scripts/env_mesio_openfoam.sh`, `scripts/env_cyclesphi.sh`
- build scripts: `build_mesio.sh:23`, `build_openvdb.sh:11`, `build_mesio_openfoam.sh:13-14`,
  `build_anariVis.sh:7-9`, `build_anari.sh`, `build_barney.sh`, `build_deepcompositing.sh`,
  `build_cyclesphi_anari.sh:18`, `build_openfoam.sh`, `build_cyclesphi.sh:13` (`/mnt/proj1/open-36-34/...` libs copy source)
  and `build_cyclesphi.sh:23` (`/home/milanjaros/git-lfs/bin`)
- run/test scripts: `run_mesio_test.sh:6`, `make_mesio_testcase.sh:11-12`, `run_anari_tests.sh`,
  `run_deepcomp_tests.sh`, `run_anariVis_cavity.sh:12`, `run_anariVis_cavity3D.sh:14,24`,
  `test_anariVis_cavity3D.sh`, `test_anariVis_cavity_matrix.sh`, `smoke_test_openfoam.sh`, `mesio_test.ecf`
- `scripts/cases/{ofexec.sh,ofexec_fast.sh,ofexec_vis.sh,ofexec_vis_mesiodev.sh,ofexec_vis_mesionext.sh}`
- `scripts/tests/{bench_mesioVDB_writer.sh,run_mesioVDB_cavity3D.sh,test_mesioVDB_cavity.sh,test_mesioVDB_errors.sh,test_mesioVDB_movingCone.sh,test_mesioVDB_refine.sh,test_mesioVDB_next.sh,test_mesioVDB_reread.sh}`
- `scripts/vis/{pyvdb.sh,render_frames_parallel.sh,follow_render_pitz.sh,make_mp4.sh}`
- `data/mesio_tests/{build.sh,run_tests.sh,run_writer_tests.sh,run_robustness_tests.sh}`, `data/cyclesphi/{render_vdb_series.sh,run_render_ppam_cpu.sh}`
- scene files: `data/cyclesphi/scenes_ppam2026/openfoam_ofstore.{512,512.closest,4000,4000.fix}.xml`
  (absolute path to `city.exr`)
- `data/cyclesphi/ppam2026_scripts_orig/*` (up to 63 occurrences per file; historical originals,
  keep as they are and say so in the README)

Suggested later commit: one `scripts/env_paths.sh` with
`PROJ_ROOT=${PROJ_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}` and
`SCRATCH_ROOT=${SCRATCH_ROOT:-/scratch/project/eu-25-121/$USER/openfoam}`, sourced by every
script instead of literal paths.

### 6.5 README outline
1. Purpose: OpenFOAM v2606 + Mesio (OpenVDB) + ANARI (barney, cyclesphi-anari, deepCompositing)
   in-situ / in-transit visualisation on Karolina (IT4I).
2. Layout: `scripts/` (env, build, run, tests, vis), `data/`, `docs/` (start with `docs/notes/`).
3. Source repositories and pinned commits (table from section 7).
4. Quick start: clone the source repos into `src/` at the pinned commits, then the build order
   `build_openvdb → build_mesio → build_openfoam → build_mesio_openfoam → build_anari →
   build_deepcompositing → build_barney / build_cyclesphi(_anari) → build_anariVis`.
5. Paths: `PROJ_ROOT`, `SCRATCH_ROOT`, `HOME` redirect to `fakehome`.
6. Third-party data: Blender colour management (`data/cyclesphi/colormanagement`), original
   ppam2026 scripts.

### 6.6 Commands
```bash
cd $W
git init -b main
# write .gitignore (6.3) and README.md (6.5)
git add .gitignore README.md scripts data docs
git status --short | grep -v '^A ' ; git status --short | wc -l   # expect ~127 added files, no build/, install/, src/, patches/
git commit -F- <<'EOF'
Workflow for OpenFOAM in-situ/in-transit visualisation on Karolina

Environment, build, run and test scripts, OpenFOAM site configuration
(FOAM_CONFIG_ETC overlay), test data and scenes, design documents and
working notes.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git remote add origin git@github.com:jar091/openfoam-insitu-workflow.git   # or code.it4i.cz
git push -u origin main
```
- [ ] repo created (private), pushed
- [ ] check that `git ls-files | grep -E '^(build|install|src)/|patches|\.log$'` prints nothing

---

## 7. Pinning the source repositories

**Recommendation: pin by commit hash in a table (README of the workflow repo plus
`docs/repos.lock` or similar), not by git submodules.**
Reasons: the workflow repo lives in the same directory as `src/` and the 9 source repos are
already independent clones with their own submodules (barney, cyclesphi); submodules would
force every source update to be a two-step commit, make `git status` in `$W` noisy (build
side-effects such as the embree map files), and break the in-place layout the scripts use.
A small `scripts/checkout_sources.sh` that clones/checks out each repo at the listed hash
gives the same reproducibility. Update the table whenever a build in `install/` is redone.

Current state (fill the new hashes after sections 1-3):

| `src/` dir | URL (to use in the table) | branch | commit (2026-10-26) |
|---|---|---|---|
| `espreso` | your repo from 1.1 | `mjar/devel` | `08eac5d9aecf74b89d99156b9acd37536fee5369` (+ commits (a)-(f): **update**) |
| `deepCompositing` | https://github.com/jar091/deepCompositing | `mjar/devel` | `7864a71e1ee708e60f70b4cf5f7ca2d63e0c41be` (+ CPU port commit: **update**) |
| `barney` | https://github.com/jar091/barney | `mjar/devel` | `7f46b5281bffdc2df8e3481a6e503f4a76609622` (+ conflict fix: **update**); submodules cuBQL `20f9db19`, embree `e9b8633e`, owl `4df4d285` |
| `ANARI-SDK` | https://github.com/jar091/ANARI-SDK | `mjar/devel` | `42388069f0a7dd6f0288b609a43b8aaf0db71625` |
| `umesh` | https://github.com/jar091/umesh | `mj/converters` | `c16a306eec4634b091287d9a54f3611ba5435b96` |
| `cyclesphi` | https://github.com/It4innovations/cyclesphi | `develop` | `07cda529e4bf3937ffea7f271ed6244fa5ac2c11` (Blender libs `lib/linux_x64` `30d9f881`) |
| `cyclesphi-anari` | https://github.com/It4innovations/cyclesphi-anari | `cyclesphi_dev` | `d053b1ae4435e3ee245363aaf06aa45b3720d9c8` |
| `hpc` | https://develop.openfoam.com/committees/hpc | `develop` | `a0b4ec82d556bc31d27edb9e2d6e809d1446f82d` |
| `OpenFOAM-v2606` | https://gitlab.com/openfoam/core/openfoam | tag `OpenFOAM-v2606` | `481094fdf34f11ed6d0d603ee59a858a0124236d` |
| `openfoam-modules` | new repo from section 5 | `main` | (first commit: **fill in**) |

Print the current values at any time with:
```bash
for d in $W/src/*/; do printf '%-18s %s %s\n' "$(basename $d)" "$(git -C $d rev-parse HEAD 2>/dev/null)" "$(git -C $d status --porcelain 2>/dev/null | wc -l) dirty"; done
```

---

## 8. Follow-up edits after the repos exist (do not edit before the commits are pushed)

Build scripts:
- [ ] `scripts/build_mesio.sh:2` ("working tree") and `:33-40`: patch logic is already removed;
      replace the in-situ file check with a check that `git status --porcelain` is empty
      (warn/abort on a dirty tree) and print `git rev-parse HEAD` into the log.
- [ ] `scripts/build_barney.sh:48-56`: comment says the conflict resolution is uncommitted; update.
      `:57-75`: `BARNEY_COMMIT` snapshot logic (`git archive` into `build/src_snapshots/`) is no
      longer needed once the fix is committed; simplify to "build the checked-out commit"
      (keep `BARNEY_SRC` if useful). `:76-80` conflict-marker guard can stay.
      `:18` says "patch embree": reword to "fix in the barney fork".
- [ ] `scripts/build_cyclesphi_anari.sh:5-10, 30-36`: symlink overlay workaround for the empty
      `cyclesphi` submodule. Alternative after you decide: `git -C src/cyclesphi-anari submodule
      update --init --reference $W/src/cyclesphi cyclesphi` (pinned commit equals
      `src/cyclesphi`, `--reference` avoids a second object store) and build `src/cyclesphi-anari`
      directly. Keeping the overlay is also fine; then document it in the README.
- [ ] `scripts/build_cyclesphi.sh:13` (`/mnt/proj1/open-36-34/...` libs source) and `:23`
      (`/home/milanjaros/git-lfs/bin`): parameterise.
- [ ] `scripts/build_anariVis.sh:9`, `scripts/build_mesio_openfoam.sh:18`: path
      `src/openfoam-insitu-modules/...` stays valid with the in-place init (section 5.5); only change if
      the modules repo is cloned elsewhere (then introduce `OF_MODULES_SRC`).
- [x] `src/openfoam-insitu-modules/mesioFoam/Make/options:2` comment no longer says "branch sc22"
      (done 2026-10-27: "Mesio in-situ API version 2"); optionally name your espreso repo there.
- [ ] Hard-coded roots (section 6.4).

Docs that still mention patches / uncommitted working trees (update in the workflow repo):
- [ ] `docs/notes/mesio_build.md:11` ("All changes are in the working tree"), `:27-29`, `:38`
      (row "Former patches"), `:60` ("reports the state of the former patches"), `:92-105`
      (table rows named `espreso-sc22-*.patch`, heading "Details of the in-situ API patch"):
      replace with the commit hashes of section 1 and the URL of your espreso repo.
- [ ] `docs/notes/anari_barney_build.md:32-45` (section "HEAD conflicts resolved in the working
      tree (uncommitted)", `git archive` snapshot, `build/src_snapshots/barney-4d9b843`),
      `:103` ("uncommitted"), `:214` ("Open: commit the conflict resolution"): replace with the
      new commit hash.
- [ ] `docs/notes/deepcompositing_cyclesphi_anari.md:86` mentions `build/deepcompositing_cudacheck`
      (removed in section 9): keep the result, drop the path.
- Not ours, keep as is: `scripts/env_openfoam.sh:9-10` and `docs/notes/openfoam_build.md:42-45`
  describe the EasyBuild easyconfig's `.patch` files that our `FOAM_CONFIG_ETC` overlay replaces
  ("no core files patched").

---

## 9. Cleanup checklist (user actions, after the commits above are pushed)

- [ ] `rm -r $W/scripts/patches` (3 obsolete espreso `.patch` files: `espreso-sc22-fix-elements-to-nodes-mpi.patch`,
      `espreso-sc22-insitu-api.patch`, `espreso-sc22-openvdb-store-balanced.patch`; contents are in
      espreso commits (a), (b), (c)-(f))
- [ ] `rm -r $W/build/src_snapshots` (only `barney-4d9b843`, 202 MB; `install/barney` does not
      depend on it; `build_barney.sh` would recreate it only with `BARNEY_COMMIT=<sha>`)
- [ ] `rm -r $W/build/deepcompositing_cudacheck $W/build/deepcompositing_cudacheck.log` (19 MB, compile-only CUDA check)
- [ ] `rm -r $W/install/mesio-wip` (229 MB) and `$W/install/mesio-asan` (292 MB); no script references them.
      Related build trees, same status: `$W/build/espreso-wip` (562 MB), `$W/build/espreso-asan` (690 MB),
      `$W/build/openfoam-modules-mesio-wip`, `$W/install/openfoam-modules-mesio-wip`
- [ ] `rm $W/a.out` (stray static test binary in the workspace root)
- [ ] `$W/data/cyclesphi/colormanagement/config.ocio.old` (identical to `config.ocio`): delete or keep excluded
- [ ] `$W/src/OpenFOAM-v2606/log.linux64GccDPInt32Opt`: move to `build/logs/` (section 4)
- [ ] ~19 GB scratch start data of pitzDaily3D (restart now uses `processor*/0.095401`):
      ```bash
      cd /scratch/project/eu-25-121/milanjaros/openfoam/runs/pitzDaily3D/62M
      rm -r processor*/0.0932695      # 2048 dirs, ~10 GB (decomposed DaRUS start fields)
      rm -r 0.0932695                 # serial ASCII copy, 9.4 GB
      rmdir restart_raw               # empty, if present
      ```
      The original restart stays in `runs/downloads/pitzDaily3D/` (tarball).
- [ ] `~/.ssh/known_hosts` line 83 (`cn356,10.48.17.116 ssh-ed25519 ...`, stale host key):
      `ssh-keygen -R cn356; ssh-keygen -R 10.48.17.116` (writes to `$HOME`, so only you do this)
- [ ] optional: `git -C $W/src/barney/submodules/embree checkout -- kernels/` (section 3)
