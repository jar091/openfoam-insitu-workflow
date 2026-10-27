#!/usr/bin/env python3
"""
CyclesPhi scene generator for the DLRCJH combustor animations (OpenFOAM HPC TC case
combustion/XiFoam/DLRCJH, mesioVDB grids T, b, Q, U_mag in one .vdb per frame).

Looks (--look), see README.md in this directory for the shader graphs:
  flame     "blackbody" flame: emission volume. Emission colour = blackbody-like ramp of T,
            emission strength = (front(b) * k_front + k_glow) * heat(T), where front(b) is
            a window around the flame front b = 0.5 and heat(T) a ~T^4 ramp. A very weak
            warm absorption gives depth; no scattering (smoke-free).
  vortex    Q-criterion vortex cores: scattering + absorption volume, density from a
            log-like Q ramp, colour from U_mag with a cool (indigo -> teal -> ice) ramp,
            lit by a key sun light; a little self-emission keeps the cores readable.
  combined  both volume closures added in one shader (4 grids).

Geometry (--walls 1): the combustor surface from the case's CAD mesh
(constant/triSurface/DLRCJH.obj, mm) as a cut-away: chamber back wall and floor
(dark ceramic), front plate with the main nozzle and the 7 pilot holes, inlet pipe stub and
pilot tubes (brushed metal). Top and viewer-side walls are removed; the viewer-side window is
optionally a faint quartz pane (--window 1).

Output: one shared scene.xml.bin (ramps + wall mesh) and one XML per frame (orbit camera:
--az0/--az1, --el0/--el1, --dist0/--dist1, --target0/--target1, eased over --nframes).
The frame index of a file is its position in --vdb, or derived from its time index with
--frame-from-name (--first/--step), so follow-mode rendering gets the right camera.

World coordinates: metres, x = chamber axis (0 = front plate, flow in +x), y up.
"""
import argparse
import math
import os
import re
import struct

RAMP = 257

# ------------------------------------------------------------------ math helpers


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a):
    l = math.sqrt(sum(x * x for x in a))
    return [x / l for x in a]


def fmt(v):
    return " ".join("%.7g" % x for x in v)


class Frame:
    """World (m) -> scene units: box centre at origin, box diagonal = 10."""

    def __init__(self, box):
        self.box = box
        self.center = [(box[0][i] + box[1][i]) * 0.5 for i in range(3)]
        diag = math.sqrt(sum((box[1][i] - box[0][i]) ** 2 for i in range(3)))
        self.s = 10.0 / diag

    def p(self, w):
        return [self.s * (w[i] - self.center[i]) for i in range(3)]

    def tfm(self):
        s, c = self.s, self.center
        return [s, 0, 0, -s * c[0], 0, s, 0, -s * c[1], 0, 0, s, -s * c[2]]


def look_at(pos, target, up=(0, 1, 0)):
    f = norm(sub(target, pos))
    r = norm(cross(f, list(up)))
    u = cross(r, f)
    m = []
    for row in range(3):
        m += [r[row], u[row], f[row], pos[row]]
    return m


# ------------------------------------------------------------------ ramps


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
            f = f * f * (3 - 2 * f)  # smoothstep per segment: no kinks in the sheets
            return [a * (1 - f) + b * f for a, b in zip(v0, v1)]
    return pts[-1][1]


def table(spec, ncomp):
    pts = parse_pts(spec, ncomp)
    return [sample(pts, i / (RAMP - 1)) for i in range(RAMP)]


def power_table(gamma, t0=0.0):
    """alpha(t) = ((t - t0)/(1 - t0))^gamma, 0 below t0."""
    out = []
    for i in range(RAMP):
        t = i / (RAMP - 1)
        out.append(0.0 if t <= t0 else ((t - t0) / (1 - t0)) ** gamma)
    return out


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

    def packed3(self, pts):  # raw byte buffer (uint64 byte count) of packed float3
        off = len(self.data)
        self.data += struct.pack("<Q", 12 * len(pts))
        for c in pts:
            self.data += struct.pack("<3f", *c)
        return off

    def colors(self, rgbs):  # 16 B per entry
        off = len(self.data)
        self.data += struct.pack("<Q", len(rgbs))
        for c in rgbs:
            self.data += struct.pack("<4f", c[0], c[1], c[2], 0.0)
        return off


