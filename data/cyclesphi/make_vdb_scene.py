#!/usr/bin/env python3
"""
Generate a CyclesPhi XML scene template (+ the mandatory companion .xml.bin) for
rendering one float grid of an OpenVDB file as a coloured, semi-transparent volume.

CyclesPhi's XML reader ("cycles" binary, src/app/cycles_xml_bin.cpp) always opens
<scene>.xml.bin next to <scene>.xml; every *array* socket (colour ramp, alpha ramp, ...)
is given in the XML as a byte offset into that .bin file.  At such an offset the
.bin holds:  uint64 count, followed by count elements (float = 4 B, colour = 4 floats
= 16 B).  Scalar sockets (floats, transforms, strings) are written inline in the XML.

The generated XML keeps the ppam2026 placeholders so the same sed-based workflow works:
    {VDB_DATA}   path to the .vdb file (absolute)
    {GRID_NAME}  name of the float grid inside the .vdb file

Scene layout produced:
  * object transform normalises the VDB world bounding box to a cube-ish box whose
    diagonal is 10 scene units, centred at the origin (so density values are
    independent of the simulation units),
  * shader:  Attribute(grid) -> Map Range(vmin..vmax, clamped) -> Color Ramp(colormap)
             ramp.color -> Principled Volume.Color (and Emission Color)
             ramp.alpha * density -> Principled Volume.Density
             ramp.alpha * emission -> Principled Volume.Emission Strength
  * world: constant-colour background used for lighting; camera rays see a separate
    (display) background colour (same trick as the ppam2026 scenes),
  * perspective camera orbiting the origin (azimuth/elevation around the chosen up axis).

The bounding box and the value range can be computed from a VDB file (needs the
`openvdb` Python module, e.g. the one in Blender's precompiled lib bundle, see
scripts/env_cyclesphi.sh / render_vdb_series.sh) or given explicitly.

Example:
  make_vdb_scene.py --vdb case/U_mag_0100.vdb --grid U_mag --out scene.xml \
      --colormap viridis --density 5 --azimuth 30 --elevation 20
"""
import argparse
import math
import os
import struct
import sys

# ---------------------------------------------------------------- colormaps (sRGB)
COLORMAPS = {
    # matplotlib-like control points (sRGB, 0..1)
    "viridis": [(0.267, 0.005, 0.329), (0.283, 0.141, 0.458), (0.254, 0.265, 0.530),
                (0.207, 0.372, 0.553), (0.164, 0.471, 0.558), (0.128, 0.567, 0.551),
                (0.135, 0.659, 0.518), (0.267, 0.749, 0.441), (0.478, 0.821, 0.318),
                (0.741, 0.873, 0.150), (0.993, 0.906, 0.144)],
    "inferno": [(0.001, 0.000, 0.014), (0.087, 0.045, 0.225), (0.258, 0.039, 0.406),
                (0.416, 0.090, 0.433), (0.578, 0.148, 0.404), (0.735, 0.216, 0.330),
                (0.865, 0.317, 0.226), (0.954, 0.469, 0.098), (0.988, 0.645, 0.040),
                (0.964, 0.844, 0.273), (0.988, 0.998, 0.645)],
    "plasma":  [(0.050, 0.030, 0.528), (0.254, 0.014, 0.615), (0.417, 0.001, 0.658),
                (0.562, 0.051, 0.642), (0.692, 0.165, 0.565), (0.798, 0.280, 0.470),
                (0.881, 0.393, 0.383), (0.949, 0.517, 0.296), (0.988, 0.652, 0.211),
                (0.988, 0.808, 0.145), (0.940, 0.975, 0.131)],
    "coolwarm": [(0.230, 0.299, 0.754), (0.406, 0.537, 0.934), (0.602, 0.731, 0.999),
                 (0.788, 0.846, 0.939), (0.930, 0.820, 0.761), (0.968, 0.657, 0.537),
                 (0.887, 0.413, 0.324), (0.706, 0.016, 0.150)],
    "turbo":   [(0.190, 0.072, 0.232), (0.276, 0.421, 0.891), (0.158, 0.736, 0.923),
                (0.197, 0.949, 0.595), (0.644, 0.990, 0.234), (0.933, 0.812, 0.227),
                (0.984, 0.493, 0.128), (0.816, 0.185, 0.019), (0.480, 0.016, 0.011)],
    # blue -> green -> red ramp used by the ppam2026 OpenFOAM scenes (already linear)
    "ppam":    "linear:(0.013,0.011,1.0),(0.0,1.0,0.011),(0.578,0.001,0.0)",
    "gray":    [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)],
}

