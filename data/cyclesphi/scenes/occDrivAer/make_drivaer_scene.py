#!/usr/bin/env python3
"""
CyclesPhi scene generator for the occDrivAer animations (OpenFOAM HPC case
incompressible/simpleFoam/occDrivAerStaticMesh, 65M cells, steady RANS; mesioVDB grids
U_mag, Cpt (total pressure coefficient), Q, vorticity_mag in one .vdb per export).

Scene = studio shot of the car (triangle mesh include from make_car_mesh.py) with the flow
field as volumes:
  wake     total-pressure-loss volume  L = 1 - Cpt  (soft translucent, scattering + a little
           emission), shaped by map_range + power so that only the wake core is dense
  vortex   Q-criterion vortex tubes (A-pillar, mirror, wheel, C-pillar/trunk vortices) as
           glowing filaments coloured by |U|
  combined both closures added (add_closure) on one volume object
  car      no volume (look development of the car/studio only)
See README.md for the node graphs.

Output modes:
  --orbit N     N per-frame XMLs frame_%04d.xml for one VDB (camera path, eased)
  --vdb a b ... one XML per VDB (converging sequence), camera fixed at --cam-t
  --template    one template XML with buffer="{VDB_DATA}"
Every XML gets a shared <outdir>/scene.xml.bin (ramps, ground) via symlink, and includes the
car mesh (absolute path, LAST element: the xml_bin reader switches to the include's .bin).

World = OpenFOAM metres, z up, x = flow direction (car nose at x = -0.81, rear at 3.80,
floor z = -0.3176). Volume and car object transforms are identity.
"""
import argparse
import math
import os
import struct

RAMP = 257
ZFLOOR = -0.3176

# ------------------------------------------------------------------ helpers


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def add(a, b): return [a[i] + b[i] for i in range(3)]
def mul(a, s): return [x * s for x in a]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a):
    l = math.sqrt(sum(x * x for x in a))
    return [x / l for x in a]


def fmt(v):
    return " ".join("%.7g" % x for x in v)


def look_at(pos, target, up=(0, 0, 1)):
    """Cycles camera matrix (3x4 row major; columns right, up, forward, position)."""
    f = norm(sub(target, pos))
    r = norm(cross(f, list(up)))
    u = cross(r, f)
    m = []
    for row in range(3):
        m += [r[row], u[row], f[row], pos[row]]
    return m


def light_tfm(pos, target, up=(0, 0, 1)):
    """Area light: emits along -Z of its frame -> Z = -(target - pos)."""
    d = norm(sub(target, pos))
    z = mul(d, -1)
    x = norm(cross(list(up), z)) if abs(z[2]) < 0.99 else [1, 0, 0]
    y = cross(z, x)
    m = []
    for row in range(3):
        m += [x[row], y[row], z[row], pos[row]]
    return m


def parse_pts(spec, ncomp):
    pts = []
    for item in spec.split(";"):
        item = item.strip()
        if not item:
            continue
        t, v = item.split(":")
        vals = [float(x) for x in v.split(",")]
        assert len(vals) == ncomp, item
        pts.append((float(t), vals))
    pts.sort()
    return pts


def sample(pts, t):
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            f = (t - t0) / max(1e-9, t1 - t0)
            f = f * f * (3 - 2 * f)  # smoothstep per segment
            return [a * (1 - f) + b * f for a, b in zip(v0, v1)]
    return pts[-1][1]


def table(spec, ncomp):
    pts = parse_pts(spec, ncomp)
    return [sample(pts, i / (RAMP - 1)) for i in range(RAMP)]


class Bin:
    def __init__(self):
        self.data = bytearray()

    def floats(self, vals):
        off = len(self.data)
        self.data += struct.pack("<Q", len(vals)) + struct.pack("<%df" % len(vals), *vals)
        return off

    def ints(self, vals):
        off = len(self.data)
        self.data += struct.pack("<Q", len(vals)) + struct.pack("<%di" % len(vals), *vals)
        return off

    def bools(self, vals):
        off = len(self.data)
        self.data += struct.pack("<Q", len(vals)) + bytes(1 if v else 0 for v in vals)
        return off

    def packed3(self, pts):
        off = len(self.data)
        self.data += struct.pack("<Q", 12 * len(pts))
        for c in pts:
            self.data += struct.pack("<3f", *c)
        return off

    def colors(self, rgbs):
        off = len(self.data)
        self.data += struct.pack("<Q", len(rgbs))
        for c in rgbs:
            self.data += struct.pack("<4f", c[0], c[1], c[2], 0.0)
        return off