# Blackbody-like ramp over normalised T (t = (T - Tlo)/(Thi - Tlo), default 700..2100 K).
# Linear RGB, hand-tuned towards a photographic flame: ember red -> orange -> amber ->
# yellow-white, with a slightly cool white at the very top (peak temperatures).
FLAME_T_COLORS = ("0:0.30,0.010,0.0;0.25:0.65,0.06,0.004;0.45:1.0,0.20,0.015;"
                  "0.62:1.0,0.42,0.06;0.76:1.0,0.62,0.18;0.88:1.0,0.80,0.45;1:0.95,0.92,0.85")
# Flame-front window over b (1 unburnt, 0 burnt): broad shoulders, peak at 0.5.
FRONT_B_ALPHA = "0:0;0.04:0;0.15:0.10;0.32:0.45;0.5:1;0.68:0.45;0.85:0.10;0.96:0;1:0"
# Vortex colour ramp over normalised U_mag: indigo (slow recirculation) -> blue -> teal ->
# cyan -> ice white (jet core). Linear RGB.
VORTEX_COLORS = ("0:0.10,0.03,0.35;0.25:0.04,0.12,0.75;0.5:0.02,0.45,0.85;"
                 "0.75:0.20,0.85,0.95;1:0.85,0.98,1.0")
# Q opacity over normalised log-ish Q (map range is applied to Q directly, the ramp shapes it)
VORTEX_ALPHA = "0:0;0.03:0;0.15:0.12;0.4:0.45;0.7:0.85;1:1"


# ------------------------------------------------------------------ shaders


def shader_flame(a, p, o):
    """w = front(b) * mask(T) + glow * heat(T); emission = E * w * colour(T); density = D * w."""
    if a.color_mode == "blackbody":
        color = f"""
		<math name="{p}tscale"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.bb_scale}" type_name="float" /></math>
		<blackbody name="{p}bb" />
		<connect from_node="{p}attr_T" from_socket="fac" to_node="{p}tscale" to_socket="value1" />
		<connect from_node="{p}tscale" from_socket="value" to_node="{p}bb" to_socket="temperature" />
		<connect from_node="{p}bb" from_socket="color" to_node="{p}pv" to_socket="emission_color" />"""
    else:
        color = f"""
		<connect from_node="{p}ramp_T" from_socket="color" to_node="{p}pv" to_socket="emission_color" />"""
    return f"""
		<attribute name="{p}attr_T"><socket name="attribute" value="T" type_name="string" /></attribute>
		<attribute name="{p}attr_b"><socket name="attribute" value="b" type_name="string" /></attribute>
		<map_range name="{p}mr_T">
			<socket name="from_min" value="{a.trange[0]}" type_name="float" />
			<socket name="from_max" value="{a.trange[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<map_range name="{p}mr_mask">
			<socket name="from_min" value="{a.tmask[0]}" type_name="float" />
			<socket name="from_max" value="{a.tmask[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<rgb_ramp name="{p}ramp_T">
			<socket name="ramp" value="{o['flame_c']}" type_name="array_color" />
			<socket name="ramp_alpha" value="{o['heat_a']}" type_name="array_float" />
		</rgb_ramp>
		<rgb_ramp name="{p}ramp_b">
			<socket name="ramp" value="{o['flame_c']}" type_name="array_color" />
			<socket name="ramp_alpha" value="{o['front_a']}" type_name="array_float" />
		</rgb_ramp>
		<math name="{p}front"><socket name="math_type" value="multiply" type_name="enum" /></math>
		<math name="{p}glow"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.glow}" type_name="float" /></math>
		<math name="{p}w"><socket name="math_type" value="multiply_add" type_name="enum" />
			<socket name="value2" value="{a.front_gain}" type_name="float" /></math>
		<math name="{p}emis"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.flame_emission}" type_name="float" /></math>
		<math name="{p}dens"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.flame_density}" type_name="float" /></math>
		<principled_volume name="{p}pv">
			<socket name="color" value="0 0 0 0" type_name="color" />
			<socket name="absorption_color" value="{fmt(a.flame_absorption + [0])}" type_name="color" />
		</principled_volume>
		<connect from_node="{p}attr_T" from_socket="fac" to_node="{p}mr_T" to_socket="value" />
		<connect from_node="{p}attr_T" from_socket="fac" to_node="{p}mr_mask" to_socket="value" />
		<connect from_node="{p}mr_T" from_socket="result" to_node="{p}ramp_T" to_socket="fac" />
		<connect from_node="{p}attr_b" from_socket="fac" to_node="{p}ramp_b" to_socket="fac" />
		<connect from_node="{p}ramp_b" from_socket="alpha" to_node="{p}front" to_socket="value1" />
		<connect from_node="{p}mr_mask" from_socket="result" to_node="{p}front" to_socket="value2" />
		<connect from_node="{p}ramp_T" from_socket="alpha" to_node="{p}glow" to_socket="value1" />
		<connect from_node="{p}front" from_socket="value" to_node="{p}w" to_socket="value1" />
		<connect from_node="{p}glow" from_socket="value" to_node="{p}w" to_socket="value3" />
		<connect from_node="{p}w" from_socket="value" to_node="{p}emis" to_socket="value1" />
		<connect from_node="{p}w" from_socket="value" to_node="{p}dens" to_socket="value1" />
		<connect from_node="{p}emis" from_socket="value" to_node="{p}pv" to_socket="emission_strength" />
		<connect from_node="{p}dens" from_socket="value" to_node="{p}pv" to_socket="density" />{color}
"""


