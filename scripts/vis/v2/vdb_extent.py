# Extent analysis of pitzDaily3D VDB grids (flame front / vortex region) to choose a tight box.
# Usage: vdb_extent.py <file.vdb>
import sys, openvdb as vdb, numpy as np
path = sys.argv[1]
def load(name):
    g = vdb.read(path, name)
    (i0,j0,k0),(i1,j1,k1) = g.evalActiveVoxelBoundingBox()
    a = np.zeros((i1-i0+1, j1-j0+1, k1-k0+1), dtype=np.float32)
    g.copyToArray(a, ijk=(i0,j0,k0))
    return g, a, (i0,j0,k0)
gb, b, o = load('b')
xf = gb.transform
h = xf.voxelSize()[0]
print("voxel", h, "shape", b.shape, "origin idx", o, "world0", xf.indexToWorld(o))
def ext(mask, label):
    idx = np.argwhere(mask)
    if len(idx) == 0: print(label, "empty"); return
    for ax, nm in enumerate("xyz"):
        lo, hi = np.percentile(idx[:, ax], [0.05, 99.95])
        mn, mx = idx[:, ax].min(), idx[:, ax].max()
        w = lambda i: (i + o[ax]) * h
        print("  %s %s: min %.4f p0.05 %.4f p99.95 %.4f max %.4f" % (label, nm, w(mn), w(lo), w(hi), w(mx)))
ext((b > 0.05) & (b < 0.95), "front")
gq, q, oq = load('Q')
ext(q > 3e5, "Q>3e5")
ext(q > 1e6, "Q>1e6")
for nm in ['T', 'U_mag']:
    g, a, _ = load(nm)
    v = a[a != 0]
    print(nm, "minmax", g.evalMinMax(), "pct", [float(np.percentile(v, p)) for p in (1, 50, 99, 99.9)])
# x-profile of front voxel counts
cnt = ((b > 0.05) & (b < 0.95)).sum(axis=(1, 2))
for i in range(0, b.shape[0], b.shape[0] // 16):
    print("  x=%.4f front voxels %d" % ((i + o[0]) * h, cnt[i]))