# Colour ramps (linear RGB), t in 0..1
RAMPS = {
    # wake: loss L -> pale steel blue -> teal -> deep blue core
    "wake_ice": "0:0.55,0.75,0.95;0.35:0.30,0.62,0.90;0.7:0.12,0.38,0.85;1:0.06,0.16,0.60",
    "wake_teal": "0:0.45,0.85,0.85;0.4:0.15,0.65,0.75;0.75:0.05,0.35,0.60;1:0.04,0.12,0.40",
    "wake_white": "0:0.85,0.88,0.92;1:0.55,0.62,0.75",
    # vortex: |U| (slow core -> fast) colour of the glowing filaments
    "vort_ember": "0:0.55,0.03,0.10;0.3:0.95,0.20,0.03;0.55:1.0,0.50,0.05;0.8:1.0,0.80,0.30;1:1.0,0.95,0.80",
    "vort_ice": "0:0.25,0.02,0.60;0.3:0.05,0.12,0.90;0.55:0.0,0.50,1.0;0.8:0.10,0.90,0.90;1:0.80,1.00,0.95",
    "vort_plasma": "0:0.30,0.02,0.55;0.3:0.75,0.05,0.55;0.55:0.98,0.30,0.25;0.8:1.0,0.65,0.10;1:0.95,0.95,0.45",
    "vort_turbo": "0:0.19,0.07,0.23;0.15:0.27,0.45,0.95;0.35:0.10,0.85,0.75;0.5:0.45,0.98,0.35;0.65:0.90,0.85,0.20;0.82:0.98,0.45,0.08;1:0.70,0.08,0.02",
}

# Car paints (base colour, metallic, roughness, coat)
PAINTS = {
    "graphite": ([0.05, 0.053, 0.058], 0.7, 0.30, 1.0),
    "silver": ([0.55, 0.56, 0.58], 1.0, 0.28, 1.0),
    "clay": ([0.55, 0.53, 0.50], 0.0, 0.55, 0.0),
    "white": ([0.80, 0.80, 0.78], 0.0, 0.35, 1.0),
    "midnight": ([0.010, 0.020, 0.050], 0.8, 0.30, 1.0),
    "red": ([0.45, 0.012, 0.010], 0.3, 0.30, 1.0),
}

# ------------------------------------------------------------------ shaders


def node_math(name, op, v2=None, v3=None):
    s = f'<math name="{name}"><socket name="math_type" value="{op}" type_name="enum" />'
    if v2 is not None:
        s += f'<socket name="value2" value="{v2}" type_name="float" />'
    if v3 is not None:
        s += f'<socket name="value3" value="{v3}" type_name="float" />'
    return s + "</math>"


def node_mr(name, a, b, c=0.0, d=1.0):
    return (f'<map_range name="{name}"><socket name="from_min" value="{a}" type_name="float" />'
            f'<socket name="from_max" value="{b}" type_name="float" />'
            f'<socket name="to_min" value="{c}" type_name="float" />'
            f'<socket name="to_max" value="{d}" type_name="float" />'
            f'<socket name="clamp" value="true" type_name="boolean" /></map_range>')


def conn(a, sa, b, sb):
    return f'<connect from_node="{a}" from_socket="{sa}" to_node="{b}" to_socket="{sb}" />'


def shader_mask(a):
    """Box fade mask m(P) in [0,1]: 0 at the VDB box faces (hides the half-voxel band towards
    the background value 0), 1 inside. Floor face fades over --fade-floor."""
    b, f = a.box, a.fade
    L = ['<texture_coordinate name="m_tc" />', '<separate_xyz name="m_sep" />',
         conn("m_tc", "object", "m_sep", "vector")]
    terms = []
    for i, ax in enumerate("xyz"):
        lo, hi = b[i], b[i + 3]
        flo = a.fade_floor if ax == "z" else f
        L.append(node_mr(f"m_{ax}0", lo, lo + flo))
        L.append(node_mr(f"m_{ax}1", hi, hi - f))
        L.append(conn("m_sep", ax, f"m_{ax}0", "value"))
        L.append(conn("m_sep", ax, f"m_{ax}1", "value"))
        terms += [f"m_{ax}0", f"m_{ax}1"]
    if a.walld:
        # wall-distance grid (vdb_walldist.py): fades out the near-wall shell of Q / loss
        L.append('<attribute name="m_wd"><socket name="attribute" value="walld" type_name="string" /></attribute>')
        L.append(node_mr("m_wall", a.wall_fade[0], a.wall_fade[1]))
        L.append(conn("m_wd", "fac", "m_wall", "value"))
        terms.append("m_wall")
    prev = terms[0]
    for k, t in enumerate(terms[1:]):
        n = f"m_p{k}"
        L.append(node_math(n, "multiply"))
        L.append(conn(prev, "result" if prev.startswith("m_") and not prev.startswith("m_p") else "value", n, "value1"))
        L.append(conn(t, "result", n, "value2"))
        prev = n
    return "\n\t\t".join(L), prev


