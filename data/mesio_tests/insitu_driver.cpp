// Standalone MPI test driver for the MESIO in-situ API (include/mesio_insitu.h).
//
// Builds a block-decomposed hexahedral finite-volume mesh in memory, in the OpenFOAM
// polyMesh layout (points, faces, owner, neighbour; internal faces first; processor
// faces as boundary faces), writes a few steps of cell fields to one .vdb per step and
// verifies the written file on rank 0:
//   - grid class is fog volume, "time" metadata is present,
//   - the field 'linear' = x + 2y + 3z + step, sampled at the world position of each
//     active voxel (grid->indexToWorld(ijk)), matches the analytic value for voxels
//     at least one cell away from the domain boundary (checks the index-to-world transform);
//     with --sampling cell it must equal the value of the cell containing the voxel centre,
//   - all active voxels lie inside the domain (or the box),
//   - --constant: every active voxel of every grid has the constant cell value.
//
// Usage: mpirun -n P insitu_driver --out DIR [--cells NX NY NZ] [--steps S]
//            [--voxel H | --density N] [--box x0 y0 z0 x1 y1 z1] [--moving] [--verbose]
//            [--setups K]          repeat Create/SetFVMesh/Commit/(steps)/Destroy K times (stress)
//            [--extra N]           N additional scalar fields (extra0..), e.g. to get 4 grids
//            [--noverify]          skip the verification on rank 0 (large benchmarks)
//            [--writer W]          distributed | parallel | single (legacy single-writer path); default: library
//            [--compression C]     blosc | none; default: library
//            [--fpe]               trap FE_DIVBYZERO | FE_INVALID | FE_OVERFLOW (as OpenFOAM's FOAM_SIGFPE)
//            [--empty K]           the last K ranks pass an empty mesh (no cells)
//            [--constant]          constant fields (linear = 1.25, blob = 0.5, |vel| = 1)
//            [--sampling S]        cellPoint | cell
//            [--contexts 2]        a second context (voxel size x2, no box) written at every step
//            [--resetmesh]         topology change test: ResetMesh + SetFVMesh + Commit before every step > 0
//            [--metadata]          set "units" metadata of every field and verify it
//            [--memory]            enable the per-write peak-RSS tracking and print the memory statistics
//            [--error KIND]        error handling test before the normal run, KIND =
//                                  grid (too large grid) | mesh (invalid index on one rank) |
//                                  file (unwritable output) | settings (differ between ranks) |
//                                  field (unknown field on one rank) | zerobox (zero-extent box with density) |
//                                  moving (moving mesh exceeds the grid limit: error inside MESIO, ResetMesh recovery)

#include "mesio_insitu.h"

#include <openvdb/openvdb.h>

#include <mpi.h>
#include <cfenv>
#include <cmath>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <execinfo.h>
#include <string>
#include <unistd.h>
#include <vector>

struct Options {
    std::string out = "insitu_out";
    int nx = 40, ny = 20, nz = 10, steps = 3;
    double L[3] = { 1.0, 0.5, 0.25 };
    double voxel = 0, box[6] = { 0, 0, 0, 0, 0, 0 };
    int density = 0, useBox = 0, moving = 0, verbose = 0;
    int setups = 1, extra = 0, verify = 1;
    int fpe = 0, empty = 0, constant = 0, contexts = 1, resetmesh = 0, metadata = 0, memory = 0;
    std::string writer, compression, sampling, error; // empty: library defaults
};

static double linear(double x, double y, double z, int step) { return x + 2 * y + 3 * z + step; }

static double blob(double x, double y, double z, int step, int steps)
{
    double cx = 0.25 + 0.5 * step / std::max(1, steps - 1), cy = 0.25, cz = 0.125, s = 0.08;
    double r2 = (x - cx) * (x - cx) + (y - cy) * (y - cy) + (z - cz) * (z - cz);
    return std::exp(-r2 / (2 * s * s));
}

static int worldRank = 0;

static void fpeHandler(int sig)
{
    char msg[128];
    int n = snprintf(msg, sizeof(msg), "[%d] SIGFPE (floating-point exception) caught, stack:\n", worldRank);
    if (write(STDERR_FILENO, msg, n) < 0) {}
    void *frames[64];
    int count = backtrace(frames, 64);
    backtrace_symbols_fd(frames, count, STDERR_FILENO);
    _exit(3);
}

