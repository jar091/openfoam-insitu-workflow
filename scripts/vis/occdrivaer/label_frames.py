# Burn an iteration counter "ITERATION <n>" into PNG frames (bundled python + OpenImageIO +
# numpy). The bundled OIIO has no FreeType and the FFmpeg module no drawtext, so the text is
# drawn with a built-in 5x7 bitmap font.
# Usage: pyvdb.sh label_frames.py <in_dir> <out_dir> [scale=5]   (iteration = last number in the name)
import glob
import os
import re
import sys
import numpy as np
import OpenImageIO as oiio

FONT = {  # 5x7, rows top -> bottom, '#' = on
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    " ": ["....."] * 7,
}


def draw(img, text, x0, y0, s, color):
    x = x0
    for ch in text:
        g = FONT[ch]
        for r, row in enumerate(g):
            for c, v in enumerate(row):
                if v == "#":
                    img[y0 + r * s:y0 + (r + 1) * s, x + c * s:x + (c + 1) * s, :3] = color
        x += 6 * s


src, dst = sys.argv[1], sys.argv[2]
s = int(sys.argv[3]) if len(sys.argv) > 3 else 5
os.makedirs(dst, exist_ok=True)
fs = sorted(glob.glob(src + "/*.png"))
for f in fs:
    it = int(re.findall(r"(\d+)", os.path.basename(f))[-1])
    buf = oiio.ImageBuf(f)
    img = buf.get_pixels(oiio.FLOAT)
    h = img.shape[0]
    draw(img, "ITERATION %d" % it, 6 * s, h - 13 * s, s, (0.80, 0.82, 0.86))
    out = oiio.ImageBuf(buf.spec())
    out.set_pixels(oiio.ROI(), img)
    out.write(os.path.join(dst, os.path.basename(f)))
print("labelled", len(fs), "frames")