def shader_wake(a, o, mask):
    """L = 1 - Cpt -> map_range(lo..hi) -> power(gamma) = w;  density = w * mask * D,
    colour (albedo) = ramp(w), emission = w * E * ramp(w)."""
    L = ['<attribute name="w_attr"><socket name="attribute" value="Cpt" type_name="string" /></attribute>',
         node_math("w_loss", "subtract"),
         '<value name="w_one"><socket name="value" value="1" type_name="float" /></value>',
         node_mr("w_mr", a.loss[0], a.loss[1]),
         node_math("w_pow", "power", a.wake_gamma),
         f'<rgb_ramp name="w_ramp"><socket name="ramp" value="{o["wake_c"]}" type_name="array_color" />'
         f'<socket name="ramp_alpha" value="{o["wake_a"]}" type_name="array_float" /></rgb_ramp>',
         node_math("w_m", "multiply"),
         node_math("w_dens", "multiply", a.wake_density),
         node_math("w_emis", "multiply", a.wake_emission),
         f'<principled_volume name="w_pv"><socket name="anisotropy" value="{a.wake_aniso}" type_name="float" />'
         f'<socket name="absorption_color" value="{fmt(a.wake_absorption + [0])}" type_name="color" /></principled_volume>',
         conn("w_one", "value", "w_loss", "value1"),
         conn("w_attr", "fac", "w_loss", "value2"),
         conn("w_loss", "value", "w_mr", "value"),
         conn("w_mr", "result", "w_pow", "value1"),
         conn("w_pow", "value", "w_ramp", "fac"),
         conn("w_ramp", "alpha", "w_m", "value1"),
         conn(mask, "value", "w_m", "value2"),
         conn("w_m", "value", "w_dens", "value1"),
         conn("w_m", "value", "w_emis", "value1"),
         conn("w_dens", "value", "w_pv", "density"),
         conn("w_emis", "value", "w_pv", "emission_strength"),
         conn("w_ramp", "color", "w_pv", "color"),
         conn("w_ramp", "color", "w_pv", "emission_color")]
    return "\n\t\t".join(L), "w_pv"


def shader_vortex(a, o, mask):
    """Q -> map_range(Qlo..Qhi) -> power(gamma) -> alpha LUT = q;  |U| -> map_range -> colour LUT.
    density = q * D, emission = q * E * colour (glowing filaments)."""
    L = ['<attribute name="v_attrQ"><socket name="attribute" value="Q" type_name="string" /></attribute>',
         f'<attribute name="v_attrU"><socket name="attribute" value="{a.vortex_color_field}" type_name="string" /></attribute>',
         node_mr("v_mrQ", a.qrange[0], a.qrange[1]),
         node_math("v_pow", "power", a.qgamma),
         f'<rgb_ramp name="v_rampQ"><socket name="ramp" value="{o["vort_c"]}" type_name="array_color" />'
         f'<socket name="ramp_alpha" value="{o["vort_a"]}" type_name="array_float" /></rgb_ramp>',
         node_mr("v_mrU", a.urange[0], a.urange[1]),
         f'<rgb_ramp name="v_rampU"><socket name="ramp" value="{o["vort_c"]}" type_name="array_color" />'
         f'<socket name="ramp_alpha" value="{o["vort_a"]}" type_name="array_float" /></rgb_ramp>',
         node_math("v_m", "multiply"),
         '<attribute name="v_attrUm"><socket name="attribute" value="U_mag" type_name="string" /></attribute>',
         node_mr("v_umask", a.vortex_umask[0], a.vortex_umask[1]),
         node_math("v_m2", "multiply"),
         node_math("v_dens", "multiply", a.vortex_density),
         node_math("v_emis", "multiply", a.vortex_emission),
         f'<principled_volume name="v_pv"><socket name="anisotropy" value="{a.vortex_aniso}" type_name="float" />'
         f'<socket name="absorption_color" value="{fmt(a.vortex_absorption + [0])}" type_name="color" /></principled_volume>',
         conn("v_attrQ", "fac", "v_mrQ", "value"),
         conn("v_mrQ", "result", "v_pow", "value1"),
         conn("v_pow", "value", "v_rampQ", "fac"),
         conn("v_attrU", "fac", "v_mrU", "value"),
         conn("v_mrU", "result", "v_rampU", "fac"),
         conn("v_rampQ", "alpha", "v_m", "value1"),
         conn(mask, "value", "v_m", "value2"),
         conn("v_attrUm", "fac", "v_umask", "value"),
         conn("v_m", "value", "v_m2", "value1"),
         conn("v_umask", "result", "v_m2", "value2"),
         conn("v_m2", "value", "v_dens", "value1"),
         conn("v_m2", "value", "v_emis", "value1"),
         conn("v_dens", "value", "v_pv", "density"),
         conn("v_emis", "value", "v_pv", "emission_strength"),
         conn("v_rampU", "color", "v_pv", "color"),
         conn("v_rampU", "color", "v_pv", "emission_color")]
    return "\n\t\t".join(L), "v_pv"


