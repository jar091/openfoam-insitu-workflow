# Print value statistics of float grids in a .vdb (bundled python + openvdb of CyclesPhi libs).
# Usage: vdb_stats.py <file.vdb> <grid> [grid...]
import sys, openvdb as vdb, numpy as np
path = sys.argv[1]
for gname in sys.argv[2:]:
    g = vdb.read(path, gname)
    (i0,j0,k0),(i1,j1,k1) = g.evalActiveVoxelBoundingBox()
    a = np.zeros((i1-i0+1, j1-j0+1, k1-k0+1), dtype=np.float32)
    g.copyToArray(a, ijk=(i0,j0,k0))
    v = a[a != 0] if gname != 'p' else a.ravel()
    qs = [50, 90, 99, 99.9, 99.99]
    print(gname, "active", g.activeVoxelCount(), "minmax", g.evalMinMax(), "pct", [float(np.percentile(v, q)) for q in qs])
    if gname == 'Q':
        for t in [1e3, 1e4, 3e4, 1e5, 3e5, 1e6]:
            print("  Q >", t, ":", int((a > t).sum()))
