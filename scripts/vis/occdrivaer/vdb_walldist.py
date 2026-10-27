# Wall-distance helper grid for the occDrivAer scenes (bundled python + openvdb + numpy).
# The car interior is the set of inactive/zero voxels of U_mag inside the mesioVDB box.
# Distance (in metres, 6-neighbour layer count x voxel size, capped at --layers) from the car
# interior is written as a sparse FloatGrid "walld" (background = cap) with the same transform,
# to a separate .vdb that the scenes load as an extra attribute (the car is static, so one
# file serves every export with the same box/voxel size).
# Usage: pyvdb.sh vdb_walldist.py <in.vdb> <out.vdb> [layers=10]
import sys
import time
import numpy as np
import openvdb as vdb

t0 = time.time()
src, dst = sys.argv[1], sys.argv[2]
layers = int(sys.argv[3]) if len(sys.argv) > 3 else 10
g = vdb.read(src, "U_mag")
(i0, j0, k0), (i1, j1, k1) = g.evalActiveVoxelBoundingBox()
a = np.zeros((i1 - i0 + 1, j1 - j0 + 1, k1 - k0 + 1), dtype=np.float32)
g.copyToArray(a, ijk=(i0, j0, k0))
h = g.transform.voxelSize()[0]
solid = a == 0
del a
d = np.full(solid.shape, layers, dtype=np.uint8)
d[solid] = 0
cur = solid
for L in range(1, layers):
    n = cur.copy()
    for ax in range(3):
        n |= np.roll(cur, 1, ax)
        n |= np.roll(cur, -1, ax)
    d[n & ~cur] = L
    cur = n
cap = float(np.float32(layers * h))
out = vdb.FloatGrid(cap)
out.transform = g.transform
out.name = "walld"
dist = d.astype(np.float32) * h
dist[d == layers] = cap
out.copyFromArray(dist, ijk=(i0, j0, k0), tolerance=1e-6)
out.prune()
vdb.write(dst, grids=[out])
print("walld: voxel %.4g m, cap %.3g m, solid voxels %d, active %d, %.1f s"
      % (h, cap, int(solid.sum()), out.activeVoxelCount(), time.time() - t0))