// local mesh of this rank (empty ranks: no cells)
struct LocalMesh {
    int i0 = 0, i1 = 0, j0 = 0, j1 = 0, k0 = 0, k1 = 0, lx = 0, ly = 0, lz = 0;
    int nPoints = 0, nCells = 0, nFaces = 0, nInternal = 0;
    std::vector<double> points;
    std::vector<int> foff, fnodes, owner, neighbour;
    int pid(int i, int j, int k) const { return (i - i0) + (lx + 1) * ((j - j0) + (ly + 1) * (k - k0)); }
    int cid(int i, int j, int k) const { return (i - i0) + lx * ((j - j0) + ly * (k - k0)); }
};

static LocalMesh buildMesh(const Options &o, int rank, int size, const double h[3])
{
    LocalMesh m;
    int active = size - o.empty;
    m.foff.push_back(0);
    if (rank >= active) {
        return m;
    }
    int dims[3] = { 0, 0, 1 };
    MPI_Dims_create(active, 2, dims);
    int px = dims[0], py = dims[1], pz = 1;
    int rx = rank % px, ry = (rank / px) % py, rz = 0;
    auto split = [] (int n, int p, int r, int &b, int &e) { b = (long)n * r / p; e = (long)n * (r + 1) / p; };
    split(o.nx, px, rx, m.i0, m.i1); split(o.ny, py, ry, m.j0, m.j1); split(o.nz, pz, rz, m.k0, m.k1);
    m.lx = m.i1 - m.i0; m.ly = m.j1 - m.j0; m.lz = m.k1 - m.k0;
    m.nPoints = (m.lx + 1) * (m.ly + 1) * (m.lz + 1);
    m.nCells = m.lx * m.ly * m.lz;
    m.points.resize(3 * m.nPoints);
    for (int k = m.k0; k <= m.k1; ++k) for (int j = m.j0; j <= m.j1; ++j) for (int i = m.i0; i <= m.i1; ++i) {
        int p = m.pid(i, j, k);
        m.points[3 * p + 0] = i * h[0]; m.points[3 * p + 1] = j * h[1]; m.points[3 * p + 2] = k * h[2];
    }
    // faces: OpenFOAM orientation (right-hand normal points out of the owner)
    auto face = [&] (int d, int side, int i, int j, int k) { // d: axis, side 0 = lower, 1 = upper face of cell ijk
        int q[4];
        if (d == 0) { int x = i + side; q[0] = m.pid(x, j, k); q[1] = m.pid(x, j + 1, k); q[2] = m.pid(x, j + 1, k + 1); q[3] = m.pid(x, j, k + 1); }
        if (d == 1) { int y = j + side; q[0] = m.pid(i, y, k); q[1] = m.pid(i, y, k + 1); q[2] = m.pid(i + 1, y, k + 1); q[3] = m.pid(i + 1, y, k); }
        if (d == 2) { int z = k + side; q[0] = m.pid(i, j, z); q[1] = m.pid(i + 1, j, z); q[2] = m.pid(i + 1, j + 1, z); q[3] = m.pid(i, j + 1, z); }
        if (side == 0) { std::swap(q[1], q[3]); } // outward normal of the lower face points to -axis
        m.fnodes.insert(m.fnodes.end(), q, q + 4);
        m.foff.push_back(m.fnodes.size());
    };
    int lo[3] = { m.i0, m.j0, m.k0 }, hi[3] = { m.i1, m.j1, m.k1 };
    for (int k = m.k0; k < m.k1; ++k) for (int j = m.j0; j < m.j1; ++j) for (int i = m.i0; i < m.i1; ++i) {
        int c[3] = { i, j, k };
        for (int d = 0; d < 3; ++d) {
            if (c[d] + 1 < hi[d]) { // internal face shared with the +d neighbour (higher index)
                face(d, 1, i, j, k);
                m.owner.push_back(m.cid(i, j, k));
                m.neighbour.push_back(m.cid(i + (d == 0), j + (d == 1), k + (d == 2)));
            }
        }
    }
    m.nInternal = m.owner.size();
    for (int k = m.k0; k < m.k1; ++k) for (int j = m.j0; j < m.j1; ++j) for (int i = m.i0; i < m.i1; ++i) {
        int c[3] = { i, j, k };
        for (int d = 0; d < 3; ++d) {
            if (c[d] == lo[d]) { face(d, 0, i, j, k); m.owner.push_back(m.cid(i, j, k)); }     // domain or processor boundary
            if (c[d] + 1 == hi[d]) { face(d, 1, i, j, k); m.owner.push_back(m.cid(i, j, k)); }
        }
    }
    m.nFaces = m.owner.size();
    return m;
}

#ifdef MESIO_INSITU_HAS_ERROR_API
static const char* lastError(MESIOInSitu ctx) { return MESIOInSituLastError(ctx); }
#else
static const char* lastError(MESIOInSitu) { return "(no error API)"; }
#endif

