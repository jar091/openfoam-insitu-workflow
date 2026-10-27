# Temporal flicker check of a PNG series: mean |f(i-1) - 2 f(i) + f(i+1)| (second temporal
# difference, 8-bit units) over pixels brighter than a threshold, vs the mean first difference.
# Smooth motion gives a small second difference; denoiser/sampling flicker raises it.
# Usage: flicker.py <png_dir>
import sys, glob
import numpy as np
import OpenImageIO as oiio
fs = sorted(glob.glob(sys.argv[1] + "/pitz_*.png"))
img = [oiio.ImageBuf(f).get_pixels(oiio.FLOAT)[..., :3] * 255.0 for f in fs]
d1, d2 = [], []
for i in range(1, len(img) - 1):
    m = img[i].mean(axis=2) > 40
    d1.append(np.abs(img[i + 1] - img[i])[m].mean())
    d2.append(np.abs(img[i - 1] - 2 * img[i] + img[i + 1])[m].mean())
print("%s: %d frames, mean |d1| %.2f, mean |d2| %.2f, max |d2| %.2f (8-bit units, bright px)"
      % (sys.argv[1].rstrip('/').split('/')[-1], len(fs), np.mean(d1), np.mean(d2), np.max(d2)))