def shader_vortex(a, p, o):
    return f"""
		<attribute name="{p}attr_Q"><socket name="attribute" value="Q" type_name="string" /></attribute>
		<attribute name="{p}attr_U"><socket name="attribute" value="U_mag" type_name="string" /></attribute>
		<map_range name="{p}mr_Q">
			<socket name="from_min" value="{a.qrange[0]}" type_name="float" />
			<socket name="from_max" value="{a.qrange[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<math name="{p}qpow"><socket name="math_type" value="power" type_name="enum" />
			<socket name="value2" value="{a.qgamma}" type_name="float" /></math>
		<map_range name="{p}mr_U">
			<socket name="from_min" value="{a.urange[0]}" type_name="float" />
			<socket name="from_max" value="{a.urange[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<rgb_ramp name="{p}ramp_Q">
			<socket name="ramp" value="{o['vort_c']}" type_name="array_color" />
			<socket name="ramp_alpha" value="{o['vort_a']}" type_name="array_float" />
		</rgb_ramp>
		<rgb_ramp name="{p}ramp_U">
			<socket name="ramp" value="{o['vort_c']}" type_name="array_color" />
			<socket name="ramp_alpha" value="{o['vort_a']}" type_name="array_float" />
		</rgb_ramp>
		<math name="{p}dens"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.vortex_density}" type_name="float" /></math>
		<math name="{p}emis"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.vortex_emission}" type_name="float" /></math>
		<principled_volume name="{p}pv">
			<socket name="anisotropy" value="{a.vortex_aniso}" type_name="float" />
			<socket name="absorption_color" value="{fmt(a.vortex_absorption + [0])}" type_name="color" />
		</principled_volume>
		<connect from_node="{p}attr_Q" from_socket="fac" to_node="{p}mr_Q" to_socket="value" />
		<connect from_node="{p}mr_Q" from_socket="result" to_node="{p}qpow" to_socket="value1" />
		<connect from_node="{p}qpow" from_socket="value" to_node="{p}ramp_Q" to_socket="fac" />
		<connect from_node="{p}attr_U" from_socket="fac" to_node="{p}mr_U" to_socket="value" />
		<connect from_node="{p}mr_U" from_socket="result" to_node="{p}ramp_U" to_socket="fac" />
		<connect from_node="{p}ramp_Q" from_socket="alpha" to_node="{p}dens" to_socket="value1" />
		<connect from_node="{p}ramp_Q" from_socket="alpha" to_node="{p}emis" to_socket="value1" />
		<connect from_node="{p}ramp_U" from_socket="color" to_node="{p}pv" to_socket="color" />
		<connect from_node="{p}ramp_U" from_socket="color" to_node="{p}pv" to_socket="emission_color" />
		<connect from_node="{p}dens" from_socket="value" to_node="{p}pv" to_socket="density" />
		<connect from_node="{p}emis" from_socket="value" to_node="{p}pv" to_socket="emission_strength" />
"""


