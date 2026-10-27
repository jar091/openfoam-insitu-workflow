# mean |a-b| over bright pixels of two PNGs (8-bit units). Usage: imgdiff.py a.png b.png
import sys, numpy as np, OpenImageIO as oiio
a, b = [oiio.ImageBuf(f).get_pixels(oiio.FLOAT)[..., :3] * 255.0 for f in sys.argv[1:3]]
m = a.mean(axis=2) > 40
print("%s vs %s: mean |diff| %.2f" % (sys.argv[1].split('/')[-1], sys.argv[2].split('/')[-1], np.abs(a - b)[m].mean()))
