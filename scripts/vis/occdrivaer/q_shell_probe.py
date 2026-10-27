# Probe: where are the Q > threshold voxels? Near the car wall (within k voxels of the inactive
# car interior) vs in the flow; and their normalised Q (2Q/|omega|^2) and U_mag.
import sys
import numpy as np
import openvdb as vdb
path = sys.argv[1]
def arr(name):
    g = vdb.read(path, name)
    (i0, j0, k0), (i1, j1, k1) = g.evalActiveVoxelBoundingBox()
    a = np.zeros((i1 - i0 + 1, j1 - j0 + 1, k1 - k0 + 1), dtype=np.float32)
    g.copyToArray(a, ijk=(i0, j0, k0))
    return a
U, Q, W = arr("U_mag"), arr("Q"), arr("vorticity_mag")
solid = U == 0
near = solid.copy()
for it in range(3):
    n = near.copy()
    for ax in range(3):
        n |= np.roll(near, 1, ax) | np.roll(near, -1, ax)
    near = n
    sel = (Q > 3e3)
    a = sel & near & ~solid; b = sel & ~near
    qn = 2 * Q / np.maximum(W * W, 1e-6)
    print("dilation", it + 1, "Q>3e3 near wall", int(a.sum()), "far", int(b.sum()))
    for nm, m in [("near", a), ("far", b)]:
        print("  %s: Qn pct10/50/90 %s  U pct10/50/90 %s" % (nm, np.percentile(qn[m], [10, 50, 90]).round(3), np.percentile(U[m], [10, 50, 90]).round(1)))