def surface_shaders(a):
    """Wall materials: ceramic liner (chamber), brushed metal (nozzle/pilots), quartz window."""
    return f"""
	<shader name="mat_ceramic">
		<principled_bsdf name="bsdf">
			<socket name="base_color" value="{fmt(a.wall_color + [0])}" type_name="color" />
			<socket name="roughness" value="0.55" type_name="float" />
			<socket name="metallic" value="0.0" type_name="float" />
		</principled_bsdf>
		<connect from_node="bsdf" from_socket="BSDF" to_node="output" to_socket="surface" />
	</shader>
	<shader name="mat_metal">
		<principled_bsdf name="bsdf">
			<socket name="base_color" value="{fmt(a.metal_color + [0])}" type_name="color" />
			<socket name="roughness" value="0.32" type_name="float" />
			<socket name="metallic" value="1.0" type_name="float" />
		</principled_bsdf>
		<connect from_node="bsdf" from_socket="BSDF" to_node="output" to_socket="surface" />
	</shader>
	<shader name="mat_window">
		<transparent_bsdf name="tr">
			<socket name="color" value="1 1 1 0" type_name="color" />
		</transparent_bsdf>
		<glossy_bsdf name="gl">
			<socket name="color" value="0.9 0.95 1 0" type_name="color" />
			<socket name="roughness" value="0.05" type_name="float" />
		</glossy_bsdf>
		<mix_closure name="mix">
			<socket name="fac" value="{a.window_reflect}" type_name="float" />
		</mix_closure>
		<connect from_node="tr" from_socket="BSDF" to_node="mix" to_socket="closure1" />
		<connect from_node="gl" from_socket="BSDF" to_node="mix" to_socket="closure2" />
		<connect from_node="mix" from_socket="closure" to_node="output" to_socket="surface" />
	</shader>
"""


# ------------------------------------------------------------------ walls mesh

SHADER_SLOTS = ["mat_ceramic", "mat_metal", "mat_window"]


def read_obj_groups(path):
    V, groups, g = [], {}, None
    with open(path) as f:
        for l in f:
            if l.startswith("v "):
                V.append([float(x) for x in l.split()[1:4]])
            elif l.startswith("g "):
                g = l.split()[1]
            elif l.startswith("f "):
                groups.setdefault(g, []).append([int(t.split("/")[0]) - 1 for t in l.split()[1:]])
    return V, groups


def build_walls(a):
    """Returns verts (world m), tris (flat), shader index per tri, smooth flags."""
    verts, tris, shd, smooth = [], [], [], []
    xmax = a.walls_xmax
    h = 0.0475

    def quad(p0, p1, p2, p3, s):
        i = len(verts)
        verts.extend([p0, p1, p2, p3])
        tris.extend([i, i + 1, i + 2, i, i + 2, i + 3])
        shd.extend([s, s]); smooth.extend([False, False])

    # Chamber: back wall (z = -h) and floor (y = -h), cut at walls_xmax; optional
    # viewer-side quartz window (z = +h). Top wall (y = +h) is removed.
    quad([0, -h, -h], [xmax, -h, -h], [xmax, h, -h], [0, h, -h], 0)    # back
    quad([0, -h, -h], [0, -h, h], [xmax, -h, h], [xmax, -h, -h], 0)    # floor
    if a.window:
        quad([0, -h, h], [xmax, -h, h], [xmax, h, h], [0, h, h], 2)
    if a.obj:
        V, G = read_obj_groups(a.obj)
        sel = {"wallChamberFront": 0, "wallInletPipe": 1, "wallsPilots": 1}
        for name, s in sel.items():
            for face in G.get(name, []):
                pts = [[V[k][0] * 1e-3, V[k][1] * 1e-3, V[k][2] * 1e-3] for k in face]
                if name == "wallInletPipe" and min(p[0] for p in pts) < -a.pipe_len:
                    continue  # only a short pipe stub upstream of the plate
                if name == "wallChamberFront" and max(p[2] for p in pts) > h - 1e-6 and \
                        min(p[2] for p in pts) > h - 1e-6:
                    continue
                i = len(verts)
                verts.extend(pts)
                for k in range(1, len(pts) - 1):
                    tris.extend([i, i + k, i + k + 1])
                    shd.append(s); smooth.append(name != "wallChamberFront")
    return verts, tris, shd, smooth


