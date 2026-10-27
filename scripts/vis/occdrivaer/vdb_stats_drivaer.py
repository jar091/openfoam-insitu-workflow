# Value statistics of the occDrivAer mesioVDB grids (bundled python + openvdb + numpy).
# Usage: pyvdb.sh vdb_stats_drivaer.py <file.vdb>
# Prints active voxels, min/max and percentiles of U_mag, 1-Cpt (total pressure loss), Q > 0,
# vorticity_mag, and the voxel counts above Q / loss thresholds (for the shader map ranges).
import sys
import numpy as np
import openvdb as vdb

path = sys.argv[1]
qs = [10, 50, 90, 99, 99.9]
for name in ["U_mag", "Cpt", "Q", "vorticity_mag"]:
    g = vdb.read(path, name)
    (i0, j0, k0), (i1, j1, k1) = g.evalActiveVoxelBoundingBox()
    a = np.zeros((i1 - i0 + 1, j1 - j0 + 1, k1 - k0 + 1), dtype=np.float32)
    g.copyToArray(a, ijk=(i0, j0, k0))
    act = a != 0
    v = a[act]
    if name == "Cpt":
        v = 1.0 - v
        print("loss=1-Cpt", end=" ")
    else:
        print(name, end=" ")
    print("active", g.activeVoxelCount(), "minmax %.4g %.4g" % (v.min(), v.max()),
          "pct", " ".join("%.4g" % np.percentile(v, q) for q in qs))
    if name == "Q":
        for t in [1e2, 1e3, 3e3, 1e4, 3e4, 1e5, 1e6]:
            print("   Q > %.0e: %d" % (t, int((v > t).sum())))
    if name == "Cpt":
        for t in [0.02, 0.05, 0.1, 0.2, 0.4, 0.7, 0.9]:
            print("   loss > %.2f: %d" % (t, int((v > t).sum())))
