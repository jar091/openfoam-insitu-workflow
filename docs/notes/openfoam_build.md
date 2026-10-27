# OpenFOAM v2606: build notes (Karolina, foss/2025b, no EasyBuild)

Status: 2026-10-26. Built and smoke-tested on Karolina `cn356` (job 5270670).
`foamInstallationTest`: "Base configuration ok. Critical systems ok."

## Source

```
src/OpenFOAM-v2606   # git clone --depth 1 --branch OpenFOAM-v2606 \
                     #   https://gitlab.com/openfoam/core/openfoam.git   (commit 481094fd)
```

Submodules (plugins/cfmesh, modules/adios, OpenQBMM, visualization, ...) are
**not** initialised. The core build does not need them. Add them later with
`git submodule update --init <path>` + `./Allwmake-plugins` / `./Allwmake-modules` if needed.

Build output stays inside the source tree:
`src/OpenFOAM-v2606/platforms/linux64GccDPInt32Opt/{bin,lib}` (~0.6 GB),
objects in `src/OpenFOAM-v2606/build/` (~2 GB). `install/` is not used.

## Modules (all foss/2025b compatible)

```
foss/2025b                      # GCC 14.3.0, OpenMPI 5.0.8, FFTW 3.3.10, OpenBLAS
CMake/4.0.3-GCCcore-14.3.0
Bison/3.8.2-GCCcore-14.3.0
flex/2.6.4-GCCcore-14.3.0
ncurses/6.5-GCCcore-14.3.0
libreadline/8.2-GCCcore-14.3.0
METIS/5.1.0-GCCcore-14.3.0      # idx 32-bit, real 64-bit
SCOTCH/7.0.10-gompi-2025b       # SCOTCH_Num = int, static libs + ptscotch
KaHIP/3.19-gompi-2025b
GMP/6.3.0-GCCcore-14.3.0
MPFR/4.2.2-GCCcore-14.3.0
Boost/1.88.0-GCC-14.3.0         # needed by CGAL (CGAL module does not load it)
CGAL/6.0.1-GCCcore-14.3.0       # header-only flavour
```

Skipped vs. the easyconfig `OpenFOAM-v2512-foss-2025a.eb`: ParaView (no reader
plugins), gnuplot (runtime-only, optional).

## Configuration (no core files patched)

The easyconfig uses `OpenFOAM-v2406-cleanup.patch` (prefs.sh + `etc/easybuild/config.sh/*`)
and `OpenFOAM-v2212-wmake-OpenMPI.patch` (EASYBUILDMPI rule). Same effect here via:

* `FOAM_CONFIG_ETC=/mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/openfoam-etc`
  (absolute path is allowed), containing `config.sh/{metis,scotch,kahip,readline,FFTW,CGAL}`
  that point `*_ARCH_PATH` to `$EBROOT*` of the modules, and
  `config.sh/prefs.sys-openmpi` that sets `MPI_ARCH_PATH=$EBROOTOPENMPI`.
* `FOAM_CONFIG_MODE=o` so nothing from `~/.OpenFOAM` or a site dir is read.
* Arguments to `etc/bashrc`:
  `WM_COMPILER=Gcc WM_PRECISION_OPTION=DP WM_LABEL_SIZE=32 WM_COMPILE_OPTION=Opt
  WM_MPLIB=SYSTEMOPENMPI WM_PROJECT_USER_DIR=/scratch/project/eu-25-121/milanjaros/openfoam/OpenFOAM-user`
  -> `WM_OPTIONS=linux64GccDPInt32Opt`, `FOAM_MPI=sys-openmpi`.
* Flags: upstream `-O3 -std=c++17` plus
  `FOAM_EXTRA_CFLAGS/FOAM_EXTRA_CXXFLAGS="-march=znver2 -fno-tree-vectorize"`
  (easyconfig: `vectorize: False` + `-march=native`; znver2 = Karolina CPU nodes, AMD EPYC 7H12).
  These must be exported *after* sourcing `etc/bashrc` (it unsets them).
* `HOME`, `XDG_*`, `CCACHE_DIR` -> `/scratch/project/eu-25-121/milanjaros/openfoam/fakehome`.

