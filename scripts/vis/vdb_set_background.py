#!/usr/bin/env python3
"""Copy one float grid of a .vdb into a new .vdb with a changed background value
(inactive voxels: outside the voxelised box and inside solid bodies).
Usage: vdb_set_background.py <in.vdb> <grid> <background> <out.vdb>
Used for inverted transfer functions (e.g. velocity deficit), where the default
background 0 would map to full opacity at the edges of the active region."""
import sys
import openvdb as vdb

src, gname, bg, dst = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
g = vdb.read(src, gname)
try:
    g.background = bg                # pyopenvdb: changes background + inactive tile/voxel values
except Exception as e:
    sys.exit("cannot set background: %s" % e)
tmp = dst + ".tmp"
vdb.write(tmp, grids=[g])
import os
os.replace(tmp, dst)
print("%s: grid %s background %g -> %s" % (src, gname, g.background, dst))
