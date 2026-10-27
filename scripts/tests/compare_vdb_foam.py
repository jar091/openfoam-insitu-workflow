"""Compare a VDB grid written by mesioVDB with an OpenFOAM field.

Usage (bundled Python with the openvdb + numpy modules, see render_vdb_series.sh):
  python3 -I compare_vdb_foam.py field <vdb> <grid> <foamField> <foamC>
      Samples the VDB grid (trilinear) at the cell centres <foamC> and compares
      with the cell values of the ASCII OpenFOAM field <foamField>.
  python3 -I compare_vdb_foam.py offset <vdbA> <vdbB> <grid>
      Statistics of A-B over all active voxels (detects constant offsets).
"""
import re
import sys

import numpy as np
import openvdb as vdb


def read_foam_internal(path):
    txt = open(path).read()
    m = re.search(r"internalField\s+nonuniform\s+List<(\w+)>\s*(\d+)\s*\(", txt)
    if not m:
        sys.exit(f"cannot parse nonuniform internalField in {path}")
    kind, n = m.group(1), int(m.group(2))
    body = txt[m.end():]
    if kind == "scalar":
        vals = np.array(body.split(None, n)[:n], dtype=float)
    else:
        nums = re.findall(r"[-+0-9.eE]+", body[: body.find("\n)\n") + 1])
        vals = np.array(nums[: 3 * n], dtype=float).reshape(n, 3)
    return vals


def dense(path, grid):
    g = vdb.read(path, grid)
    (i0, j0, k0), (i1, j1, k1) = g.evalActiveVoxelBoundingBox()
    arr = np.zeros((i1 - i0 + 1, j1 - j0 + 1, k1 - k0 + 1), dtype=np.float32)
    g.copyToArray(arr, ijk=(i0, j0, k0))
    return g, arr, np.array([i0, j0, k0])


def trilinear(arr, x):
    i = np.clip(np.floor(x).astype(int), 0, np.array(arr.shape) - 2)
    f = np.clip(x - i, 0.0, 1.0)
    out = np.zeros(len(x))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) \
                    * (f[:, 2] if dz else 1 - f[:, 2])
                out += w * arr[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
    return out


def cmd_field(vdbfile, grid, foamfield, foamc):
    ref = read_foam_internal(foamfield)
    C = read_foam_internal(foamc)
    g, arr, lo = dense(vdbfile, grid)
    if arr.shape[2] == 1:   # thin in z: duplicate the layer for trilinear
        arr = np.concatenate([arr, arr], axis=2)
    idx = np.array([g.transform.worldToIndex(tuple(c)) for c in C]) - lo
    s = trilinear(arr, idx)
    d = s - ref
    rng = ref.max() - ref.min()
    corr = np.corrcoef(s, ref)[0, 1]
    print(f"{grid}: cells {len(ref)}, OpenFOAM range [{ref.min():.6g}, {ref.max():.6g}], "
          f"VDB@C range [{s.min():.6g}, {s.max():.6g}]")
    print(f"  max|VDB-FOAM| = {np.abs(d).max():.4g} ({np.abs(d).max() / rng * 100:.2f} % of range), "
          f"RMS = {np.sqrt((d ** 2).mean()):.4g} ({np.sqrt((d ** 2).mean()) / rng * 100:.2f} % of range), "
          f"correlation = {corr:.5f}")
    # interior cells: outside the two outermost cell layers of the (box-shaped) domain
    inner = np.ones(len(C), dtype=bool)
    for a in range(3):
        u = np.unique(np.round(C[:, a], 9))
        if len(u) > 4:
            inner &= (C[:, a] > u[1] + 1e-12) & (C[:, a] < u[-2] - 1e-12)
    if inner.any() and not inner.all():
        di = d[inner]
        print(f"  interior cells ({inner.sum()}): max|VDB-FOAM| = {np.abs(di).max():.4g} "
              f"({np.abs(di).max() / rng * 100:.2f} % of range), RMS = {np.sqrt((di ** 2).mean()):.4g} "
              f"({np.sqrt((di ** 2).mean()) / rng * 100:.2f} % of range), "
              f"correlation = {np.corrcoef(s[inner], ref[inner])[0, 1]:.5f}")


def cmd_offset(a, b, grid):
    _, A, la = dense(a, grid)
    _, B, lb = dense(b, grid)
    d = (A - B).ravel()
    print(f"{grid}: A-B mean {d.mean():.6g}, std {d.std():.3g}, min {d.min():.6g}, max {d.max():.6g}")


if __name__ == "__main__":
    if sys.argv[1] == "field":
        cmd_field(*sys.argv[2:6])
    elif sys.argv[1] == "offset":
        cmd_offset(*sys.argv[2:5])
    else:
        sys.exit(__doc__)
