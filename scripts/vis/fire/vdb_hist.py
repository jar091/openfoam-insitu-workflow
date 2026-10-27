# Percentiles of float grids in a .vdb over active voxels, plus counts above thresholds.
# Usage (bundled python): pyvdb.sh vdb_hist.py <file.vdb> <grid>[:thr1,thr2,...] ...
import sys, openvdb as vdb, numpy as np
path = sys.argv[1]
for spec in sys.argv[2:]:
    gname, _, thr = spec.partition(":")
    g = vdb.read(path, gname)
    (i0, j0, k0), (i1, j1, k1) = g.evalActiveVoxelBoundingBox()
    a = np.full((i1 - i0 + 1, j1 - j0 + 1, k1 - k0 + 1), np.nan, dtype=np.float32)
    g.copyToArray(a, ijk=(i0, j0, k0))
    m = g.background
    v = a[np.isfinite(a)]
    print("%s: active %d bg %g bbox %s-%s min %g max %g" % (gname, g.activeVoxelCount(), m, (i0, j0, k0), (i1, j1, k1), v.min(), v.max()))
    print("   pct 1/10/50/90/99/99.9:", ["%.4g" % np.percentile(v, q) for q in (1, 10, 50, 90, 99, 99.9)])
    for t in [float(x) for x in thr.split(",") if x]:
        print("   > %g : %d" % (t, int((v > t).sum())))
