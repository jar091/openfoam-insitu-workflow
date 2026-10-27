# Environment for OpenFOAM v2606 built from source on Karolina (foss/2025b).
#
# Usage (bash, on a compute node, never on the login node for heavy work):
#     source /mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/env_openfoam.sh
#
# Third-party libraries (METIS, SCOTCH, KaHIP, CGAL, Boost, FFTW, readline)
# come from Lmod modules. They are wired into OpenFOAM through the
# FOAM_CONFIG_ETC mechanism (scripts/openfoam-etc/config.sh/*), so no core
# OpenFOAM file is patched. This mirrors what the EasyBuild easyconfig
# OpenFOAM-v2512-foss-2025a.eb + OpenFOAM-v2406-cleanup.patch do.

OF_ROOT=/mnt/proj2/eu-25-121/milanjaros/openfoam
OF_SCRATCH=/scratch/project/eu-25-121/milanjaros/openfoam

# ---------------------------------------------------------------------------
# Never write into the real $HOME
export HOME="$OF_SCRATCH/fakehome"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_DATA_HOME="$HOME/.local/share"
export CCACHE_DIR="$HOME/.ccache"
mkdir -p "$HOME" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME"

# ---------------------------------------------------------------------------
# Modules (toolchain foss/2025b = GCC 14.3.0 + OpenMPI 5.0.8 + FFTW/OpenBLAS)
module purge >/dev/null 2>&1
module load \
    foss/2025b \
    CMake/4.0.3-GCCcore-14.3.0 \
    Bison/3.8.2-GCCcore-14.3.0 \
    flex/2.6.4-GCCcore-14.3.0 \
    ncurses/6.5-GCCcore-14.3.0 \
    libreadline/8.2-GCCcore-14.3.0 \
    METIS/5.1.0-GCCcore-14.3.0 \
    SCOTCH/7.0.10-gompi-2025b \
    KaHIP/3.19-gompi-2025b \
    GMP/6.3.0-GCCcore-14.3.0 \
    MPFR/4.2.2-GCCcore-14.3.0 \
    Boost/1.88.0-GCC-14.3.0 \
    CGAL/6.0.1-GCCcore-14.3.0 \
    || return 1 2>/dev/null || exit 1

# ---------------------------------------------------------------------------
# OpenFOAM configuration
# Site overrides for third-party locations (absolute FOAM_CONFIG_ETC is allowed)
export FOAM_CONFIG_ETC="$OF_ROOT/scripts/openfoam-etc"
# Do not pick up user/group prefs from ~/.OpenFOAM or a site dir
export FOAM_CONFIG_MODE="o"

# shellcheck disable=SC1091
. "$OF_ROOT/src/OpenFOAM-v2606/etc/bashrc" \
    WM_COMPILER_TYPE=system \
    WM_COMPILER=Gcc \
    WM_PRECISION_OPTION=DP \
    WM_LABEL_SIZE=32 \
    WM_COMPILE_OPTION=Opt \
    WM_MPLIB=SYSTEMOPENMPI \
    WM_PROJECT_USER_DIR="$OF_SCRATCH/OpenFOAM-user"

# Extra flags (FOAM_EXTRA_* are reset by etc/bashrc, so set them afterwards).
# The easyconfig uses toolchainopts vectorize=False (-fno-tree-vectorize) and
# -march=native. Karolina CPU nodes are AMD EPYC 7H12 (Zen2); znver2 is
# explicit so the result does not depend on the build host.
export FOAM_EXTRA_CFLAGS="-march=znver2 -fno-tree-vectorize"
export FOAM_EXTRA_CXXFLAGS="-march=znver2 -fno-tree-vectorize"

# Parallel make for wmake
export WM_NCOMPPROCS="${WM_NCOMPPROCS:-128}"

# OpenMPI 5 / PRRTE: keep session dirs off $HOME
export TMPDIR="${TMPDIR:-/tmp}"

unset OF_ROOT OF_SCRATCH
