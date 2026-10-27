# OpenFOAM HPC Technical Committee cases - survey for OpenVDB / in-situ demo

Clone: `/mnt/proj2/eu-25-121/milanjaros/openfoam/src/hpc` (shallow, from https://develop.openfoam.com/committees/hpc.git; ~500 MB).
Cases were surveyed only (nothing was run). Paths are relative to the clone root.

## Case table

| Case (path) | Solver / physics | Mesh generation | Sizes | External inputs | Volume-render candidates | Demo fit |
|---|---|---|---|---|---|---|
| `incompressible/icoFoam/cavity3D/{1M,8M,64M}/fixedIter` | icoFoam, laminar, Re=10, 15 steps benchmark | `blockMesh` (uniform hex), `decomposePar`, `renumberMesh` | 1M / 8M / 64M | none | `mag(U)`, `p`, vorticity (smooth, low-contrast flow) | Pure I/O + pipeline test. Not visually interesting (steady creeping vortex). Trivial and fast. |
| `incompressible/simpleFoam/HPC_motorbike/{Small,Medium,Large}/v1912` (also `v8`) | simpleFoam steady RANS, kOmegaSST | `AllmeshS` = blockMesh + parallel `snappyHexMesh` (+ reconstructParMesh); M/L made by mirrorMesh | S 8.5M / M 17M / L 34M | none (`motorBike.obj.gz` is in the repo) | `mag(U)` wake, `p`, `Q` (steady, so only one snapshot per iteration) | Good geometry, recognisable object. Steady: in-situ gives "converging solution" animation. Meshing takes ~35 min on 16 cores. |
| `incompressible/simpleFoam/occDrivAerStaticMesh` | simpleFoam steady RANS, car, 140 km/h | none, pre-generated polyMesh | 65M / 110M / 236M | YES: polyMesh tarballs from Zenodo record 15012221 (`polyMesh_65M/110M/236M.tar.gz`, put in `constant/`) | `mag(U)`, `p`, total pressure (wake) | Impressive but heavy and large downloads; needs >= 4 nodes. |
| `incompressible/simpleFoam/conicalDiffuser/{3M,100M}` | simpleFoam RANS (ERCOFTAC diffuser) | `m4` -> `blockMesh` | 3M / 100M | none | `mag(U)`, separation | Simple geometry (cone), less visual. |
| `incompressible/pimpleFoam/LES/*` (conicalDiffuser, offshorewindpark, modelwindfarm, aerodynamicsDrivAer, occDrivAerRotMesh, wheelRotMesh) | pimpleFoam LES/DDES, wind farm with actuator line, DrivAer | mostly pre-generated meshes / inflow data (python script for offshorewindpark) | large | mostly external meshes | wake `mag(U)`, vorticity, Q | Wind park wake would look great but needs inflow generation + large mesh. Not a quick start. |
| `combustion/XiFoam/pitzDaily3D/{3M,62M}/fixedIter` | XiFoam, LES premixed combustion, transient, backward-facing step | `m4` -> `blockMesh`, `0_orig` -> `0`, `decomposePar` (`Allpre`) | 3M / 62M | none | `T`, `b` (regress variable / flame front), `mag(U)`, Q-criterion | BEST demo candidate: self-contained, transient, flame + shear-layer vortices, README thumbnail is a 62M rendering. Benchmark runs only 20 steps of 1e-9 s. |
| `combustion/XiFoam/DLRCJH` | XiFoam LES, DLR gas-turbine combustor | `mesh/{3M,24M,489M}/Allrun` | 3M / 24M / 489M | restart files from external link (see README) | `T`, `b`, swirl `mag(U)`, Q | Spectacular but needs restart files and cases are heavy. |
| `combustion/reactingFoam/LES/DLRJHC/{1M,4M,11M}` | reactingFoam LES, detailed chemistry, jet in hot coflow | `m4`->`blockMesh`, `addSwirlAndRotation` | 1M / 4M / 11M | none | `T`, species (OH, CH4), `mag(U)` | Chemistry-dominated: very slow per step, small box. Visually good for T but wall time high. |
| `combustion/reactingFoam/laminar/counterFlowFlame` | laminar flame 2D | blockMesh | small | none | none (2D) | not suitable |
| `combustion/fireFoam/RAS/stecklerWithSpray` | fireFoam + spray, room fire | `Allrun.pre` | n/a | check README | `T`, soot, smoke | Nice smoke/fire volume, but more setup; secondary option. |
| `compressible/rhoPimpleFoam/LES/*` (DrivAer aeroacoustic, high-lift CRM, propeller, ...) | rhoPimpleFoam LES/DDES | pre-generated/complex | 10M-1B+ | external meshes | `p` acoustic waves, Q | Heavy, external data; not for a quick demo. |
| `compressible/rhoPimpleFoam/laminar/*WaveTrain`, `hydroacousticSheddingCylinder` | 1D/2D | simple | small | none | none (1D/2D) | not suitable for 3D volume rendering |
| `lagrangian/sprayFoam/gasSprayPenetration` | sprayFoam | blockMesh | small | none | spray + `T` | Lagrangian parcels, not field-only. |
| `viscoelastic/*` | viscoelasticFluidFoam (custom solver in `src/`, 2D cavity / 3D extrusion) | blockMesh | small-medium | custom solver needs compiling | stress, velocity | Custom solver; skip. |
| `incompressible/adjointOptimisationFoam/*` | adjoint | - | - | custom | - | skip |

Notes: README versions say validated with v2106/v2412; a v2606 run may need small fixes (e.g. `Allrun` calls `$WM_PROJECT_DIR/bin/tools/RunFunctions`, which still exists).

## Recommendations

### (a) Quick test (minutes, 1 node, 128 cores): `incompressible/icoFoam/cavity3D/8M/fixedIter`
(or 1M for a smoke test). Uniform hex mesh, no downloads, blockMesh takes seconds, 15 steps. Ideal to validate the OpenVDB conversion + in-situ hook path (structured-like, regular data, `mag(U)`, `p`). Add `-fileHandler` none; set `numberOfSubdomains 128` in `system/decomposeParDict`.
```
cd src/hpc/incompressible/icoFoam/cavity3D/8M/fixedIter
# edit system/decomposeParDict: numberOfSubdomains 128 (scotch)
./Allpre      # blockMesh, decomposePar, renumberMesh
mpirun -np 128 icoFoam -parallel     # Allrun does this via runParallel
```
To get something to render: set `endTime 0.05` (or more) with `deltaT 0.0005` (Co=1 kept), `writeInterval 20`, `writeFormat binary`; the in-situ function object triggers on `execute` each N steps.
Alternative with more visual contrast (still minutes): `combustion/XiFoam/pitzDaily3D/3M/fixedIter` on one node (see below).

### (b) Visually impressive demo (few nodes, <= ~1h): `combustion/XiFoam/pitzDaily3D/62M/fixedIter`
Transient LES premixed flame; `T` and `b` give a clear flame-front volume rendering, `mag(U)`/Q show the shear-layer vortices behind the step. No downloads, mesh from blockMesh (m4). 62M cells fits 4 nodes (512 cores) comfortably; use 3M on 1 node for dry runs.
```
cd src/hpc/combustion/XiFoam/pitzDaily3D/62M/fixedIter
# edit system/decomposeParDict: numberOfSubdomains 512 (match srun -n)
./Allpre                                   # m4 -> blockMesh, 0_orig->0, decomposePar
srun -n 512 XiFoam -parallel > log.XiFoam  # Allrun = Allpre + runParallel
```
Changes for a longer, nicer run: in `system/controlDict` raise `endTime` from `20e-9` (only 20 steps of 1e-9 s; check actual `deltaT` in the file, usually adjustable time step) to e.g. `5e-3` so the flame develops, set `writeControl timeStep; writeInterval 50` (or rely only on the in-situ function object), keep `writeFormat binary`. Flow is ~13 m/s so ~1 ms covers several flow-through times of the step region; expect long wall time at 62M, so limit with `endTime` to what fits ~1h (use `stopAt writeNow`/`wallClock` controls if needed). Also check `fvSolution.fixedIter` (fixed linear iterations) vs `fixedTol` - fixedTol is more robust for a physical run.

### Backup for (b): `incompressible/simpleFoam/HPC_motorbike/Small/v1912` (8.5M)
Recognisable geometry, no downloads (`motorBike.obj.gz` included), `snappyHexMesh` in parallel (`./AllmeshS`, then `./Allrun`; set `numberOfSubdomains` in `system/decomposeParDict`, default 500 iterations, deltaT 1). Steady RANS, so render `mag(U)` / `p` iso-volumes every ~10 iterations as the solution converges. Do meshing once, mirror to M/L if more cells wanted. Use `v1912` dir unless v8 is explicitly preferred.

### Not recommended now
occDrivAerStaticMesh (huge Zenodo downloads, 65-236M cells), DLRCJH (restart files, heavy), reactingFoam DLRJHC (chemistry cost), compressible LES (external data).
