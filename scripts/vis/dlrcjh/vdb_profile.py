# Axial profiles of a DLRCJH mesioVDB file: per x-slab statistics of T, the flame-front
# fraction (0.05 < b < 0.95, T > 1000 K), Q percentiles and U_mag. Used to choose the
# export box and the transfer functions. Usage: vdb_profile.py <file.vdb> [nslabs]
import sys, openvdb as vdb, numpy as np
path = sys.argv[1]; ns = int(sys.argv[2]) if len(sys.argv) > 2 else 24
A = {}
for g in ("T", "b", "Q", "U_mag"):
    grid = vdb.read(path, g)
    (i0, j0, k0), (i1, j1, k1) = grid.evalActiveVoxelBoundingBox()
    a = np.zeros((i1 - i0 + 1, j1 - j0 + 1, k1 - k0 + 1), dtype=np.float32)
    grid.copyToArray(a, ijk=(i0, j0, k0)); A[g] = a
    tf = grid.transform
    print(g, "bbox ijk", (i0, j0, k0), (i1, j1, k1), "world", tf.indexToWorld((i0, j0, k0)), tf.indexToWorld((i1, j1, k1)))
T, b, Q, U = A["T"], A["b"], A["Q"], A["U_mag"]
act = T > 1
front = act & (b > 0.05) & (b < 0.95) & (T > 1000)
qa = Q[act]
print("Q pct (active) 50/90/99/99.9/99.99:", [float(np.percentile(qa, q)) for q in (50, 90, 99, 99.9, 99.99)])
print("Q>0 pct:", [float(np.percentile(qa[qa > 0], q)) for q in (50, 90, 99, 99.9)])
print("U pct:", [float(np.percentile(U[act], q)) for q in (1, 50, 90, 99, 99.9)])
print("T pct:", [float(np.percentile(T[act], q)) for q in (1, 10, 50, 90, 99, 99.9)])
nx = T.shape[0]; e = np.linspace(0, nx, ns + 1).astype(int)
x0 = tf.indexToWorld((i0, 0, 0))[0]; dx = tf.voxelSize()[0]
print("slab x[mm]   active  Tmean  Tmax  front%  b<0.5%  Qp99  Umax")
for s in range(ns):
    sl = slice(e[s], e[s + 1]); m = act[sl]
    if m.sum() == 0: continue
    print("%5.0f-%5.0f %8d %6.0f %6.0f %6.2f %6.1f %9.3g %6.1f" % ((x0 + e[s] * dx) * 1e3, (x0 + e[s + 1] * dx) * 1e3, m.sum(),
          T[sl][m].mean(), T[sl][m].max(), 100 * front[sl].sum() / m.sum(), 100 * (b[sl][m] < 0.5).mean(),
          np.percentile(Q[sl][m], 99), U[sl][m].max()))
# lateral extent of the front
idx = np.argwhere(front)
if len(idx):
    lo = idx.min(0); hi = idx.max(0)
    print("front ijk extent", lo, hi, "world lo", tf.indexToWorld(tuple(int(v) for v in lo + np.array([i0, j0, k0]))),
          "hi", tf.indexToWorld(tuple(int(v) for v in hi + np.array([i0, j0, k0]))))