Detected by wmake: METIS, SCOTCH + PT-SCOTCH, KaHIP, CGAL (header) + Boost, FFTW, readline.
Built decomposition libs: `libmetisDecomp`, `libscotchDecomp`, `libptscotchDecomp`,
`libkahipDecomp`; CGAL tools `foamyHexMesh`, `foamyQuadMesh` built too.
272 executables, 133 libraries.

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/env_openfoam.sh` | module loads + exports + `source etc/bashrc ...` |
| `scripts/build_openfoam.sh` | `./Allwmake -j 128 -s -l`, log `build/logs/openfoam_build.log` (+ `src/OpenFOAM-v2606/log.linux64GccDPInt32Opt`) |
| `scripts/smoke_test_openfoam.sh` | foamInstallationTest, serial + 4-rank cavity; log `build/logs/openfoam_smoke.log` |
| `scripts/openfoam-etc/config.sh/*` | third-party locations (FOAM_CONFIG_ETC) |

## Build

```
srun --jobid=5270670 --overlap -N1 -n1 -c 128 -w cn356 \
    bash /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/build_openfoam.sh
```

Took 95 min wall (user 714 min, sys 399 min). Zero compile errors; only
harmless warnings (unused variables, maybe-uninitialized in PDRutilsIntersect.C).

## Using the build

```
# on a compute node (inside the job), bash:
source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_openfoam.sh
which icoFoam   # .../src/OpenFOAM-v2606/platforms/linux64GccDPInt32Opt/bin/icoFoam
```

Run cases on scratch, e.g. `/scratch/project/eu-25-121/milanjaros/openfoam/runs/<case>`.

## Parallel runs inside job 5270670

Option A: direct Slurm launch (PMIx), from the login node or any shell:

```
srun --jobid=5270670 --overlap -N1 -n4 -w cn356 --mpi=pmix bash -c '
  source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_openfoam.sh >/dev/null 2>&1
  cd /scratch/project/eu-25-121/milanjaros/openfoam/runs/<case>
  exec icoFoam -parallel' > log.icoFoam 2>&1
```

For multi-node: `-N<n> --ntasks-per-node=<k> -w <nodelist>`.

Option B: `mpirun` inside a single-task step. **Gotcha:** OpenMPI 5 (PRRTE)
detects Slurm and tries to start its daemons with `srun`, which fails inside an
existing step ("srun returned non-zero exit status (256) from launching the
per-node daemon"). Disable the Slurm launcher/allocator:

```
srun --jobid=5270670 --overlap -N1 -n1 -c 8 -w cn356 bash -c '
  source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_openfoam.sh
  cd <case>; decomposePar
  mpirun --prtemca plm ^slurm --prtemca ras ^slurm -np 4 --bind-to core icoFoam -parallel'
```

(This only works on the node of the step; use option A for multiple nodes.)

## Smoke test result

`/scratch/project/eu-25-121/milanjaros/openfoam/runs/smoke_cavity`:

* `serial/`: blockMesh + icoFoam cavity, 100 steps, `End`.
* `parallel4/`: decomposePar (scotch, 4) + `mpirun` 4 ranks + reconstructPar, `End`.
  Max |U_serial - U_parallel| at t=0.5 is 1e-6 (= solver tolerance) for max |U| = 0.85.
* `parallel4_srun/`: same case launched with `srun -n4 --mpi=pmix`, `End`.

## Gotchas

* `/mnt/proj2` is NFS: the build is I/O bound (load stayed around 10 on 128 cores,
  `dep:` scanning is slow). Next time try `./Allwmake -j 128 -s -q -l` (queue mode, one
  big make over all objects) or build on scratch/local `/tmp` and copy back.
* `etc/bashrc` sets `WM_PROJECT_USER_DIR=$HOME/OpenFOAM/...`; it is overridden via
  a bashrc argument, so user binaries/libs go to scratch.
* OpenMPI 5 has no `orte-info`; `MPI_ARCH_PATH` is therefore set explicitly in
  `prefs.sys-openmpi`.
* The `KaHIP` module also loads Python 3.13.5 and GKlib-METIS (headers only, no
  conflict with METIS).
* `XALT` is a sticky module that stays loaded after `module purge`; harmless.
