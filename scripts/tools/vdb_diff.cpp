// Compare float grids of the same name in two .vdb files voxel by voxel.
// Build: g++ -std=c++17 -O2 vdb_diff.cpp -I$OPENVDB_ROOT/include -L$OPENVDB_ROOT/lib -lopenvdb -ltbb -o vdb_diff
#include <openvdb/openvdb.h>
#include <cmath>
#include <cstdio>

int main(int argc, char **argv)
{
    if (argc < 3) { std::printf("usage: vdb_diff a.vdb b.vdb\n"); return 1; }
    openvdb::initialize();
    openvdb::io::File fa(argv[1]), fb(argv[2]);
    fa.open(); fb.open();
    int rc = 0;
    for (auto it = fa.beginName(); it != fa.endName(); ++it) {
        auto ga = openvdb::gridPtrCast<openvdb::FloatGrid>(fa.readGrid(it.gridName()));
        auto gb = openvdb::gridPtrCast<openvdb::FloatGrid>(fb.readGrid(it.gridName()));
        auto acc = gb->getConstAccessor();
        double maxdiff = 0, maxref = 0; openvdb::Coord where; size_t n = 0, nbad = 0;
        for (auto v = ga->cbeginValueOn(); v; ++v, ++n) {
            float b = acc.getValue(v.getCoord());
            double d = std::fabs(double(*v) - b);
            maxref = std::max(maxref, std::fabs(double(*v)));
            if (d > 1e-5 * (1 + std::fabs(double(*v)))) ++nbad;
            if (d > maxdiff) { maxdiff = d; where = v.getCoord(); }
        }
        std::printf("%-16s active A=%zu B=%zu  max|A-B|=%.6g at (%d,%d,%d) (A=%g B=%g)  differing voxels=%zu  max|A|=%g\n",
            it.gridName().c_str(), (size_t)ga->activeVoxelCount(), (size_t)gb->activeVoxelCount(), maxdiff,
            where.x(), where.y(), where.z(), ga->getConstAccessor().getValue(where), acc.getValue(where), nbad, maxref);
        if (nbad) rc = 2;
    }
    return rc;
}
