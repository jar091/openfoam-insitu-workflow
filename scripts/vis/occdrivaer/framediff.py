# Visible change between consecutive frames of a PNG series (bundled python + OpenImageIO):
# mean |f(i+1) - f(i)| over all pixels and the fraction of pixels changing by > 4/255.
# Usage: pyvdb.sh framediff.py <png_dir> [glob=*.png]
import glob
import sys
import numpy as np
import OpenImageIO as oiio
fs = sorted(glob.glob(sys.argv[1] + "/" + (sys.argv[2] if len(sys.argv) > 2 else "*.png")))
prev = None
for f in fs:
    img = oiio.ImageBuf(f).get_pixels(oiio.FLOAT)[..., :3] * 255.0
    if prev is not None:
        d = np.abs(img - prev).max(axis=2)
        print("%-24s mean|d| %5.2f  changed(>4) %5.1f %%" % (f.split("/")[-1], d.mean(), 100.0 * (d > 4).mean()))
    prev = img
