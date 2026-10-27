#!/usr/bin/env python3
"""
Edit the transfer function of a CyclesPhi volume template written by
data/cyclesphi/make_vdb_scene.py (template.xml + template.xml.bin) in place.

  --alpha "t0:a0,t1:a1,..."   piecewise-linear opacity on the normalised value t in [0,1]
  --colors "t0:r,g,b;t1:..."  piecewise-linear colour ramp (sRGB 0..1, converted to linear)
  --invert                    swap map_range from_min/from_max (t = 1 at the low value)
  --range VMIN VMAX           set map_range from_min/from_max (applied before --invert)

The ramp arrays live in the .bin at the offsets given in the XML (257 entries each),
so they are overwritten in place.  Use case: OpenFOAM VDBs whose inactive voxels
(background 0) must stay transparent with an inverted map (e.g. velocity deficit):
--invert --alpha "0:0,0.25:0,0.8:1,0.97:1,0.98:0,1:0".
"""
import argparse
import re
import struct

N = 257


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def pwl(points, t):
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            if isinstance(v0, tuple):
                return tuple(a + (b - a) * f for a, b in zip(v0, v1))
            return v0 + (v1 - v0) * f
    return points[-1][1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xml")
    ap.add_argument("--alpha")
    ap.add_argument("--colors")
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--range", type=float, nargs=2)
    a = ap.parse_args()

    xml = open(a.xml).read()
    off_ramp = int(re.search(r'name="ramp" value="(\d+)"', xml).group(1))
    off_alpha = int(re.search(r'name="ramp_alpha" value="(\d+)"', xml).group(1))
    binf = a.xml + ".bin"
    data = bytearray(open(binf, "rb").read())

    if a.alpha:
        pts = [tuple(float(x) for x in p.split(":")) for p in a.alpha.split(",")]
        assert struct.unpack_from("<Q", data, off_alpha)[0] == N
        vals = [pwl(pts, i / (N - 1)) for i in range(N)]
        struct.pack_into("<%df" % N, data, off_alpha + 8, *vals)
    if a.colors:
        pts = []
        for p in a.colors.split(";"):
            t, rgb = p.split(":")
            pts.append((float(t), tuple(float(x) for x in rgb.split(","))))
        assert struct.unpack_from("<Q", data, off_ramp)[0] == N
        for i in range(N):
            c = pwl(pts, i / (N - 1))
            struct.pack_into("<4f", data, off_ramp + 8 + 16 * i,
                             *[srgb_to_linear(x) for x in c], 0.0)
    open(binf, "wb").write(data)

    lo = re.search(r'name="from_min" value="([^"]+)"', xml).group(1)
    hi = re.search(r'name="from_max" value="([^"]+)"', xml).group(1)
    if a.range:
        lo, hi = "%.9g" % a.range[0], "%.9g" % a.range[1]
    if a.invert:
        lo, hi = hi, lo
    xml = re.sub(r'name="from_min" value="[^"]+"', 'name="from_min" value="%s"' % lo, xml)
    xml = re.sub(r'name="from_max" value="[^"]+"', 'name="from_max" value="%s"' % hi, xml)
    open(a.xml, "w").write(xml)
    print("%s: map_range %s -> %s, alpha %s, colors %s" % (a.xml, lo, hi, a.alpha, a.colors))


if __name__ == "__main__":
    main()