def bsdf_shader(name, base, metallic, rough, coat=0.0, coat_rough=0.03, spec=0.5):
    return f"""
	<shader name="{name}">
		<principled_bsdf name="bsdf">
			<socket name="base_color" value="{fmt(list(base) + [0])}" type_name="color" />
			<socket name="metallic" value="{metallic}" type_name="float" />
			<socket name="roughness" value="{rough}" type_name="float" />
			<socket name="specular_ior_level" value="{spec}" type_name="float" />
			<socket name="coat_weight" value="{coat}" type_name="float" />
			<socket name="coat_roughness" value="{coat_rough}" type_name="float" />
		</principled_bsdf>
		<connect from_node="bsdf" from_socket="BSDF" to_node="output" to_socket="surface" />
	</shader>"""


def car_shaders(a):
    base, met, rough, coat = PAINTS[a.paint]
    if a.paint_color:
        base = a.paint_color
    s = bsdf_shader("car_paint", base, met, rough, coat, 0.03)
    if a.paint == "clay":
        g = [0.5, 0.49, 0.47]
        s += bsdf_shader("car_glass", [0.30, 0.31, 0.32], 0.0, 0.2, 0.0)
        s += bsdf_shader("car_trim", g, 0.0, 0.6)
        s += bsdf_shader("car_tyre", [0.25, 0.25, 0.25], 0.0, 0.7)
        s += bsdf_shader("car_metal", g, 0.0, 0.5)
        s += bsdf_shader("car_under", g, 0.0, 0.6)
        s += bsdf_shader("car_lamp", [0.6, 0.6, 0.6], 0.0, 0.3)
    else:
        s += bsdf_shader("car_glass", [0.004, 0.005, 0.006], 0.0, 0.12, 0.6, 0.08, 0.5)
        s += bsdf_shader("car_trim", [0.012, 0.012, 0.013], 0.0, 0.45)
        s += bsdf_shader("car_tyre", [0.018, 0.018, 0.019], 0.0, 0.75, 0.0, 0.03, 0.3)
        s += bsdf_shader("car_metal", [0.62, 0.63, 0.65], 1.0, 0.22)
        s += bsdf_shader("car_under", [0.03, 0.03, 0.032], 0.0, 0.6)
        s += bsdf_shader("car_lamp", [0.85, 0.86, 0.88], 1.0, 0.06)
    return s


def ground_shader(a):
    """Studio floor: dark, slightly glossy; colour fades towards the background colour with the
    distance from the car (radial vignette) so that the horizon line dissolves."""
    return f"""
	<shader name="ground_mat">
		<texture_coordinate name="g_tc" />
		<vector_math name="g_d"><socket name="math_type" value="distance" type_name="enum" />
			<socket name="vector2" value="{fmt(a.ground_center + [0])}" type_name="vector" /></vector_math>
		{node_mr("g_mr", a.ground_fade[0], a.ground_fade[1])}
		<mix_color name="g_col">
			<socket name="a" value="{fmt(a.ground_color + [0])}" type_name="color" />
			<socket name="b" value="{fmt(a.ground_far + [0])}" type_name="color" />
		</mix_color>
		<map_range name="g_rough"><socket name="from_min" value="{a.ground_fade[0]}" type_name="float" />
			<socket name="from_max" value="{a.ground_fade[1]}" type_name="float" />
			<socket name="to_min" value="{a.ground_rough}" type_name="float" />
			<socket name="to_max" value="0.9" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" /></map_range>
		<principled_bsdf name="bsdf">
			<socket name="metallic" value="0" type_name="float" />
			<socket name="specular_ior_level" value="{a.ground_spec}" type_name="float" />
		</principled_bsdf>
		{conn("g_tc", "object", "g_d", "vector1")}
		{conn("g_d", "value", "g_mr", "value")}
		{conn("g_d", "value", "g_rough", "value")}
		{conn("g_mr", "result", "g_col", "fac")}
		{conn("g_col", "result", "bsdf", "base_color")}
		{conn("g_rough", "result", "bsdf", "roughness")}
		{conn("bsdf", "BSDF", "output", "surface")}
	</shader>"""


def lights_xml(a):
    out = ""
    for name, (pos, tgt, su, sv, strength, color, vis) in a.light_list.items():
        out += f"""
	<shader name="{name}_shader">
		<emission name="em"><socket name="color" value="{fmt(color + [0])}" type_name="color" />
			<socket name="strength" value="1" type_name="float" /></emission>
		{conn("em", "emission", "output", "surface")}
	</shader>
	<arealight name="{name}" geometry_type="4">
		<socket name="used_shaders" value="{name}_shader" type_name="array_node" />
		<socket name="light_type" value="area" type_name="enum" />
		<socket name="strength" value="{strength} {strength} {strength} 0" type_name="color" />
		<socket name="sizeu" value="{su}" type_name="float" />
		<socket name="sizev" value="{sv}" type_name="float" />
		<socket name="spread" value="{math.radians(a.light_spread)}" type_name="float" />
		<socket name="use_mis" value="true" type_name="boolean" />
	</arealight>
	<object name="{name}_object">
		<socket name="geometry" value="{name}" type_name="node" />
		<socket name="tfm" value="{fmt(light_tfm(pos, tgt))}" type_name="transform" />
		<socket name="visibility" value="{vis}" type_name="uint" />
	</object>"""
    return out