RAMP_SIZE = 257  # Cycles RAMP_TABLE_SIZE (256) + 1, like Blender exports


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def colormap_table(name):
    cm = COLORMAPS[name]
    linear = False
    if isinstance(cm, str):
        linear = True
        cm = [tuple(float(v) for v in p.strip("()").split(","))
              for p in cm.split(":", 1)[1].split("),(")]
    out = []
    n = len(cm) - 1
    for i in range(RAMP_SIZE):
        t = i / (RAMP_SIZE - 1) * n
        k = min(int(t), n - 1)
        f = t - k
        rgb = [cm[k][j] * (1 - f) + cm[k + 1][j] * f for j in range(3)]
        if not linear:
            rgb = [srgb_to_linear(v) for v in rgb]
        out.append(rgb)
    return out


def alpha_table(alpha_min, alpha_gamma, alpha_floor):
    """Opacity transfer function on the normalised value t in [0,1]:
       0 below alpha_min, then ((t-alpha_min)/(1-alpha_min))**gamma, never below floor."""
    out = []
    for i in range(RAMP_SIZE):
        t = i / (RAMP_SIZE - 1)
        if t < alpha_min:
            a = 0.0
        else:
            a = ((t - alpha_min) / max(1e-6, 1.0 - alpha_min)) ** alpha_gamma
            a = max(a, alpha_floor)
        out.append(a)
    return out


# ---------------------------------------------------------------- VDB inspection
def vdb_info(path, grid):
    """Return (bbox_min, bbox_max, vmin, vmax) in world space using pyopenvdb."""
    try:
        import openvdb as vdb
    except ImportError:
        try:
            import pyopenvdb as vdb
        except ImportError:
            sys.exit("ERROR: python module 'openvdb' not found; pass --bbox and --range "
                     "explicitly or run with the bundled python (see render_vdb_series.sh)")
    g = vdb.read(path, grid)
    (i0, j0, k0), (i1, j1, k1) = g.evalActiveVoxelBoundingBox()
    xf = g.transform
    corners = []
    for i in (i0 - 0.5, i1 + 0.5):
        for j in (j0 - 0.5, j1 + 0.5):
            for k in (k0 - 0.5, k1 + 0.5):
                corners.append(xf.indexToWorld((i, j, k)))
    bmin = [min(c[a] for c in corners) for a in range(3)]
    bmax = [max(c[a] for c in corners) for a in range(3)]
    vmin, vmax = g.evalMinMax()
    return bmin, bmax, float(vmin), float(vmax)


# ---------------------------------------------------------------- small vector helpers
def sub(a, b): return [a[i] - b[i] for i in range(3)]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def norm(a):
    l = math.sqrt(sum(x * x for x in a))
    return [x / l for x in a]


def camera_matrix(azimuth_deg, elevation_deg, distance, up_axis):
    """Cycles camera transform (3x4, row-major): columns = right, up, forward, position.
    (Same convention as the ppam2026 scenes exported from Blender.)"""
    up = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}[up_axis]
    e1 = {"x": [0, 1, 0], "y": [0, 0, 1], "z": [1, 0, 0]}[up_axis]
    e2 = cross(up, e1)
    az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
    d = [math.cos(el) * math.cos(az) * e1[i] + math.cos(el) * math.sin(az) * e2[i]
         + math.sin(el) * up[i] for i in range(3)]
    pos = [distance * x for x in d]
    f = norm([-x for x in pos])           # look at the origin
    r = norm(cross(f, up))
    u = cross(r, f)
    m = []
    for row in range(3):
        m += [r[row], u[row], f[row], pos[row]]
    return m