static void check(int rc, const char *what, MESIOInSitu ctx)
{
    if (rc) {
        fprintf(stderr, "[%d] %s failed (code %d): %s\n", worldRank, what, rc, lastError(ctx));
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
}

static int setWriter(const Options &o, MESIOInSitu ctx)
{
#ifdef MESIO_INSITU_HAS_WRITER_OPTIONS
    if (o.writer.size() || o.compression.size()) {
        int writer = o.writer == "single" ? MESIO_INSITU_WRITER_SINGLE : o.writer == "parallel" ? MESIO_INSITU_WRITER_PARALLEL : MESIO_INSITU_WRITER_DISTRIBUTED;
        int compression = o.compression == "none" ? MESIO_INSITU_COMPRESSION_NONE : MESIO_INSITU_COMPRESSION_BLOSC;
        if (MESIOInSituSetWriterOptions(ctx, writer, compression)) return 1;
    }
#endif
#ifdef MESIO_INSITU_HAS_ERROR_API
    if (o.sampling.size()) {
        if (MESIOInSituSetSampling(ctx, o.sampling == "cell" ? MESIO_INSITU_SAMPLING_CELL : MESIO_INSITU_SAMPLING_CELLPOINT)) return 1;
    }
    if (o.memory) {
        MESIOInSituSetMemoryTracking(ctx, 1);
    }
#endif
    return 0;
}

// Error handling tests (MESIO_INSITU_HAS_ERROR_API): every case must return the expected code
// on all ranks, the process must survive, and a following normal run must work.
static int errorTest(const Options &o, const LocalMesh &m, int rank, int size)
{
#ifndef MESIO_INSITU_HAS_ERROR_API
    if (rank == 0) fprintf(stderr, "this Mesio build has no error API\n");
    return 1;
#else
    MESIOInSituSettings s;
    MESIOInSituDefaultSettings(&s);
    s.voxelSize = 0.01;
    int expected = MESIO_INSITU_ERROR_ARGUMENT, code = MESIO_INSITU_OK;
    const char *phase = "";
    MESIOInSitu ctx = nullptr;
    std::vector<double> values(m.nCells, 1.0), vel(3 * m.nCells, 1.0);
    auto create = [&] () {
        phase = "Create";
        code = MESIOInSituCreate(&ctx, MPI_COMM_WORLD, &s);
        return code == MESIO_INSITU_OK;
    };
    auto setup = [&] (bool commit) {
        int rc = MESIOInSituSetFVMesh(ctx, m.nPoints, m.points.data(), m.nFaces, m.foff.data(), m.fnodes.data(), m.owner.data(), m.nInternal, m.neighbour.data(), m.nCells);
        rc |= MESIOInSituAddCellField(ctx, "linear", 1);
        rc |= MESIOInSituAddCellField(ctx, "vel", 3);
        if (!commit) return rc == 0;
        phase = "Commit";
        code = MESIOInSituCommit(ctx);
        return code == MESIO_INSITU_OK;
    };
    auto write = [&] (const std::string &file) {
        MESIOInSituSetCellField(ctx, "linear", values.data());
        MESIOInSituSetCellField(ctx, "vel", vel.data());
        phase = "WriteVDB";
        code = MESIOInSituWriteVDB(ctx, 0.5, file.c_str());
        return code == MESIO_INSITU_OK;
    };

    if (o.error == "grid") {          // 1e6 voxels per axis: detected in Commit before the mesh build
        s.voxelSize = 1e-6;
        if (create() && setup(true)) write(o.out + "/never.vdb");
    } else if (o.error == "zerobox") { // zero-extent box with density: Create
        s.voxelSize = 0; s.density = 50; s.useBox = 1;
        for (int d = 0; d < 3; ++d) { s.boxMin[d] = s.boxMax[d] = 0.3; }
        if (create() && setup(true)) write(o.out + "/never.vdb");
    } else if (o.error == "settings") { // density differs on the last rank
        s.voxelSize = 0; s.density = rank == size - 1 ? 51 : 50;
        if (create() && setup(true)) write(o.out + "/never.vdb");
    } else if (o.error == "mesh") {    // invalid owner on the last rank: local error, reported by Commit everywhere
        if (create()) {
            LocalMesh bad = m;
            if (rank == size - 1 && bad.nFaces) bad.owner[0] = bad.nCells + 7;
            int rc = MESIOInSituSetFVMesh(ctx, bad.nPoints, bad.points.data(), bad.nFaces, bad.foff.data(), bad.fnodes.data(), bad.owner.data(), bad.nInternal, bad.neighbour.data(), bad.nCells);
            if (rank == size - 1 && rc != MESIO_INSITU_ERROR_ARGUMENT) { fprintf(stderr, "[%d] SetFVMesh did not detect the invalid owner\n", rank); return 1; }
            MESIOInSituAddCellField(ctx, "linear", 1); // fails on the last rank (no mesh)
            phase = "Commit";
            code = MESIOInSituCommit(ctx);
        }
    } else if (o.error == "field") {   // unknown field name on rank 0: reported by WriteVDB everywhere
        if (create() && setup(true)) {
            if (rank == 0 && MESIOInSituSetCellField(ctx, "nosuchfield", values.data()) != MESIO_INSITU_ERROR_ARGUMENT) { fprintf(stderr, "SetCellField did not fail\n"); return 1; }
            write(o.out + "/never.vdb");
        }
    } else if (o.error == "moving") {  // moving mesh grows beyond the grid limit: global error inside MESIO
        expected = MESIO_INSITU_ERROR_MESIO;
        s.voxelSize = 0.01; s.movingMesh = 1; // 101 voxels along x; 100001 after scaling
        if (create() && setup(true)) {
            std::vector<double> scaled(m.points);
            for (double &x : scaled) x *= 1000;
            MESIOInSituUpdatePoints(ctx, scaled.data());
            write(o.out + "/never.vdb");
            // the context failed: further writes are refused, ResetMesh recovers it
            int state = MESIOInSituWriteVDB(ctx, 0.5, (o.out + "/never.vdb").c_str());
            bool recovered = state == MESIO_INSITU_ERROR_STATE && MESIOInSituResetMesh(ctx) == MESIO_INSITU_OK;
            recovered = recovered && MESIOInSituSetFVMesh(ctx, m.nPoints, m.points.data(), m.nFaces, m.foff.data(), m.fnodes.data(), m.owner.data(), m.nInternal, m.neighbour.data(), m.nCells) == MESIO_INSITU_OK;
            recovered = recovered && MESIOInSituCommit(ctx) == MESIO_INSITU_OK;
            int saved = code;
            recovered = recovered && write(o.out + "/after_reset.vdb");
            code = saved;
            if (!recovered) { fprintf(stderr, "[%d] recovery by ResetMesh failed: %s\n", rank, lastError(ctx)); return 1; }
        }
    } else if (o.error == "file") {    // not writable: IO error on all ranks, the context stays usable
        expected = MESIO_INSITU_ERROR_IO;
        if (create() && setup(true)) write("/proc/mesio_no_such_dir/step.vdb");
    } else {
        if (rank == 0) fprintf(stderr, "unknown error test %s\n", o.error.c_str());
        return 1;
    }

    // the same code on all ranks
    int cmin = code, cmax = code;
    MPI_Allreduce(MPI_IN_PLACE, &cmin, 1, MPI_INT, MPI_MIN, MPI_COMM_WORLD);
    MPI_Allreduce(MPI_IN_PLACE, &cmax, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);
    const char *message = lastError(ctx);
    if (rank == 0 || rank == size - 1) {
        printf("[%d] error test %s: %s returned %d (expected %d): \"%s\"\n", rank, o.error.c_str(), phase, code, expected, message);
        fflush(stdout);
    }
    bool ok = cmin == cmax && code == expected && std::strlen(message) > 0;
    if (o.error == "mesh") { // the first local error of the failing rank is reported on all ranks
        ok &= std::strstr(message, "owner of face 0") != nullptr;
    }

    // recovery: the IO error keeps the context usable; otherwise destroy and start again
    if (o.error == "file" && ctx) {
        ok &= write(o.out + "/after_io_error.vdb");
    }
    MESIOInSituDestroy(ctx);
    ctx = nullptr;
    s.voxelSize = 0.01; s.density = 100; s.useBox = 0;
    ok &= create() && setup(true) && write(o.out + "/recovered.vdb");
    MESIOInSituDestroy(ctx);
    int all = ok;
    MPI_Allreduce(MPI_IN_PLACE, &all, 1, MPI_INT, MPI_MIN, MPI_COMM_WORLD);
    if (rank == 0) { printf("error test %s: %s\n", o.error.c_str(), all ? "OK" : "FAILED"); fflush(stdout); }
    return all ? 0 : 1;
#endif
}

// verification of one written file on rank 0
static bool verify(const Options &o, const char *name, int step, double shift, const double h[3], const double *box, bool cell)
{
    openvdb::io::File file(name);
    file.open();
    auto grid = openvdb::gridPtrCast<openvdb::FloatGrid>(file.readGrid("linear"));
    auto gblob = openvdb::gridPtrCast<openvdb::FloatGrid>(file.readGrid("blob"));
    auto gvel = openvdb::gridPtrCast<openvdb::FloatGrid>(file.readGrid("vel"));
    file.close();
    bool fog = grid->getGridClass() == openvdb::GRID_FOG_VOLUME;
    auto tmeta = grid->getMetadata<openvdb::DoubleMetadata>("time");
    bool units = true;
    if (o.metadata) {
        auto ul = grid->getMetadata<openvdb::StringMetadata>("units");
        auto uv = gvel->getMetadata<openvdb::StringMetadata>("units");
        units = ul && uv && ul->value() == "K" && uv->value() == "m s^-1";
    }
    double maxerr = 0, worst[3] = { 0, 0, 0 };
    size_t checked = 0, outside = 0;
    double lo3[3] = { shift, 0, 0 }, hi3[3] = { o.L[0] + shift, o.L[1], o.L[2] };
    for (int d = 0; d < 3 && box; ++d) { lo3[d] = std::max(lo3[d], box[d]); hi3[d] = std::min(hi3[d], box[3 + d]); }
    for (auto v = grid->cbeginValueOn(); v; ++v) {
        openvdb::Vec3d w = grid->indexToWorld(v.getCoord());
        bool inside = true;
        for (int d = 0; d < 3; ++d) inside &= lo3[d] - 1e-9 <= w[d] && w[d] <= hi3[d] + 1e-9;
        if (!inside) { ++outside; continue; }
        double err;
        if (o.constant) {
            err = std::fabs(*v - 1.25);
        } else {
            bool interior = w[0] > shift + 1.01 * h[0] && w[0] < o.L[0] + shift - 1.01 * h[0] &&
                            w[1] > 1.01 * h[1] && w[1] < o.L[1] - 1.01 * h[1] &&
                            w[2] > 1.01 * h[2] && w[2] < o.L[2] - 1.01 * h[2];
            if (!interior) continue;
            if (cell) { // the value of a cell containing the voxel centre (both cells for centres on faces)
                err = 1e30;
                double x[3] = { w[0] - shift, w[1], w[2] };
                int c0[3], c1[3];
                for (int d = 0; d < 3; ++d) { c0[d] = std::floor(x[d] / h[d] - 1e-6); c1[d] = std::floor(x[d] / h[d] + 1e-6); }
                for (int i = c0[0]; i <= c1[0]; ++i) for (int j = c0[1]; j <= c1[1]; ++j) for (int k = c0[2]; k <= c1[2]; ++k) {
                    err = std::min(err, std::fabs(*v - linear((i + .5) * h[0] + shift, (j + .5) * h[1], (k + .5) * h[2], step)));
                }
            } else {
                err = std::fabs(*v - linear(w[0], w[1], w[2], step));
            }
        }
        ++checked;
        if (err > maxerr) { maxerr = err; worst[0] = w[0]; worst[1] = w[1]; worst[2] = w[2]; }
    }
    float blobmax = 0, blobmin = 1e30f, velmin = 1e30f, velmax = 0;
    for (auto v = gblob->cbeginValueOn(); v; ++v) { blobmax = std::max(blobmax, *v); blobmin = std::min(blobmin, *v); }
    for (auto v = gvel->cbeginValueOn(); v; ++v) { velmax = std::max(velmax, *v); velmin = std::min(velmin, *v); }
    bool constant = !o.constant || (std::fabs(blobmin - 0.5f) < 1e-6 && std::fabs(blobmax - 0.5f) < 1e-6 && std::fabs(velmin - 1.f) < 1e-6 && std::fabs(velmax - 1.f) < 1e-6);
    bool empty = false; // the box does not intersect the mesh: no active voxel expected
    for (int d = 0; d < 3; ++d) empty |= lo3[d] > hi3[d];
    if (empty) {
        bool ok = fog && tmeta && grid->activeVoxelCount() == 0 && gblob->activeVoxelCount() == 0 && gvel->activeVoxelCount() == 0;
        printf("  verify %s: box outside the mesh, active %zu -> %s\n", name, (size_t)grid->activeVoxelCount(), ok ? "OK" : "FAILED");
        fflush(stdout);
        return ok;
    }
    bool ok = fog && tmeta && std::fabs(tmeta->value() - 0.1 * step) < 1e-12 && checked > 0 && maxerr < 1e-4 && outside == 0 && units && constant
              && gblob->activeVoxelCount() == grid->activeVoxelCount() && gvel->activeVoxelCount() == grid->activeVoxelCount();
    printf("  verify %s: class %s, time %s, active %zu, checked %zu voxels, max|linear - %s| = %.3g at (%.4f %.4f %.4f), outside %zu, blob [%.3f %.3f], vel [%.3f %.3f]%s -> %s\n",
           name, fog ? "fog" : "NOT FOG", tmeta ? std::to_string(tmeta->value()).c_str() : "missing",
           (size_t)grid->activeVoxelCount(), checked, o.constant ? "1.25" : cell ? "cell value" : "(x+2y+3z+t)", maxerr, worst[0], worst[1], worst[2], outside,
           blobmin, blobmax, velmin, velmax, o.metadata ? (units ? ", units OK" : ", units WRONG") : "", ok ? "OK" : "FAILED");
    fflush(stdout);
    return ok;
}

int main(int argc, char **argv)
{
    MPI_Init(&argc, &argv); // like OpenFOAM: no MPI_THREAD_MULTIPLE requested
    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    worldRank = rank;

    Options o;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--out") o.out = argv[++i];
        else if (a == "--cells") { o.nx = atoi(argv[++i]); o.ny = atoi(argv[++i]); o.nz = atoi(argv[++i]); }
        else if (a == "--steps") o.steps = atoi(argv[++i]);
        else if (a == "--voxel") o.voxel = atof(argv[++i]);
        else if (a == "--density") o.density = atoi(argv[++i]);
        else if (a == "--box") { o.useBox = 1; for (int d = 0; d < 6; ++d) o.box[d] = atof(argv[++i]); }
        else if (a == "--moving") o.moving = 1;
        else if (a == "--verbose") o.verbose = 1;
        else if (a == "--setups") o.setups = atoi(argv[++i]);
        else if (a == "--extra") o.extra = atoi(argv[++i]);
        else if (a == "--noverify") o.verify = 0;
        else if (a == "--writer") o.writer = argv[++i];
        else if (a == "--compression") o.compression = argv[++i];
        else if (a == "--fpe") o.fpe = 1;
        else if (a == "--empty") o.empty = atoi(argv[++i]);
        else if (a == "--constant") o.constant = 1;
        else if (a == "--sampling") o.sampling = argv[++i];
        else if (a == "--contexts") o.contexts = atoi(argv[++i]);
        else if (a == "--resetmesh") o.resetmesh = 1;
        else if (a == "--metadata") o.metadata = 1;
        else if (a == "--memory") o.memory = 1;
        else if (a == "--error") o.error = argv[++i];
        else { if (rank == 0) fprintf(stderr, "unknown option %s\n", a.c_str()); MPI_Abort(MPI_COMM_WORLD, 1); }
    }
    if (o.empty >= size) { if (rank == 0) fprintf(stderr, "--empty must be smaller than the number of ranks\n"); MPI_Abort(MPI_COMM_WORLD, 1); }

    if (o.fpe) { // as OpenFOAM (sigFpe): after MPI_Init, before any MESIO/OpenVDB call
        feenableexcept(FE_DIVBYZERO | FE_INVALID | FE_OVERFLOW);
        signal(SIGFPE, fpeHandler);
        if (rank == 0) printf("floating-point exception trapping enabled (FE_DIVBYZERO | FE_INVALID | FE_OVERFLOW)\n");
    }

    double h[3] = { o.L[0] / o.nx, o.L[1] / o.ny, o.L[2] / o.nz };
    LocalMesh m = buildMesh(o, rank, size, h);
    openvdb::initialize();

    if (o.error.size()) {
        int rc = errorTest(o, m, rank, size);
        if (rank == 0) printf("%s\n", rc ? "TEST FAILED" : "TEST PASSED");
        MPI_Finalize();
        return rc;
    }

    MESIOInSituSettings s;
    MESIOInSituDefaultSettings(&s);
    if (o.voxel > 0) s.voxelSize = o.voxel;
    if (o.density > 0) s.density = o.density;
    if (o.useBox) { s.useBox = 1; for (int d = 0; d < 3; ++d) { s.boxMin[d] = o.box[d]; s.boxMax[d] = o.box[3 + d]; } }
    s.movingMesh = o.moving;
    s.verbosity = o.verbose;
    MESIOInSituSettings s2 = s; // second context: double voxel size, whole mesh
    s2.useBox = 0;
    s2.voxelSize = 2 * (o.voxel > 0 ? o.voxel : 0.01);
#ifndef MESIO_INSITU_HAS_WRITER_OPTIONS
    if (o.writer.size() || o.compression.size()) {
        if (rank == 0) fprintf(stderr, "this Mesio build has no writer options\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
#endif
#ifndef MESIO_INSITU_HAS_ERROR_API
    if (o.empty || o.sampling.size() || o.contexts > 1 || o.resetmesh || o.metadata || o.memory) {
        if (rank == 0) fprintf(stderr, "this Mesio build has no error API (empty ranks, sampling, contexts, ResetMesh, metadata, memory)\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
#endif

    int failures = 0;
    std::vector<double> flin(m.nCells), fblob(m.nCells), fvel(3 * m.nCells), fextra(m.nCells), moved(m.points);
    for (int setup = 0; setup < o.setups; ++setup) {
    MPI_Barrier(MPI_COMM_WORLD);
    double t0 = MPI_Wtime();
    std::vector<MESIOInSitu> ctx(o.contexts, nullptr);
    auto meshAndFields = [&] (MESIOInSitu c, bool fields) {
        check(MESIOInSituSetFVMesh(c, m.nPoints, m.points.data(), m.nFaces, m.foff.data(), m.fnodes.data(), m.owner.data(), m.nInternal, m.neighbour.data(), m.nCells), "SetFVMesh", c);
        if (!fields) return;
        check(MESIOInSituAddCellField(c, "linear", 1), "AddCellField", c);
        check(MESIOInSituAddCellField(c, "blob", 1), "AddCellField", c);
        check(MESIOInSituAddCellField(c, "vel", 3), "AddCellField", c);
        for (int e = 0; e < o.extra; ++e) check(MESIOInSituAddCellField(c, ("extra" + std::to_string(e)).c_str(), 1), "AddCellField", c);
#ifdef MESIO_INSITU_HAS_ERROR_API
        if (o.metadata) {
            check(MESIOInSituSetFieldMetadata(c, "linear", "units", "K"), "SetFieldMetadata", c);
            check(MESIOInSituSetFieldMetadata(c, "vel", "units", "m s^-1"), "SetFieldMetadata", c);
            check(MESIOInSituSetFieldMetadata(c, "vel", "dimensions", "[0 1 -1 0 0 0 0]"), "SetFieldMetadata", c);
        }
#endif
    };
    for (int c = 0; c < o.contexts; ++c) {
        check(MESIOInSituCreate(&ctx[c], MPI_COMM_WORLD, c ? &s2 : &s), "Create", nullptr);
        if (setWriter(o, ctx[c])) MPI_Abort(MPI_COMM_WORLD, 1);
        meshAndFields(ctx[c], true);
        check(MESIOInSituCommit(ctx[c]), "Commit", ctx[c]);
    }
    MPI_Barrier(MPI_COMM_WORLD);
    double t1 = MPI_Wtime();

    for (int c = 0; c < o.contexts; ++c) {
        int gdims[3]; double gorigin[3], gvoxel;
        MESIOInSituGridInfo(ctx[c], gdims, gorigin, &gvoxel);
        if (rank == 0) {
            printf("setup %d context %d: ranks %d (%d empty), cells %dx%dx%d, grid %dx%dx%d, voxel %g, origin (%g %g %g), create+commit %.3f s\n",
                   setup, c, size, o.empty, o.nx, o.ny, o.nz, gdims[0], gdims[1], gdims[2], gvoxel, gorigin[0], gorigin[1], gorigin[2], t1 - t0);
        }
    }

    for (int step = 0; step < o.steps; ++step) {
        double shift = o.moving ? step * h[0] : 0; // moving mesh: translate by one cell per step
        if (o.resetmesh && step > 0) { // topology "change": the same mesh again
#ifdef MESIO_INSITU_HAS_ERROR_API
            double tr0 = MPI_Wtime();
            for (int c = 0; c < o.contexts; ++c) {
                check(MESIOInSituResetMesh(ctx[c]), "ResetMesh", ctx[c]);
                meshAndFields(ctx[c], false);
                check(MESIOInSituCommit(ctx[c]), "Commit after ResetMesh", ctx[c]);
            }
            if (rank == 0) printf("step %d: ResetMesh + SetFVMesh + Commit %.3f s\n", step, MPI_Wtime() - tr0);
#endif
        }
        if (o.moving) {
            for (int p = 0; p < m.nPoints; ++p) moved[3 * p] = m.points[3 * p] + shift;
            for (int c = 0; c < o.contexts; ++c) check(MESIOInSituUpdatePoints(ctx[c], moved.data()), "UpdatePoints", ctx[c]);
        }
        for (int k = m.k0; k < m.k1; ++k) for (int j = m.j0; j < m.j1; ++j) for (int i = m.i0; i < m.i1; ++i) {
            int c = m.cid(i, j, k);
            double x = (i + .5) * h[0] + shift, y = (j + .5) * h[1], z = (k + .5) * h[2];
            if (o.constant) {
                flin[c] = 1.25; fblob[c] = 0.5;
                fvel[3 * c + 0] = 0.6; fvel[3 * c + 1] = 0.8; fvel[3 * c + 2] = 0;
            } else {
                flin[c] = linear(x, y, z, step);
                fblob[c] = blob(x - shift, y, z, step, o.steps);
                fvel[3 * c + 0] = y; fvel[3 * c + 1] = -x; fvel[3 * c + 2] = 0.5;
            }
        }
        for (int c = 0; c < o.contexts; ++c) {
            check(MESIOInSituSetCellField(ctx[c], "linear", flin.data()), "SetCellField", ctx[c]);
            check(MESIOInSituSetCellField(ctx[c], "blob", fblob.data()), "SetCellField", ctx[c]);
            check(MESIOInSituSetCellField(ctx[c], "vel", fvel.data()), "SetCellField", ctx[c]);
            for (int e = 0; e < o.extra; ++e) {
                for (int i = 0; i < m.nCells; ++i) fextra[i] = flin[i] * (e + 2) + fblob[i];
                check(MESIOInSituSetCellField(ctx[c], ("extra" + std::to_string(e)).c_str(), fextra.data()), "SetCellField", ctx[c]);
            }
        }

        for (int c = 0; c < o.contexts; ++c) {
            char name[1024];
            if (c == 0) snprintf(name, sizeof(name), "%s/step_%04d.vdb", o.out.c_str(), step);
            else snprintf(name, sizeof(name), "%s/ctx%d/step_%04d.vdb", o.out.c_str(), c, step);
            MPI_Barrier(MPI_COMM_WORLD);
            double tw0 = MPI_Wtime();
            check(MESIOInSituWriteVDB(ctx[c], 0.1 * step, name), "WriteVDB", ctx[c]);
            double sec[4]; long long voxels, bytes;
            double tw1 = MPI_Wtime();
            MESIOInSituLastWriteStats(ctx[c], sec, &voxels, &bytes);
            double maxsec[4];
            MPI_Reduce(sec, maxsec, 4, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
#ifdef MESIO_INSITU_HAS_WRITER_OPTIONS
            double tloc[MESIO_INSITU_TIMINGS], tmax[MESIO_INSITU_TIMINGS];
            MESIOInSituLastWriteTimings(ctx[c], tloc);
            MPI_Reduce(tloc, tmax, MESIO_INSITU_TIMINGS, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
#endif
#ifdef MESIO_INSITU_HAS_ERROR_API
            long long mem[MESIO_INSITU_MEMORY], memmax[MESIO_INSITU_MEMORY], memw[MESIO_INSITU_MEMORY];
            MESIOInSituLastWriteMemory(ctx[c], mem);
            MPI_Reduce(mem, memmax, MESIO_INSITU_MEMORY, MPI_LONG_LONG, MPI_MAX, 0, MPI_COMM_WORLD);
            std::copy(mem, mem + MESIO_INSITU_MEMORY, memw); // the writer rank is rank 0
#endif

            if (rank == 0) {
                printf("step %d: %s voxels %lld bytes %lld  total %.4f s: convert %.4f sample %.4f aggregate %.4f write %.4f s\n",
                       step, name, voxels, bytes, tw1 - tw0, maxsec[0], maxsec[1], maxsec[2], maxsec[3]);
#ifdef MESIO_INSITU_HAS_WRITER_OPTIONS
                printf("  timings (max over ranks) [s]: convert %.4f plan %.4f sample %.4f exchange %.4f merge %.4f gather %.4f write %.4f total %.4f\n",
                       tmax[0], tmax[1], tmax[2], tmax[3], tmax[4], tmax[5], tmax[6], tmax[7]);
#endif
#ifdef MESIO_INSITU_HAS_ERROR_API
                if (o.memory) {
                    printf("  memory [MB]: writer rank RSS %.1f peak %.1f buffers %.1f; max over ranks RSS %.1f peak %.1f buffers %.1f\n",
                           memw[0] / 1048576., memw[1] / 1048576., memw[2] / 1048576., memmax[0] / 1048576., memmax[1] / 1048576., memmax[2] / 1048576.);
                }
#endif
                fflush(stdout);
            }
            if (rank == 0 && o.verify) {
                failures += !verify(o, name, step, shift, h, c == 0 && o.useBox ? o.box : nullptr, o.sampling == "cell");
            }
        }
    }

    for (int c = 0; c < o.contexts; ++c) MESIOInSituDestroy(ctx[c]);
    } // setups
    MPI_Bcast(&failures, 1, MPI_INT, 0, MPI_COMM_WORLD);
    if (rank == 0) printf("%s\n", failures ? "TEST FAILED" : "TEST PASSED");
    MPI_Finalize();
    return failures ? 1 : 0;
}