def camera_for(a, t):
    """Eased camera path: azimuth (0 = from +x/behind the car, 180 = from the front),
    elevation, distance and target interpolated with ease-in/out."""
    e = 0.5 - 0.5 * math.cos(math.pi * t) if a.ease else t
    az = a.az[0] + (a.az[1] - a.az[0]) * e
    el = a.el[0] + (a.el[1] - a.el[0]) * e + a.el_wave * math.sin(2 * math.pi * e)
    dist = a.dist[0] + (a.dist[1] - a.dist[0]) * e + a.dist_wave * math.sin(math.pi * e) ** 2
    tgt = [a.target0[i] + (a.target1[i] - a.target0[i]) * e for i in range(3)]
    azr, elr = math.radians(az), math.radians(el)
    dist += a.dist_side * math.sin(azr) ** 2  # side views need room for the wake
    # rear views (camera behind the car, looking upstream through the wake): higher camera and
    # target pulled towards the car, so the car does not shrink behind the near wake
    rear = max(0.0, math.cos(azr)) ** 2
    el += a.el_rear * rear
    elr = math.radians(el)
    tgt[0] -= a.target_rear * rear
    d = [math.cos(elr) * math.cos(azr), math.cos(elr) * math.sin(azr), math.sin(elr)]
    pos = [tgt[i] + dist * d[i] for i in range(3)]
    pos[2] = max(pos[2], ZFLOOR + 0.15)
    return look_at(pos, tgt)