def fmt(v):
    # NOTE: colour sockets in CyclesPhi XML need 4 values ("r g b 0").
    return " ".join("%.7g" % x for x in v)


# ---------------------------------------------------------------- writer
class BinWriter:
    def __init__(self):
        self.data = bytearray()

    def floats(self, values):
        off = len(self.data)
        self.data += struct.pack("<Q", len(values))
        self.data += struct.pack("<%df" % len(values), *values)
        return off

    def colors(self, rgbs):
        off = len(self.data)
        self.data += struct.pack("<Q", len(rgbs))
        for c in rgbs:
            self.data += struct.pack("<4f", c[0], c[1], c[2], 0.0)
        return off


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="output XML template path (.xml.bin written next to it)")
    ap.add_argument("--vdb", help="VDB file used to compute bbox/value range (optional)")
    ap.add_argument("--grid", help="grid name used with --vdb (also baked in if --bake-grid)")
    ap.add_argument("--bbox", type=float, nargs=6, metavar=("X0", "Y0", "Z0", "X1", "Y1", "Z1"),
                    help="world bounding box (overrides --vdb)")
    ap.add_argument("--range", type=float, nargs=2, metavar=("VMIN", "VMAX"),
                    help="value range mapped to the colormap (overrides --vdb min/max)")
    ap.add_argument("--colormap", default="viridis", choices=sorted(COLORMAPS))
    ap.add_argument("--density", type=float, default=5.0,
                    help="density multiplier (per scene unit; scene diagonal = 10 units)")
    ap.add_argument("--emission", type=float, default=0.0,
                    help="emission strength multiplier (0 = pure scattering/absorption)")
    ap.add_argument("--alpha-min", type=float, default=0.05,
                    help="normalised value below which the volume is fully transparent")
    ap.add_argument("--alpha-gamma", type=float, default=1.0, help="opacity ramp exponent")
    ap.add_argument("--alpha-floor", type=float, default=0.0, help="minimum opacity above alpha-min")
    ap.add_argument("--azimuth", type=float, default=35.0)
    ap.add_argument("--elevation", type=float, default=25.0)
    ap.add_argument("--up", default="z", choices=["x", "y", "z"], help="world up axis of the data")
    ap.add_argument("--fov", type=float, default=30.0, help="field of view in degrees (shorter image side)")
    ap.add_argument("--zoom", type=float, default=1.0, help=">1 moves the camera closer")
    ap.add_argument("--background", type=float, nargs=3, default=[0.02, 0.02, 0.025],
                    help="background colour seen by the camera (linear RGB)")
    ap.add_argument("--light", type=float, nargs=3, default=[1.0, 1.0, 1.0],
                    help="world light colour (linear RGB) used to illuminate the volume")
    ap.add_argument("--light-strength", type=float, default=1.0)
    ap.add_argument("--interpolation", default="linear", choices=["linear", "closest", "cubic"])
    ap.add_argument("--bake-vdb", action="store_true", help="write --vdb path instead of {VDB_DATA}")
    ap.add_argument("--bake-grid", action="store_true", help="write --grid instead of {GRID_NAME}")
    a = ap.parse_args()

    bmin = bmax = None
    vmin = vmax = None
    if a.vdb and (a.bbox is None or a.range is None):
        if not a.grid:
            sys.exit("ERROR: --grid is required with --vdb")
        bmin, bmax, vmin, vmax = vdb_info(a.vdb, a.grid)
        print("VDB %s grid %s: bbox %s .. %s, value range %g .. %g" % (a.vdb, a.grid, bmin, bmax, vmin, vmax))
    if a.bbox:
        bmin, bmax = a.bbox[:3], a.bbox[3:]
    if a.range:
        vmin, vmax = a.range
    if bmin is None or vmin is None:
        sys.exit("ERROR: need --vdb or both --bbox and --range")
    if vmax <= vmin:
        vmax = vmin + 1e-6

    # Normalise the data box: centre -> origin, diagonal -> 10 units.
    center = [(bmin[i] + bmax[i]) * 0.5 for i in range(3)]
    diag = math.sqrt(sum((bmax[i] - bmin[i]) ** 2 for i in range(3)))
    s = 10.0 / diag
    tfm = [s, 0, 0, -s * center[0], 0, s, 0, -s * center[1], 0, 0, s, -s * center[2]]

    fov = math.radians(a.fov)
    distance = 5.0 / math.sin(fov * 0.5) / a.zoom  # bounding sphere radius = 5
    cam = camera_matrix(a.azimuth, a.elevation, distance, a.up)

    binw = BinWriter()
    off_ramp = binw.colors(colormap_table(a.colormap))
    off_alpha = binw.floats(alpha_table(a.alpha_min, a.alpha_gamma, a.alpha_floor))

    vdb_ref = os.path.abspath(a.vdb) if (a.bake_vdb and a.vdb) else "{VDB_DATA}"
    grid_ref = a.grid if (a.bake_grid and a.grid) else "{GRID_NAME}"
    interp = {"linear": "",
              "closest": ' interpolation="INTERPOLATION_CLOSEST"',
              "cubic": ' interpolation="INTERPOLATION_CUBIC"'}[a.interpolation]

    xml = f"""<?xml version="1.0"?>
<!-- Generated by make_vdb_scene.py
     colormap={a.colormap} range=[{vmin:.6g}, {vmax:.6g}] density={a.density} emission={a.emission}
     data bbox min={fmt(bmin)} max={fmt(bmax)}
     Placeholders: {{VDB_DATA}} = .vdb path, {{GRID_NAME}} = float grid name.
     Array sockets (ramp, ramp_alpha) are byte offsets into the companion .xml.bin file. -->
<cycles>
	<shader name="default_surface">
		<principled_bsdf name="surf_bsdf" />
		<connect from_node="surf_bsdf" from_socket="BSDF" to_node="output" to_socket="surface" />
	</shader>
	<shader name="default_volume" />
	<shader name="default_light" />
	<shader name="default_background">
		<background_shader name="bg_light">
			<socket name="color" value="{fmt(list(a.light) + [0])}" type_name="color" />
			<socket name="strength" value="{a.light_strength}" type_name="float" />
		</background_shader>
		<background_shader name="bg_camera">
			<socket name="color" value="{fmt(list(a.background) + [0])}" type_name="color" />
			<socket name="strength" value="1" type_name="float" />
		</background_shader>
		<light_path name="bg_lightpath" />
		<mix_closure name="bg_mix" />
		<connect from_node="bg_lightpath" from_socket="is_camera_ray" to_node="bg_mix" to_socket="fac" />
		<connect from_node="bg_light" from_socket="background" to_node="bg_mix" to_socket="closure1" />
		<connect from_node="bg_camera" from_socket="background" to_node="bg_mix" to_socket="closure2" />
		<connect from_node="bg_mix" from_socket="closure" to_node="output" to_socket="surface" />
	</shader>
	<shader name="default_empty" />

	<!-- Volume transfer function: value -> [0,1] -> colour ramp (colour + opacity) -->
	<shader name="vdb_volume_shader">
		<attribute name="vol_attr">
			<socket name="attribute" value="{grid_ref}" type_name="string" />
		</attribute>
		<map_range name="vol_range">
			<socket name="from_min" value="{vmin:.9g}" type_name="float" />
			<socket name="from_max" value="{vmax:.9g}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<rgb_ramp name="vol_ramp">
			<socket name="ramp" value="{off_ramp}" type_name="array_color" />
			<socket name="ramp_alpha" value="{off_alpha}" type_name="array_float" />
		</rgb_ramp>
		<math name="vol_density">
			<socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.density}" type_name="float" />
		</math>
		<math name="vol_emission">
			<socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.emission}" type_name="float" />
		</math>
		<principled_volume name="vol_principled" />
		<connect from_node="vol_attr" from_socket="fac" to_node="vol_range" to_socket="value" />
		<connect from_node="vol_range" from_socket="result" to_node="vol_ramp" to_socket="fac" />
		<connect from_node="vol_ramp" from_socket="color" to_node="vol_principled" to_socket="color" />
		<connect from_node="vol_ramp" from_socket="color" to_node="vol_principled" to_socket="emission_color" />
		<connect from_node="vol_ramp" from_socket="alpha" to_node="vol_density" to_socket="value1" />
		<connect from_node="vol_ramp" from_socket="alpha" to_node="vol_emission" to_socket="value1" />
		<connect from_node="vol_density" from_socket="value" to_node="vol_principled" to_socket="density" />
		<connect from_node="vol_emission" from_socket="value" to_node="vol_principled" to_socket="emission_strength" />
		<connect from_node="vol_principled" from_socket="volume" to_node="output" to_socket="volume" />
	</shader>

	<camera name="camera">
		<socket name="matrix" value="{fmt(cam)}" type_name="transform" />
		<socket name="fov" value="{fov:.7g}" type_name="float" />
		<socket name="nearclip" value="0.01" type_name="float" />
		<socket name="farclip" value="{distance * 10:.7g}" type_name="float" />
	</camera>

	<film name="film">
		<socket name="filter_type" value="blackman_harris" type_name="enum" />
		<socket name="filter_width" value="1.5" type_name="float" />
	</film>
	<background name="background">
		<socket name="visibility" value="157" type_name="uint" />
	</background>
	<integrator name="integrator">
		<socket name="max_bounce" value="12" type_name="int" />
		<socket name="max_volume_bounce" value="0" type_name="int" />
		<socket name="transparent_max_bounce" value="8" type_name="int" />
		<socket name="volume_ray_marching" value="true" type_name="boolean" />
		<socket name="volume_max_steps" value="256" type_name="int" />
		<socket name="use_adaptive_sampling" value="false" type_name="boolean" />
	</integrator>

	<!-- The volume geometry: one float grid read from an OpenVDB file.
	     geometry_type 2 = VOLUME. The bounding mesh is generated from the grid. -->
	<volume name="vdb_volume" geometry_type="2">
		<socket name="used_shaders" value="vdb_volume_shader" type_name="array_node" />
		<socket name="object_space" value="true" type_name="boolean" />
		<attribute name="{grid_ref}" std="ATTR_STD_NONE" type="float" element="ATTR_ELEMENT_VOXEL" flags="0" buffer="{vdb_ref}" volume_type="openvdb"{interp} />
	</volume>
	<object name="vdb_object">
		<socket name="geometry" value="vdb_volume" type_name="node" />
		<!-- 3x4 row-major: normalises the data bbox (centre -> 0, diagonal -> 10 units) -->
		<socket name="tfm" value="{fmt(tfm)}" type_name="transform" />
		<socket name="visibility" value="1693" type_name="uint" />
	</object>

	<!-- World light (geometry_type 5 = BACKGROUND_LIGHT) -->
	<backgroundlight name="world_light" geometry_type="5">
		<socket name="used_shaders" value="default_background" type_name="array_node" />
		<socket name="light_type" value="background" type_name="enum" />
		<socket name="use_mis" value="true" type_name="boolean" />
	</backgroundlight>
	<object name="world_object">
		<socket name="geometry" value="world_light" type_name="node" />
	</object>
</cycles>
"""
    with open(a.out, "w") as f:
        f.write(xml)
    with open(a.out + ".bin", "wb") as f:
        f.write(binw.data)
    print("Wrote %s and %s.bin" % (a.out, a.out))


if __name__ == "__main__":
    main()
