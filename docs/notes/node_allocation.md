# Node allocation for job 5270670 (32 x qcpu nodes, 128 cores each, CPU only)

All compute work runs inside job 5270670 via
`srun --jobid=5270670 --overlap -w <nodes> ...` (never on the login node).

| Nodes | Count | Use |
|---|---|---|
| cn356 | 1 | OpenFOAM v2606 build; later mesio function object development builds |
| cn357 | 1 | mesio / OpenVDB build and tests |
| cn358 | 1 | CyclesPhi build and single-node render tests |
| cn627 | 1 | ANARI-SDK + Barney (CPU) build and tests |
| cn628 | 1 | Light tasks, small OpenFOAM tests (cavity3D 1M/8M) |
| cn629-cn630 | 2 | deepCompositing (CPU) + cyclesphi-anari build and MPI tests |
| cn631-cn646 | 16 | Production simulation: pitzDaily3D 62M (XiFoam) with mesio VDB export / in-situ ANARI |
| cn647-cn650 | 4 | HPC_motorbike Small: parallel snappyHexMesh + simpleFoam |
| cn651-cn655 | 5 | Rendering: CyclesPhi frame-parallel VDB rendering; in-transit Barney/deepCompositing render nodes |

Notes:
- Once builds finish, the build nodes (cn356-cn358, cn627-cn630) join the render/in-transit pool.
- Frame-parallel rendering: one render process per node, frames distributed round-robin.
- Multi-node MPI: `srun --jobid=5270670 --overlap -N <n> -w <nodelist> --ntasks-per-node=128 ...`

## Second job 5275975 (32 x qcpu, from 2026-10-26 ~22:30)

Use `srun --jobid=5275975 --overlap -w <nodes> ...` for these nodes.

| Nodes (job 5275975) | Count | Use |
|---|---|---|
| cn309-cn316 | 8 | DLRCJH rendering (replaces the cn639-cn646 grant in job 5270670) |
| cn317-cn321 | 5 | Wind-farm LES case (run + render) |
| cn516-cn523 | 8 | fireFoam / reactingFoam DLRJHC (run + render) |
| cn524-cn529 | 6 | pitzDaily3D v2 rendering |
| cn001-cn005 | 5 | occDrivAerStaticMesh 65M (run + render) |