def scene_xml(a, o, vdb, cam):
    look = a.look
    vol = ""
    grids = []
    if look != "car":
        mask_xml, mask = shader_mask(a)
        body = "\n\t\t" + mask_xml
        outs = []
        if look in ("wake", "combined"):
            x, n = shader_wake(a, o, mask)
            body += "\n\t\t" + x
            outs.append(n)
            grids.append("Cpt")
        if look in ("vortex", "combined"):
            x, n = shader_vortex(a, o, mask)
            body += "\n\t\t" + x
            outs.append(n)
            grids += [g for g in ["Q", a.vortex_color_field, "U_mag"] if g not in grids]
        if len(outs) == 1:
            body += "\n\t\t" + conn(outs[0], "volume", "output", "volume")
        else:
            body += ("\n\t\t<add_closure name=\"addc\" />\n\t\t" + conn(outs[0], "volume", "addc", "closure1")
                     + "\n\t\t" + conn(outs[1], "volume", "addc", "closure2")
                     + "\n\t\t" + conn("addc", "closure", "output", "volume"))
        attrs = "\n".join(
            f'\t\t<attribute name="{g}" std="ATTR_STD_NONE" type="float" element="ATTR_ELEMENT_VOXEL" '
            f'flags="0" buffer="{vdb}" volume_type="openvdb" />' for g in grids)
        if a.walld:
            attrs += (f'\n\t\t<attribute name="walld" std="ATTR_STD_NONE" type="float" element="ATTR_ELEMENT_VOXEL" '
                      f'flags="0" buffer="{a.walld}" volume_type="openvdb" />')
        vol = f"""
	<shader name="vol_shader">{body}
	</shader>
	<volume name="vdb_volume" geometry_type="2">
		<socket name="used_shaders" value="vol_shader" type_name="array_node" />
		<socket name="object_space" value="true" type_name="boolean" />
		<socket name="step_size" value="{a.step_size}" type_name="float" />
{attrs}
	</volume>
	<object name="vdb_object">
		<socket name="geometry" value="vdb_volume" type_name="node" />
		<socket name="tfm" value="1 0 0 0 0 1 0 0 0 0 1 0" type_name="transform" />
	</object>"""
    denoise = ""
    if a.denoise:
        denoise = """
		<socket name="use_denoise" value="true" type_name="boolean" />
		<socket name="denoiser_type" value="openimagedenoise" type_name="enum" />
		<socket name="denoise_use_gpu" value="false" type_name="boolean" />
		<socket name="denoiser_prefilter" value="accurate" type_name="enum" />
		<socket name="denoiser_quality" value="high" type_name="enum" />"""
    G = a.ground_size
    car_inc = f'\n\t<include src="{a.car}" />' if a.car else ""
    return f"""<?xml version="1.0"?>
<!-- occDrivAer studio scene, look={look}, paint={a.paint}
     (data/cyclesphi/scenes/occDrivAer/make_drivaer_scene.py) -->
<cycles>
	<shader name="default_surface" />
	<shader name="default_volume" />
	<shader name="default_light" />
	<shader name="default_background">
		<background_shader name="bg_light">
			<socket name="color" value="{fmt(a.ambient + [0])}" type_name="color" />
			<socket name="strength" value="1" type_name="float" />
		</background_shader>
		<texture_coordinate name="bg_tc" />
		<separate_xyz name="bg_sep" />
		{node_mr("bg_mr", a.bg_range[0], a.bg_range[1])}
		<mix_color name="bg_grad">
			<socket name="a" value="{fmt(a.bg_bottom + [0])}" type_name="color" />
			<socket name="b" value="{fmt(a.bg_top + [0])}" type_name="color" />
		</mix_color>
		<background_shader name="bg_camera"><socket name="strength" value="1" type_name="float" /></background_shader>
		<light_path name="bg_lp" />
		<mix_closure name="bg_mix" />
		{conn("bg_tc", "generated", "bg_sep", "vector")}
		{conn("bg_sep", "z", "bg_mr", "value")}
		{conn("bg_mr", "result", "bg_grad", "fac")}
		{conn("bg_grad", "result", "bg_camera", "color")}
		{conn("bg_lp", "is_camera_ray", "bg_mix", "fac")}
		{conn("bg_light", "background", "bg_mix", "closure1")}
		{conn("bg_camera", "background", "bg_mix", "closure2")}
		{conn("bg_mix", "closure", "output", "surface")}
	</shader>
	<shader name="default_empty" />
{car_shaders(a)}
{ground_shader(a)}
{vol}
{lights_xml(a)}
	<mesh name="ground" geometry_type="0">
		<socket name="used_shaders" value="ground_mat" type_name="array_node" />
		<socket name="triangles" value="{o['g_tris']}" type_name="array_int" />
		<socket name="shader" value="{o['g_shader']}" type_name="array_int" />
		<socket name="smooth" value="{o['g_smooth']}" type_name="array_boolean" />
		<attribute name="P" std="ATTR_STD_POSITION" type="point" element="ATTR_ELEMENT_VERTEX" flags="0" size="4" buffer="{o['g_verts']}" />
	</mesh>
	<object name="ground_object">
		<socket name="geometry" value="ground" type_name="node" />
		<socket name="tfm" value="1 0 0 0 0 1 0 0 0 0 1 0" type_name="transform" />
	</object>

	<camera name="camera">
		<socket name="matrix" value="{fmt(cam)}" type_name="transform" />
		<socket name="fov" value="{math.radians(a.fov):.7g}" type_name="float" />
		<socket name="nearclip" value="0.05" type_name="float" />
		<socket name="farclip" value="1000" type_name="float" />
	</camera>
	<film name="film">
		<socket name="exposure" value="{a.exposure}" type_name="float" />
		<socket name="filter_type" value="blackman_harris" type_name="enum" />
		<socket name="filter_width" value="1.5" type_name="float" />
	</film>
	<background name="background">
		<socket name="visibility" value="255" type_name="uint" />
	</background>
	<integrator name="integrator">
		<socket name="max_bounce" value="{a.max_bounce}" type_name="int" />
		<socket name="max_diffuse_bounce" value="{a.diffuse_bounces}" type_name="int" />
		<socket name="max_glossy_bounce" value="{a.glossy_bounces}" type_name="int" />
		<socket name="max_transmission_bounce" value="2" type_name="int" />
		<socket name="max_volume_bounce" value="{a.volume_bounces}" type_name="int" />
		<socket name="transparent_max_bounce" value="8" type_name="int" />
		<socket name="volume_ray_marching" value="true" type_name="boolean" />
		<socket name="volume_max_steps" value="{a.max_steps}" type_name="int" />
		<socket name="volume_step_rate" value="{a.step_rate}" type_name="float" />
		<socket name="sample_clamp_indirect" value="{a.clamp_indirect}" type_name="float" />
		<socket name="use_adaptive_sampling" value="false" type_name="boolean" />
		<socket name="seed" value="{a.seed}" type_name="int" />{denoise}
	</integrator>

	<backgroundlight name="world_light" geometry_type="5">
		<socket name="used_shaders" value="default_background" type_name="array_node" />
		<socket name="light_type" value="background" type_name="enum" />
		<socket name="use_mis" value="true" type_name="boolean" />
	</backgroundlight>
	<object name="world_object">
		<socket name="geometry" value="world_light" type_name="node" />
	</object>{car_inc}
</cycles>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--look", default="combined", choices=["wake", "vortex", "combined", "car"])
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--vdb", nargs="+", default=[])
    ap.add_argument("--orbit", type=int, default=0, help="N frames of the camera path for --vdb[0]")
    ap.add_argument("--frames", default="", help="subset of orbit frames 'a:b:s' (python range)")
    ap.add_argument("--template", default="")
    ap.add_argument("--cam-t", type=float, default=0.0, help="camera path parameter for --vdb series / template")
    ap.add_argument("--name", default="", help="output XML base name for a single --vdb (default VDB name)")
    ap.add_argument("--car", default="/scratch/project/eu-25-121/milanjaros/openfoam/runs/occDrivAer/geometry/car_mesh.xml")
    ap.add_argument("--box", type=float, nargs=6, default=[-1.3, -1.5, ZFLOOR, 8.5, 1.5, 1.7])
    ap.add_argument("--fade", type=float, default=0.25, help="mask fade width at the box faces (m)")
    ap.add_argument("--fade-floor", type=float, default=0.03)
    ap.add_argument("--walld", default="", help="wall-distance .vdb (grid walld) from vdb_walldist.py")
    ap.add_argument("--wall-fade", type=float, nargs=2, default=[0.03, 0.07], help="mask 0 -> 1 over this wall distance (m)")
    # camera
    ap.add_argument("--az", type=float, nargs=2, default=[150.0, 150.0])
    ap.add_argument("--el", type=float, nargs=2, default=[18.0, 18.0])
    ap.add_argument("--el-wave", type=float, default=0.0)
    ap.add_argument("--dist", type=float, nargs=2, default=[10.0, 10.0])
    ap.add_argument("--dist-wave", type=float, default=0.0)
    ap.add_argument("--dist-side", type=float, default=0.0, help="extra distance x sin^2(azimuth)")
    ap.add_argument("--el-rear", type=float, default=0.0, help="extra elevation x max(0,cos(az))^2")
    ap.add_argument("--target-rear", type=float, default=0.0, help="target shift to -x x max(0,cos(az))^2")
    ap.add_argument("--target0", type=float, nargs=3, default=[2.6, 0.0, 0.25])
    ap.add_argument("--target1", type=float, nargs=3, default=None)
    ap.add_argument("--ease", type=int, default=1)
    ap.add_argument("--fov", type=float, default=32.0, help="fov in degrees (shorter image side)")
    # wake
    ap.add_argument("--loss", type=float, nargs=2, default=[0.05, 0.9], help="map range of 1 - Cpt")
    ap.add_argument("--wake-gamma", type=float, default=1.5)
    ap.add_argument("--wake-colors", default="wake_ice")
    ap.add_argument("--wake-alpha", default="0:0;0.08:0;0.3:0.25;0.7:0.7;1:1")
    ap.add_argument("--wake-density", type=float, default=6.0)
    ap.add_argument("--wake-emission", type=float, default=0.15)
    ap.add_argument("--wake-aniso", type=float, default=0.3)
    ap.add_argument("--wake-absorption", type=float, nargs=3, default=[0.0, 0.0, 0.0])
    # vortex
    ap.add_argument("--qrange", type=float, nargs=2, default=[2e3, 1e5])
    ap.add_argument("--qgamma", type=float, default=0.5)
    ap.add_argument("--vortex-color-field", default="U_mag")
    ap.add_argument("--urange", type=float, nargs=2, default=[10.0, 50.0])
    ap.add_argument("--vortex-umask", type=float, nargs=2, default=[12.0, 20.0],
                    help="vortex opacity x map_range(U_mag): removes the near-wall Q shell (U -> 0 at walls)")
    ap.add_argument("--vortex-colors", default="vort_ember")
    ap.add_argument("--vortex-alpha", default="0:0;0.06:0;0.25:0.3;0.6:0.85;1:1")
    ap.add_argument("--vortex-density", type=float, default=40.0)
    ap.add_argument("--vortex-emission", type=float, default=8.0)
    ap.add_argument("--vortex-aniso", type=float, default=0.2)
    ap.add_argument("--vortex-absorption", type=float, nargs=3, default=[0.0, 0.0, 0.0])
    # car / ground / world
    ap.add_argument("--paint", default="graphite", choices=list(PAINTS))
    ap.add_argument("--paint-color", type=float, nargs=3, default=None)
    ap.add_argument("--ground-size", type=float, default=1500.0)
    ap.add_argument("--ground-color", type=float, nargs=3, default=[0.035, 0.036, 0.04])
    ap.add_argument("--ground-far", type=float, nargs=3, default=[0.006, 0.0065, 0.008])
    ap.add_argument("--ground-center", type=float, nargs=3, default=[2.5, 0.0, ZFLOOR])
    ap.add_argument("--ground-fade", type=float, nargs=2, default=[6.0, 30.0])
    ap.add_argument("--ground-rough", type=float, default=0.28)
    ap.add_argument("--ground-spec", type=float, default=0.5)
    ap.add_argument("--ambient", type=float, nargs=3, default=[0.025, 0.026, 0.03])
    ap.add_argument("--bg-top", type=float, nargs=3, default=[0.030, 0.033, 0.040])
    ap.add_argument("--bg-bottom", type=float, nargs=3, default=[0.010, 0.011, 0.013])
    ap.add_argument("--bg-range", type=float, nargs=2, default=[0.0, 0.7])
    ap.add_argument("--key", type=float, default=220.0, help="key softbox power (W)")
    ap.add_argument("--rim", type=float, default=400.0, help="rim light power (W)")
    ap.add_argument("--fill", type=float, default=80.0, help="fill light power (W)")
    ap.add_argument("--light-spread", type=float, default=120.0)
    ap.add_argument("--lights-visible", type=int, default=0)
    # integrator / film
    ap.add_argument("--exposure", type=float, default=1.0)
    ap.add_argument("--max-bounce", type=int, default=4)
    ap.add_argument("--volume-bounces", type=int, default=0)
    ap.add_argument("--diffuse-bounces", type=int, default=1)
    ap.add_argument("--glossy-bounces", type=int, default=2)
    ap.add_argument("--max-steps", type=int, default=1024)
    ap.add_argument("--step-size", type=float, default=0.0)
    ap.add_argument("--step-rate", type=float, default=3.0, help="ray-marching step = rate x voxel size")
    ap.add_argument("--clamp-indirect", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--denoise", type=int, default=1)
    a = ap.parse_args()
    if a.target1 is None:
        a.target1 = a.target0
    a.box = list(a.box)
    a.ground_color = list(a.ground_color)
    a.ground_center = list(a.ground_center)
    a.ground_far = list(a.ground_far)
    a.ambient, a.bg_top, a.bg_bottom = list(a.ambient), list(a.bg_top), list(a.bg_bottom)
    a.wake_absorption, a.vortex_absorption = list(a.wake_absorption), list(a.vortex_absorption)
    # studio lights (world metres): key softbox above, slightly front-left of the car;
    # rim strip behind/right (edge light on roof line and wake); weak fill from the camera side
    c = [1.5, 0.0, 0.4]
    a.light_list = {
        # visibility 254 = all rays but camera (softbox highlights in the paint), 246 = no glossy
        "key": ([0.8, -2.0, 6.5], c, 12.0, 6.0, a.key, [1.0, 0.97, 0.92], 254),
        "rim": ([7.5, 4.5, 3.0], c, 1.5, 6.0, a.rim, [0.80, 0.88, 1.0], 246),
        "fill": ([-5.0, 5.0, 2.0], c, 4.0, 4.0, a.fill, [0.95, 0.95, 1.0], 246),
    }
    a.light_list = {k: v for k, v in a.light_list.items() if v[4] > 0}

    os.makedirs(a.outdir, exist_ok=True)
    b = Bin()
    wc = RAMPS.get(a.wake_colors, a.wake_colors)
    vc = RAMPS.get(a.vortex_colors, a.vortex_colors)
    o = {"wake_c": b.colors(table(wc, 3)),
         "wake_a": b.floats([v[0] for v in table(a.wake_alpha, 1)]),
         "vort_c": b.colors(table(vc, 3)),
         "vort_a": b.floats([v[0] for v in table(a.vortex_alpha, 1)])}
    G = a.ground_size
    gz = ZFLOOR
    o["g_verts"] = b.packed3([[-G, -G, gz], [G, -G, gz], [G, G, gz], [-G, G, gz]])
    o["g_tris"] = b.ints([0, 1, 2, 0, 2, 3])
    o["g_shader"] = b.ints([0, 0])
    o["g_smooth"] = b.bools([False, False])

    def write(xml_name, vdb, cam):
        xml = os.path.join(a.outdir, xml_name + ".xml")
        with open(xml, "w") as f:
            f.write(scene_xml(a, o, vdb, cam))
        lnk = xml + ".bin"
        if os.path.lexists(lnk):
            os.remove(lnk)
        os.symlink("scene.xml.bin", lnk)
        return xml

    with open(os.path.join(a.outdir, "scene.xml.bin"), "wb") as f:
        f.write(b.data)
    if a.template:
        xml = os.path.join(a.outdir, a.template + ".xml")
        with open(xml, "w") as f:
            f.write(scene_xml(a, o, "{VDB_DATA}", camera_for(a, a.cam_t)))
        os.replace(os.path.join(a.outdir, "scene.xml.bin"), xml + ".bin")
        print("wrote template", xml)
        return
    if a.orbit:
        vdb = os.path.abspath(a.vdb[0]) if a.vdb else ""
        rng = range(a.orbit)
        if a.frames:
            s = [int(x) if x else None for x in a.frames.split(":")]
            rng = range(a.orbit)[slice(*s)]
        for i in rng:
            t = i / max(1, a.orbit - 1)
            write("frame_%04d" % i, vdb, camera_for(a, t))
        print("wrote %d orbit frame(s) to %s" % (len(rng), a.outdir))
        return
    for vdb in a.vdb:
        base = a.name or os.path.basename(vdb)[:-4]
        write(base, os.path.abspath(vdb), camera_for(a, a.cam_t))
    if not a.vdb:
        write(a.name or "scene", "", camera_for(a, a.cam_t))
    print("wrote %d scene(s) to %s" % (max(1, len(a.vdb)), a.outdir))


if __name__ == "__main__":
    main()
