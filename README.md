# openfoam-insitu-workflow

Workflow for in-situ and in-transit visualisation of OpenFOAM v2606 simulations on the
Karolina cluster (IT4Innovations):

- direct MPI-to-OpenVDB export through Mesio (function object `mesioVDB`),
- offline volume rendering of the VDB series with CyclesPhi (Cycles XML scenes),
- in-situ / in-transit rendering through ANARI (Barney CPU, cyclesphi-anari, helide) with
  deep compositing (function object `anariVis`).

The OpenFOAM modules themselves are in
[openfoam-insitu-modules](https://github.com/jar091/openfoam-insitu-modules). This repository
holds the environment, build, run and visualisation scripts, the test inputs and render
scenes, and the design documents and working notes.

## Layout

| Path | Contents |
|---|---|
| `scripts/` | `env_*.sh` (module loads and paths), `build_*.sh` (OpenVDB, Mesio, OpenFOAM, ANARI-SDK, Barney, deepCompositing, CyclesPhi, cyclesphi-anari, OpenFOAM modules), `run_*`/`test_*` scripts, `openfoam-etc/` (OpenFOAM site configuration used through `FOAM_CONFIG_ETC`), `cases/` (MPI launchers for job steps), `tests/`, `vis/` (frame-parallel and follow-mode rendering, MP4 assembly) |
| `data/openfoam/` | `controlDict` examples for `mesioVDB` and `anariVis` |
| `data/mesio_tests/`, `data/anari_tests/` | standalone test drivers for the Mesio in-situ API and the ANARI devices |
| `data/cyclesphi/` | CyclesPhi scene tools (`make_vdb_scene.py`, `render_vdb_series.sh`), colour management (Blender OCIO config), the original ppam2026 scenes and scripts, and per-case scenes in `scenes/<case>/` (XML + `.xml.bin`, shader node graphs documented in each `README.md`) |
| `docs/` | design documents (Mesio integration, ANARI in-situ / in-transit) and `notes/` (build notes, case preparation, production runs, animations per case) |

Start reading with `docs/notes/openfoam_build.md`, `docs/notes/mesio_openfoam_functionobject.md`
and `docs/notes/production_runs.md`.

## Source repositories

The scripts expect the source repositories under `src/` of the project root. State used for
the results in `docs/notes/`:

| `src/` directory | Repository | Branch | Commit |
|---|---|---|---|
| `OpenFOAM-v2606` | https://gitlab.com/openfoam/core/openfoam.git | tag `OpenFOAM-v2606` | `481094fdf34f` |
| `espreso` (Mesio) | git@code.it4i.cz:blender/espreso.git | `mjar/devel` | `a5f9e111ae08` |
| `ANARI-SDK` | https://github.com/jar091/ANARI-SDK.git | `mjar/devel` | `42388069f0a7` |
| `barney` | https://github.com/jar091/barney.git | `mjar/devel` | `1695eaa11791` |
| `barney/submodules/embree` | https://github.com/jar091/embree.git | `mjar/devel` | `c5d68d252bdc` |
| `deepCompositing` | https://github.com/jar091/deepCompositing.git | `mjar/devel` | `af9be22751bf` |
| `cyclesphi` | https://github.com/It4innovations/cyclesphi.git | `develop` | `07cda529e4bf` |
| `cyclesphi-anari` | https://github.com/It4innovations/cyclesphi-anari.git | `cyclesphi_dev` | `d053b1ae4435` |
| `umesh` | https://github.com/jar091/umesh.git | `mj/converters` | `c16a306eec46` |
| `hpc` (OpenFOAM HPC TC cases) | https://develop.openfoam.com/committees/hpc.git | `develop` | `a0b4ec82d556` |
| `openfoam-modules` | https://github.com/jar091/openfoam-insitu-modules.git | `main` | |

## Build order

All builds use foss/2025b (GCC 14.3, OpenMPI 5.0.8) and run on compute nodes:

1. `build_openvdb.sh` (OpenVDB 12, oneTBB, c-blosc)
2. `build_mesio.sh` (`MESIO_VARIANT` selects the install prefix)
3. `build_openfoam.sh`
4. `build_mesio_openfoam.sh` (`mesioFoam`)
5. `build_anari.sh`, `build_deepcompositing.sh`, `build_barney.sh` (CPU backend),
   `build_cyclesphi.sh`, `build_cyclesphi_anari.sh`
6. `build_anariVis.sh` (`anariVis`)

## Paths

The scripts currently contain the Karolina project root
(`/mnt/proj2/eu-25-121/milanjaros/openfoam`) and the scratch root
(`/scratch/project/eu-25-121/milanjaros/openfoam`) as literals; the list of files is in
`docs/REPOSITORIES_TODO.md`, section 6.4. All generated data (cases, VDB files, images,
logs) goes to scratch, and compute steps redirect `HOME` to a directory on scratch.

## Third-party content

- `data/cyclesphi/colormanagement/`: Blender colour management configuration (OCIO config,
  LUTs).
- `data/cyclesphi/ppam2026_scripts_orig/` and `data/cyclesphi/scenes_ppam2026/`: original
  ppam2026 render scripts and scenes, kept unchanged for reference.

## Development

AI agent harnesses were used for selected development, testing, and optimization tasks