# ------------------------------------------------------------------ camera


def camera_for(a, F, t):
    e = 0.5 - 0.5 * math.cos(math.pi * t)  # ease in/out
    az = a.az0 + (a.az1 - a.az0) * e
    el = a.el0 + (a.el1 - a.el0) * e
    dist = a.dist0 + (a.dist1 - a.dist0) * e
    tgt = [a.target0[i] + (a.target1[i] - a.target0[i]) * e for i in range(3)]
    azr, elr = math.radians(az), math.radians(el)
    # azimuth around the y (up) axis, 0 = looking from +z (side window), 90 = from +x (outlet)
    d = [math.cos(elr) * math.sin(azr), math.sin(elr), math.cos(elr) * math.cos(azr)]
    pos_w = [tgt[i] + dist * d[i] for i in range(3)]
    return look_at(F.p(pos_w), F.p(tgt))


# ------------------------------------------------------------------ scene


def scene_xml(a, F, o, vdb, cam):
    look = a.look
    grids = {"flame": ["T", "b"], "vortex": ["Q", "U_mag"], "combined": ["T", "b", "Q", "U_mag"]}[look]
    body = ""
    if look in ("flame", "combined"):
        body += shader_flame(a, "f_", o)
    if look in ("vortex", "combined"):
        body += shader_vortex(a, "v_", o)
    if look == "flame":
        body += '\t\t<connect from_node="f_pv" from_socket="volume" to_node="output" to_socket="volume" />\n'
    elif look == "vortex":
        body += '\t\t<connect from_node="v_pv" from_socket="volume" to_node="output" to_socket="volume" />\n'
    else:
        body += ('\t\t<add_closure name="addc" />\n'
                 '\t\t<connect from_node="f_pv" from_socket="volume" to_node="addc" to_socket="closure1" />\n'
                 '\t\t<connect from_node="v_pv" from_socket="volume" to_node="addc" to_socket="closure2" />\n'
                 '\t\t<connect from_node="addc" from_socket="closure" to_node="output" to_socket="volume" />\n')
    interp = {"linear": "", "cubic": ' interpolation="INTERPOLATION_CUBIC"'}[a.interpolation]
    attrs = "\n".join(
        f'\t\t<attribute name="{g}" std="ATTR_STD_NONE" type="float" element="ATTR_ELEMENT_VOXEL" '
        f'flags="0" buffer="{vdb}" volume_type="openvdb"{interp} />' for g in grids)
    fov = math.radians(a.fov)

    sd = norm(a.sun_dir)
    up = [0, 1, 0] if abs(sd[1]) < 0.95 else [1, 0, 0]
    sx = norm(cross(up, sd)); sy = cross(sd, sx)
    sun_tfm = [sx[0], sy[0], sd[0], 0, sx[1], sy[1], sd[1], 0, sx[2], sy[2], sd[2], 0]
    sun = ""
    if a.sun_strength > 0:
        sun = f"""
	<shader name="sun_shader">
		<emission name="sun_em">
			<socket name="color" value="{fmt(a.sun_color + [0])}" type_name="color" />
			<socket name="strength" value="1" type_name="float" />
		</emission>
		<connect from_node="sun_em" from_socket="emission" to_node="output" to_socket="surface" />
	</shader>
	<sunlight name="sun" geometry_type="8">
		<socket name="used_shaders" value="sun_shader" type_name="array_node" />
		<socket name="light_type" value="sun" type_name="enum" />
		<socket name="strength" value="{a.sun_strength} {a.sun_strength} {a.sun_strength} 0" type_name="color" />
		<socket name="angle" value="0.15" type_name="float" />
		<socket name="use_mis" value="true" type_name="boolean" />
	</sunlight>
	<object name="sun_object">
		<socket name="geometry" value="sun" type_name="node" />
		<socket name="tfm" value="{fmt(sun_tfm)}" type_name="transform" />
	</object>
"""
    walls = ""
    if a.walls:
        walls = surface_shaders(a) + f"""
	<mesh name="walls" geometry_type="0">
		<socket name="used_shaders" value="{' '.join(SHADER_SLOTS)}" type_name="array_node" />
		<socket name="triangles" value="{o['w_tris']}" type_name="array_int" />
		<socket name="shader" value="{o['w_shader']}" type_name="array_int" />
		<socket name="smooth" value="{o['w_smooth']}" type_name="array_boolean" />
		<attribute name="P" std="ATTR_STD_POSITION" type="point" element="ATTR_ELEMENT_VERTEX" flags="0" size="{o['w_nverts']}" buffer="{o['w_verts']}" />
	</mesh>
	<object name="walls_object">
		<socket name="geometry" value="walls" type_name="node" />
		<socket name="tfm" value="{fmt(F.tfm())}" type_name="transform" />
	</object>
"""
    denoise = ""
    if a.denoise:
        denoise = """
		<socket name="use_denoise" value="true" type_name="boolean" />
		<socket name="denoiser_type" value="openimagedenoise" type_name="enum" />
		<socket name="denoise_use_gpu" value="false" type_name="boolean" />
		<socket name="denoiser_prefilter" value="accurate" type_name="enum" />
		<socket name="denoiser_quality" value="high" type_name="enum" />"""
    return f"""<?xml version="1.0"?>
<!-- DLRCJH combustor, look={look} (data/cyclesphi/scenes/DLRCJH/make_dlrcjh_scene.py) -->
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
		<map_range name="bg_mr">
			<socket name="from_min" value="-0.5" type_name="float" />
			<socket name="from_max" value="0.45" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<mix_color name="bg_grad">
			<socket name="a" value="{fmt(a.bg_bottom + [0])}" type_name="color" />
			<socket name="b" value="{fmt(a.bg_top + [0])}" type_name="color" />
		</mix_color>
		<background_shader name="bg_camera">
			<socket name="strength" value="1" type_name="float" />
		</background_shader>
		<light_path name="bg_lightpath" />
		<mix_closure name="bg_mix" />
		<connect from_node="bg_tc" from_socket="generated" to_node="bg_sep" to_socket="vector" />
		<connect from_node="bg_sep" from_socket="y" to_node="bg_mr" to_socket="value" />
		<connect from_node="bg_mr" from_socket="result" to_node="bg_grad" to_socket="fac" />
		<connect from_node="bg_grad" from_socket="result" to_node="bg_camera" to_socket="color" />
		<connect from_node="bg_lightpath" from_socket="is_camera_ray" to_node="bg_mix" to_socket="fac" />
		<connect from_node="bg_light" from_socket="background" to_node="bg_mix" to_socket="closure1" />
		<connect from_node="bg_camera" from_socket="background" to_node="bg_mix" to_socket="closure2" />
		<connect from_node="bg_mix" from_socket="closure" to_node="output" to_socket="surface" />
	</shader>
	<shader name="default_empty" />

	<shader name="vol_shader">{body}	</shader>
{sun}{walls}
	<camera name="camera">
		<socket name="matrix" value="{fmt(cam)}" type_name="transform" />
		<socket name="fov" value="{fov:.7g}" type_name="float" />
		<socket name="nearclip" value="0.01" type_name="float" />
		<socket name="farclip" value="1000" type_name="float" />
	</camera>
	<film name="film">
		<socket name="exposure" value="{a.exposure}" type_name="float" />
		<socket name="filter_type" value="blackman_harris" type_name="enum" />
		<socket name="filter_width" value="1.5" type_name="float" />
	</film>
	<background name="background">
		<socket name="visibility" value="157" type_name="uint" />
	</background>
	<integrator name="integrator">
		<socket name="max_bounce" value="{a.max_bounce}" type_name="int" />
		<socket name="max_diffuse_bounce" value="2" type_name="int" />
		<socket name="max_glossy_bounce" value="2" type_name="int" />
		<socket name="max_volume_bounce" value="{a.volume_bounces}" type_name="int" />
		<socket name="transparent_max_bounce" value="8" type_name="int" />
		<socket name="volume_ray_marching" value="{'true' if a.ray_marching else 'false'}" type_name="boolean" />
		<socket name="volume_max_steps" value="{a.max_steps}" type_name="int" />
		<socket name="volume_step_rate" value="{a.step_rate}" type_name="float" />
		<socket name="sample_clamp_indirect" value="{a.clamp_indirect}" type_name="float" />
		<socket name="use_adaptive_sampling" value="false" type_name="boolean" />{denoise}
	</integrator>

	<volume name="vdb_volume" geometry_type="2">
		<socket name="used_shaders" value="vol_shader" type_name="array_node" />
		<socket name="object_space" value="true" type_name="boolean" />
		<socket name="step_size" value="{a.step_size}" type_name="float" />
{attrs}
	</volume>
	<object name="vdb_object">
		<socket name="geometry" value="vdb_volume" type_name="node" />
		<socket name="tfm" value="{fmt(F.tfm())}" type_name="transform" />
		<socket name="visibility" value="1693" type_name="uint" />
	</object>

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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--look", required=True, choices=["flame", "vortex", "combined"])
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--vdb", nargs="+", default=[])
    ap.add_argument("--template", default="",
                    help="write one template <outdir>/<name>.xml + .xml.bin with buffer={VDB_DATA} "
                         "and the camera at --template-t (0..1 of the orbit) instead of per-frame XMLs")
    ap.add_argument("--template-t", type=float, default=0.0)
    ap.add_argument("--box", type=float, nargs=6, default=[-0.004, -0.0475, -0.0475, 0.36, 0.0475, 0.0475],
                    help="VDB box (world m): x0 y0 z0 x1 y1 z1 (scene normalisation)")
    ap.add_argument("--frame-from-name", action="store_true")
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--nframes", type=int, default=0, help="frames of the orbit (default: number of files)")
    # camera (world m / degrees)
    ap.add_argument("--target0", type=float, nargs=3, default=[0.17, -0.005, 0.0])
    ap.add_argument("--target1", type=float, nargs=3, default=None)
    ap.add_argument("--az0", type=float, default=35.0, help="0 = from +z (side), 90 = from +x (outlet)")
    ap.add_argument("--az1", type=float, default=None)
    ap.add_argument("--el0", type=float, default=25.0)
    ap.add_argument("--el1", type=float, default=None)
    ap.add_argument("--dist0", type=float, default=0.45)
    ap.add_argument("--dist1", type=float, default=None)
    ap.add_argument("--fov", type=float, default=30.0)
    # flame
    ap.add_argument("--trange", type=float, nargs=2, default=[700.0, 2100.0])
    ap.add_argument("--heat-gamma", type=float, default=3.0, help="heat(T) = t^gamma above --heat-t0")
    ap.add_argument("--heat-t0", type=float, default=0.25)
    ap.add_argument("--flame-colors", default=FLAME_T_COLORS)
    ap.add_argument("--front-alpha", default=FRONT_B_ALPHA)
    ap.add_argument("--front-gain", type=float, default=1.0)
    ap.add_argument("--tmask", type=float, nargs=2, default=[950.0, 1250.0], help="front visible only where T rises above this window")
    ap.add_argument("--color-mode", default="ramp", choices=["ramp", "blackbody"])
    ap.add_argument("--bb-scale", type=float, default=1.4, help="blackbody temperature = bb_scale * T")
    ap.add_argument("--glow", type=float, default=0.02, help="emission of hot products off the front")
    ap.add_argument("--flame-emission", type=float, default=30.0)
    ap.add_argument("--flame-density", type=float, default=0.15)
    ap.add_argument("--flame-absorption", type=float, nargs=3, default=[0.05, 0.25, 0.6])
    # vortex
    ap.add_argument("--qrange", type=float, nargs=2, default=[1e7, 1e9])
    ap.add_argument("--qgamma", type=float, default=0.5)
    ap.add_argument("--urange", type=float, nargs=2, default=[5.0, 120.0])
    ap.add_argument("--vortex-colors", default=VORTEX_COLORS)
    ap.add_argument("--vortex-alpha", default=VORTEX_ALPHA)
    ap.add_argument("--vortex-density", type=float, default=60.0)
    ap.add_argument("--vortex-emission", type=float, default=1.0)
    ap.add_argument("--vortex-aniso", type=float, default=0.35)
    ap.add_argument("--vortex-absorption", type=float, nargs=3, default=[0.6, 0.8, 0.9])
    # lights / world
    ap.add_argument("--sun-strength", type=float, default=0.0)
    ap.add_argument("--sun-dir", type=float, nargs=3, default=[-0.3, 1.0, 0.6])
    ap.add_argument("--sun-color", type=float, nargs=3, default=[0.85, 0.92, 1.0])
    ap.add_argument("--ambient", type=float, nargs=3, default=[0.03, 0.035, 0.045])
    ap.add_argument("--bg-top", type=float, nargs=3, default=[0.016, 0.019, 0.03])
    ap.add_argument("--bg-bottom", type=float, nargs=3, default=[0.001, 0.001, 0.002])
    # walls
    ap.add_argument("--walls", type=int, default=1)
    ap.add_argument("--obj", default="/scratch/project/eu-25-121/milanjaros/openfoam/runs/DLRCJH/geometry/constant/triSurface/DLRCJH.obj")
    ap.add_argument("--walls-xmax", type=float, default=0.36)
    ap.add_argument("--pipe-len", type=float, default=0.06)
    ap.add_argument("--window", type=int, default=0)
    ap.add_argument("--window-reflect", type=float, default=0.06)
    ap.add_argument("--wall-color", type=float, nargs=3, default=[0.16, 0.15, 0.14])
    ap.add_argument("--metal-color", type=float, nargs=3, default=[0.55, 0.56, 0.58])
    # integrator / film
    ap.add_argument("--exposure", type=float, default=1.0)
    ap.add_argument("--max-bounce", type=int, default=3)
    ap.add_argument("--volume-bounces", type=int, default=0)
    ap.add_argument("--ray-marching", type=int, default=1)
    ap.add_argument("--max-steps", type=int, default=1024)
    ap.add_argument("--step-size", type=float, default=0.0)
    ap.add_argument("--step-rate", type=float, default=1.0, help="integrator volume_step_rate (x voxel size)")
    ap.add_argument("--clamp-indirect", type=float, default=10.0)
    ap.add_argument("--interpolation", default="linear", choices=["linear", "cubic"])
    ap.add_argument("--denoise", type=int, default=1)
    a = ap.parse_args()
    for k in ("target", "az", "el", "dist"):
        if getattr(a, k + "1") is None:
            setattr(a, k + "1", getattr(a, k + "0"))

    F = Frame(((a.box[0], a.box[1], a.box[2]), (a.box[3], a.box[4], a.box[5])))
    os.makedirs(a.outdir, exist_ok=True)
    b = Bin()
    o = {"flame_c": b.colors(table(a.flame_colors, 3)),
         "heat_a": b.floats(power_table(a.heat_gamma, a.heat_t0)),
         "front_a": b.floats([v[0] for v in table(a.front_alpha, 1)]),
         "vort_c": b.colors(table(a.vortex_colors, 3)),
         "vort_a": b.floats([v[0] for v in table(a.vortex_alpha, 1)])}
    if a.walls:
        verts, tris, shd, smooth = build_walls(a)
        o["w_verts"] = b.packed3(verts)
        o["w_nverts"] = len(verts)
        o["w_tris"] = b.ints(tris)
        o["w_shader"] = b.ints(shd)
        o["w_smooth"] = b.bools(smooth)
    if a.template:
        xml = os.path.join(a.outdir, a.template + ".xml")
        with open(xml + ".bin", "wb") as f:
            f.write(b.data)
        with open(xml, "w") as f:
            f.write(scene_xml(a, F, o, "{VDB_DATA}", camera_for(a, F, a.template_t)))
        print("wrote template", xml)
        return
    with open(os.path.join(a.outdir, "scene.xml.bin"), "wb") as f:
        f.write(b.data)
    n = a.nframes or len(a.vdb)
    for i, vdb in enumerate(a.vdb):
        base = os.path.basename(vdb)[:-4]
        k = i
        if a.frame_from_name:
            k = (int(re.findall(r"(\d+)", base)[-1]) - a.first) // a.step
        t = 0.0 if n <= 1 else min(1.0, max(0.0, k / (n - 1)))
        xml = os.path.join(a.outdir, base + ".xml")
        with open(xml, "w") as f:
            f.write(scene_xml(a, F, o, os.path.abspath(vdb), camera_for(a, F, t)))
        lnk = xml + ".bin"
        if os.path.lexists(lnk):
            os.remove(lnk)
        os.symlink("scene.xml.bin", lnk)
    print("wrote %d scene(s) to %s" % (len(a.vdb), a.outdir))


if __name__ == "__main__":
    main()
