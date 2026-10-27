#!/usr/bin/env python3
"""
CyclesPhi scene generator for the MB12 model wind farm LES (OpenFOAM HPC TC case
incompressible/pimpleFoam/LES/modelwindfarm/windfarmmodel, 30 rotorDisk turbines),
rendered from mesioVDB exports (one .vdb per frame with the grids U_mag, Q, vorticity_mag).

Scene units are metres (the VDB world space, object transforms are identity apart from
the rotors). Wind blows along +x, z is up, the wind-tunnel floor is z = 0.

Looks (--look):
  wake      velocity deficit d = 1 - |U| / U_inflow(z) as a soft blue-white scattering
            volume. U_inflow(z) = 0.3053 ln(z) + 3.179 m/s is the log-law fit of the
            inlet profile (constant/boundaryData/inlet/0/UMean), evaluated in the shader
            from the shading position, so the undisturbed boundary layer stays clear and
            only the turbine wakes show up.
  vortex    Q-criterion vortex tubes as thin glowing filaments: opacity/emission from Q,
            colour from the vorticity magnitude (amber -> gold -> white-hot).
  combined  both volumes added in one shader (wake scattering + vortex emission).

Geometry (all looks): 30 turbines (tower, nacelle, spinner, 3 tapered and twisted blades
from the rotorDisk blade data, D = 0.15 m, hub 0.125 m), a ground plane with a faint
1D (0.15 m) checker, a sky-gradient world and a warm low sun with soft shadows.

Output: <outdir>/<name>.xml for every frame, one shared <outdir>/common.bin and
<name>.xml.bin -> common.bin symlinks (the CyclesPhi reader opens <xml>.bin).
Per frame only the VDB path, the camera (slow dolly) and the rotor angles change.

Usage:
  make_windfarm_scene.py --look combined --outdir DIR --vdb VDB/wf_002005.vdb ... \
      [--frame-from-name --first 2005 --step 5 --nframes 300] [options]
  make_windfarm_scene.py --look combined --template OUT.xml   # placeholder {VDB_DATA}
"""
import argparse
import math
import os
import re
import struct

RAMP = 257

# ------------------------------------------------------------------ case geometry
ROWS_X = [3.0 + 0.75 * i for i in range(10)]   # rotor planes (5D spacing)
COLS_Y = [0.3, 0.9, 1.5]                        # 4D lateral spacing
HUB_Z = 0.125
R_TIP = 0.075
VDB_BOX = ((2.70, 0.005, 0.0), (10.79, 1.795, 0.45))  # mesioVDB box (functionsVis)
# Inflow log-law fit U(z) = A ln z + B (inlet UMean, u*/kappa = 0.305 m/s, z0 ~ 3e-5 m)
LOG_A, LOG_B = 0.3053, 3.179
# rotorDisk blade data: radius, twist (deg), chord
BLADE = [(0.01, -20.50, 0.0139), (0.02, -20.9, 0.0147), (0.03, -19.83, 0.0147),
         (0.04, -16.91, 0.0141), (0.05, -13.19, 0.0131), (0.06, -10.67, 0.0118),
         (0.07, -9.12, 0.0102), (0.075, -6.66, 0.0060)]


# ------------------------------------------------------------------ small helpers
def fmt(v):
    return " ".join("%.7g" % x for x in v)


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def add(a, b): return [a[i] + b[i] for i in range(3)]
def mul(a, s): return [x * s for x in a]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def lerp(a, b, t): return [a[i] * (1 - t) + b[i] * t for i in range(len(a))]
def norm(a):
    l = math.sqrt(sum(x * x for x in a))
    return [x / l for x in a]


def look_at(pos, target, up=(0, 0, 1)):
    """Cycles camera matrix (3x4 row-major): columns right, up, forward, position."""
    f = norm(sub(target, pos))
    r = norm(cross(f, list(up)))
    u = cross(r, f)
    m = []
    for row in range(3):
        m += [r[row], u[row], f[row], pos[row]]
    return m


def srgb2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def ramp_table(points, srgb=True):
    """points: [(t, (r,g,b)), ...] -> 257 linear RGB entries."""
    out = []
    for i in range(RAMP):
        t = i / (RAMP - 1)
        for k in range(len(points) - 1):
            if points[k][0] <= t <= points[k + 1][0]:
                t0, c0 = points[k]
                t1, c1 = points[k + 1]
                f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                c = lerp(c0, c1, f)
                break
        else:
            c = points[0][1] if t < points[0][0] else points[-1][1]
        out.append([srgb2lin(x) for x in c] if srgb else list(c))
    return out


def alpha_table(points):
    out = []
    for i in range(RAMP):
        t = i / (RAMP - 1)
        a = points[-1][1]
        for k in range(len(points) - 1):
            if points[k][0] <= t <= points[k + 1][0]:
                f = 0 if points[k + 1][0] == points[k][0] else (t - points[k][0]) / (points[k + 1][0] - points[k][0])
                # smooth (cosine) interpolation between control points
                f = 0.5 - 0.5 * math.cos(math.pi * f)
                a = points[k][1] * (1 - f) + points[k + 1][1] * f
                break
        out.append(a)
    return out


class Bin:
    def __init__(self):
        self.d = bytearray()

    def floats(self, v):
        o = len(self.d)
        self.d += struct.pack("<Q", len(v)) + struct.pack("<%df" % len(v), *v)
        return o

    def colors(self, v):
        o = len(self.d)
        self.d += struct.pack("<Q", len(v))
        for c in v:
            self.d += struct.pack("<4f", c[0], c[1], c[2], 0.0)
        return o

    def ints(self, v):
        o = len(self.d)
        self.d += struct.pack("<Q", len(v)) + struct.pack("<%di" % len(v), *v)
        return o

    def bools(self, v):
        o = len(self.d)
        self.d += struct.pack("<Q", len(v)) + bytes(1 if x else 0 for x in v)
        return o

    def points_raw(self, pts):
        """Attribute buffer: uint64 byte count + packed_float3 (12 B) per point."""
        body = bytearray()
        for p in pts:
            body += struct.pack("<3f", p[0], p[1], p[2])
        o = len(self.d)
        self.d += struct.pack("<Q", len(body)) + body
        return o


# ------------------------------------------------------------------ meshes
class MeshBuilder:
    def __init__(self):
        self.v = []
        self.t = []
        self.sh = []
        self.sm = []

    def tri(self, a, b, c, shader=0, smooth=True):
        self.t += [a, b, c]
        self.sh.append(shader)
        self.sm.append(smooth)

    def quad(self, a, b, c, d, shader=0, smooth=True):
        self.tri(a, b, c, shader, smooth)
        self.tri(a, c, d, shader, smooth)

    def frustum(self, p0, p1, r0, r1, n=16, cap0=True, cap1=True, shader=0):
        """Truncated cone from p0 (radius r0) to p1 (radius r1)."""
        ax = norm(sub(p1, p0))
        ref = [0, 0, 1] if abs(ax[2]) < 0.9 else [1, 0, 0]
        e1 = norm(cross(ax, ref))
        e2 = cross(ax, e1)
        base = len(self.v)
        for p, r in ((p0, r0), (p1, r1)):
            for k in range(n):
                a = 2 * math.pi * k / n
                self.v.append(add(p, add(mul(e1, r * math.cos(a)), mul(e2, r * math.sin(a)))))
        for k in range(n):
            k1 = (k + 1) % n
            self.quad(base + k, base + k1, base + n + k1, base + n + k, shader)
        for cap, p, off, flip in ((cap0, p0, 0, True), (cap1, p1, n, False)):
            if not cap:
                continue
            c = len(self.v)
            self.v.append(list(p))
            for k in range(n):
                k1 = (k + 1) % n
                if flip:
                    self.tri(c, base + off + k1, base + off + k, shader, False)
                else:
                    self.tri(c, base + off + k, base + off + k1, shader, False)

    def blade(self, phi, shader=0):
        """One blade in rotor-local coordinates (axis +x, centre at origin)."""
        er = [0, math.cos(phi), math.sin(phi)]
        et = [0, -math.sin(phi), math.cos(phi)]
        ex = [1, 0, 0]
        prof = [(-0.5, 0.0), (-0.3, 0.07), (0.1, 0.07), (0.5, 0.0), (0.1, -0.035), (-0.3, -0.035)]
        secs = [(0.006, -22.0, 0.008)] + BLADE
        npf = len(prof)
        base = len(self.v)
        for r, tw, ch in secs:
            b = math.radians(tw)
            cd = add(mul(et, math.cos(b)), mul(ex, math.sin(b)))   # chord direction
            nd = cross(er, cd)                                     # thickness direction
            for (u, w) in prof:
                self.v.append(add(mul(er, r), add(mul(cd, u * ch), mul(nd, w * ch))))
        for s in range(len(secs) - 1):
            for k in range(npf):
                k1 = (k + 1) % npf
                a = base + s * npf
                bb = base + (s + 1) * npf
                self.quad(a + k, a + k1, bb + k1, bb + k, shader)
        tip = base + (len(secs) - 1) * npf
        for k in range(1, npf - 1):
            self.tri(tip, tip + k, tip + k + 1, shader, False)


def build_static():
    m = MeshBuilder()
    for x0 in ROWS_X:
        for y0 in COLS_Y:
            m.frustum([x0 + 0.012, y0, 0.0], [x0 + 0.012, y0, HUB_Z - 0.004], 0.0045, 0.003, 12)
            m.frustum([x0 + 0.004, y0, HUB_Z], [x0 + 0.042, y0, HUB_Z], 0.0068, 0.0055, 16)
            m.frustum([x0 + 0.004, y0, HUB_Z], [x0 - 0.010, y0, HUB_Z], 0.0080, 0.0005, 16, cap1=False)
    return m


def build_rotor():
    m = MeshBuilder()
    for k in range(3):
        m.blade(2 * math.pi * k / 3)
    return m


def build_ground():
    m = MeshBuilder()
    x0, x1, y0, y1, z = -200.0, 200.0, -200.0, 200.0, -0.0005
    m.v = [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]]
    m.quad(0, 1, 2, 3, 0, False)
    return m


def mesh_xml(name, m, shader, b):
    off_t = b.ints(m.t)
    off_s = b.ints(m.sh)
    off_m = b.bools(m.sm)
    off_p = b.points_raw(m.v)
    return f"""	<mesh name="{name}" geometry_type="0">
		<socket name="used_shaders" value="{shader}" type_name="array_node" />
		<socket name="triangles" value="{off_t}" type_name="array_int" />
		<socket name="shader" value="{off_s}" type_name="array_int" />
		<socket name="smooth" value="{off_m}" type_name="array_boolean" />
		<attribute name="P" std="ATTR_STD_POSITION" type="point" element="ATTR_ELEMENT_VERTEX" flags="0" buffer="{off_p}" />
	</mesh>
"""


# ------------------------------------------------------------------ shader graph helper
class Graph:
    def __init__(self, name):
        self.name = name
        self.nodes = []
        self.links = []

    def node(self, typ, name, **socks):
        s = []
        for k, v in socks.items():
            if isinstance(v, tuple) and v[0] in ("enum", "string", "array_color", "array_float"):
                s.append(f'\t\t\t<socket name="{k}" value="{v[1]}" type_name="{v[0]}" />')
            elif isinstance(v, bool):
                s.append(f'\t\t\t<socket name="{k}" value="{"true" if v else "false"}" type_name="boolean" />')
            elif isinstance(v, (list, tuple)):
                vv = list(v) + [0] * (4 - len(v))
                s.append(f'\t\t\t<socket name="{k}" value="{fmt(vv)}" type_name="color" />')
            else:
                s.append(f'\t\t\t<socket name="{k}" value="{v:.9g}" type_name="float" />')
        body = ("\n" + "\n".join(s) + "\n\t\t") if s else ""
        self.nodes.append(f'\t\t<{typ} name="{name}">{body}</{typ}>' if s else f'\t\t<{typ} name="{name}" />')
        return name

    def link(self, a, ao, b, bi):
        self.links.append(f'\t\t<connect from_node="{a}" from_socket="{ao}" to_node="{b}" to_socket="{bi}" />')

    def math(self, name, op, a=None, b=None, **kw):
        """a/b: (node, socket) tuples or floats."""
        kws = dict(math_type=("enum", op))
        if isinstance(a, (int, float)):
            kws["value1"] = float(a)
        if isinstance(b, (int, float)):
            kws["value2"] = float(b)
        kws.update(kw)
        self.node("math", name, **kws)
        if isinstance(a, tuple):
            self.link(a[0], a[1], name, "value1")
        if isinstance(b, tuple):
            self.link(b[0], b[1], name, "value2")
        return (name, "value")

    def maprange(self, name, val, fmin, fmax, typ="linear", clamp=True):
        self.node("map_range", name, range_type=("enum", typ), from_min=fmin, from_max=fmax, clamp=clamp)
        self.link(val[0], val[1], name, "value")
        return (name, "result")

    def xml(self):
        return f'\t<shader name="{self.name}">\n' + "\n".join(self.nodes + self.links) + "\n\t</shader>\n"


TOP_FADE = 0.05


def box_mask(g, pos_sep, eps):
    """Product of smoothstep ramps that fades the volume within eps of the VDB box faces
    (inactive voxels are background 0, which would otherwise map to a full deficit)."""
    (x0, y0, z0), (x1, y1, z1) = VDB_BOX
    terms = []
    # x: inflow/outlet faces; y: side-wall boundary layers of the wind tunnel (no-slip walls
    # at y = 0 and 1.8 m); z: floor boundary layer (wall-function layer, U -> 0 at the floor)
    # and the top face of the box.
    for ax, lo, hi, elo, ehi in (("x", x0, x1, eps, 3 * eps), ("y", y0, y1, 0.07, 0.07),
                                 ("z", z0, z1, 0.022, TOP_FADE)):
        terms.append(g.maprange(f"m_{ax}0", (pos_sep, ax), lo, lo + elo, "smoothstep"))
        terms.append(g.maprange(f"m_{ax}1", (pos_sep, ax), hi, hi - ehi, "smoothstep"))
    m = terms[0]
    for i, t in enumerate(terms[1:]):
        m = g.math(f"m_mul{i}", "multiply", m, t)
    return m


# ------------------------------------------------------------------ volume shaders
WAKE_RAMPS = {
    # sRGB control points on the normalised deficit t
    "blue": [(0.0, (0.86, 0.93, 1.0)), (0.35, (0.62, 0.80, 1.0)),
             (0.7, (0.30, 0.55, 0.98)), (1.0, (0.12, 0.30, 0.85))],
    "ice": [(0.0, (0.97, 0.98, 1.0)), (0.3, (0.80, 0.90, 1.0)), (0.6, (0.45, 0.70, 1.0)),
            (0.85, (0.20, 0.45, 0.95)), (1.0, (0.10, 0.25, 0.80))],
    "cloud": [(0.0, (1.0, 1.0, 1.0)), (0.5, (0.90, 0.95, 1.0)), (1.0, (0.68, 0.84, 1.0))],
    "deep": [(0.0, (0.55, 0.80, 1.0)), (0.4, (0.25, 0.55, 1.0)), (0.8, (0.10, 0.30, 0.95)),
             (1.0, (0.05, 0.15, 0.80))],
    "teal": [(0.0, (0.95, 0.98, 1.0)), (0.35, (0.65, 0.90, 0.97)), (0.7, (0.25, 0.65, 0.90)),
             (1.0, (0.08, 0.35, 0.75))],
}
WAKE_ALPHAS = {
    "soft": [(0.0, 0.0), (0.12, 0.05), (0.45, 0.45), (0.8, 0.85), (1.0, 1.0)],
    "crisp": [(0.0, 0.0), (0.2, 0.02), (0.45, 0.2), (0.7, 0.7), (1.0, 1.0)],
    "core": [(0.0, 0.0), (0.3, 0.0), (0.55, 0.25), (0.8, 0.8), (1.0, 1.0)],
}
def deficit_node(g, pos_sep):
    """d = 1 - |U| / U_inflow(z), U_inflow(z) = LOG_A ln(max(z, 4 mm)) + LOG_B."""
    g.node("attribute", "a_U", attribute=("string", "U_mag"))
    zc = g.math("w_zc", "maximum", (pos_sep, "z"), 0.004)
    lnz = g.math("w_lnz", "logarithm", zc, math.e)
    uref = g.math("w_uref", "multiply_add", lnz, LOG_A, value3=LOG_B)
    ratio = g.math("w_ratio", "divide", ("a_U", "fac"), uref)
    return g.math("w_def", "subtract", 1.0, ratio)


def wake_part(g, b, a, deficit, mask):
    t = g.maprange("w_map", deficit, a.def_range[0], a.def_range[1])
    ramp = ramp_table(WAKE_RAMPS[a.wake_ramp])
    alpha = alpha_table(WAKE_ALPHAS[a.wake_alpha])
    g.node("rgb_ramp", "w_ramp", ramp=("array_color", b.colors(ramp)), ramp_alpha=("array_float", b.floats(alpha)))
    g.link(t[0], t[1], "w_ramp", "fac")
    am = g.math("w_am", "multiply", ("w_ramp", "alpha"), mask)
    dens = g.math("w_dens", "multiply", am, a.wake_density)
    emis = g.math("w_emis", "multiply", am, a.wake_emission)
    g.node("principled_volume", "w_pv", anisotropy=a.wake_anisotropy)
    g.link("w_ramp", "color", "w_pv", "color")
    # emission colour: own ramp (e.g. bright scattering albedo + blue glow in the wake core)
    g.node("rgb_ramp", "w_eramp", ramp=("array_color", b.colors(ramp_table(WAKE_RAMPS[a.wake_emit_ramp]))),
           ramp_alpha=("array_float", b.floats([1.0] * RAMP)))
    g.link(t[0], t[1], "w_eramp", "fac")
    g.link("w_eramp", "color", "w_pv", "emission_color")
    g.link(dens[0], dens[1], "w_pv", "density")
    g.link(emis[0], emis[1], "w_pv", "emission_strength")
    return ("w_pv", "volume")


def vortex_part(g, b, a, mask, deficit=None):
    g.node("attribute", "a_Q", attribute=("string", "Q"))
    g.node("attribute", "a_W", attribute=("string", "vorticity_mag"))
    # opacity field (--vortex-field) and colour field (the other one)
    if a.vortex_field == "Q":
        tq = g.maprange("q_map", ("a_Q", "fac"), a.q_range[0], a.q_range[1])
        tw = g.maprange("q_wmap", ("a_W", "fac"), a.w_range[0], a.w_range[1])
    else:
        tq = g.maprange("q_map", ("a_W", "fac"), a.w_range[0], a.w_range[1])
        tw = g.maprange("q_wmap", ("a_Q", "fac"), a.q_range[0], a.q_range[1])
    alpha = alpha_table([(0.0, 0.0), (0.15, 0.08), (0.5, 0.55), (1.0, 1.0)])
    g.node("rgb_ramp", "q_aramp", ramp=("array_color", b.colors(ramp_table([(0, (1, 1, 1)), (1, (1, 1, 1))]))),
           ramp_alpha=("array_float", b.floats(alpha)))
    g.link(tq[0], tq[1], "q_aramp", "fac")
    col = ramp_table([(0.0, (0.95, 0.30, 0.05)), (0.35, (1.0, 0.55, 0.12)),
                      (0.7, (1.0, 0.82, 0.40)), (1.0, (1.0, 0.97, 0.85))])
    g.node("rgb_ramp", "q_cramp", ramp=("array_color", b.colors(col)),
           ramp_alpha=("array_float", b.floats([1.0] * RAMP)))
    g.link(tw[0], tw[1], "q_cramp", "fac")
    # extra floor fade for Q: the wall turbulence of the floor boundary layer (z < ~5 cm)
    # would otherwise cover the ground with small vortices
    fl = g.maprange("q_floor", ("pos", "z"), a.q_floor[0], a.q_floor[1], "smoothstep")
    m2 = g.math("q_mask", "multiply", mask, fl)
    if deficit is not None:
        # wake gate: keep the vortices that live in (or at the edge of) the turbine wakes
        gate = g.maprange("q_gate", deficit, a.q_gate[0], a.q_gate[1], "smoothstep")
        m2 = g.math("q_mask_g", "multiply", m2, gate)
    am = g.math("q_am", "multiply", ("q_aramp", "alpha"), m2)
    dens = g.math("q_dens", "multiply", am, a.q_density)
    emis = g.math("q_emis", "multiply", am, a.q_emission)
    g.node("principled_volume", "q_pv", color=a.q_albedo, anisotropy=0.0)
    g.link("q_cramp", "color", "q_pv", "emission_color")
    g.link(dens[0], dens[1], "q_pv", "density")
    g.link(emis[0], emis[1], "q_pv", "emission_strength")
    return ("q_pv", "volume")


def volume_shader(a, b):
    g = Graph("wf_volume")
    g.node("geometry", "geo")
    g.node("separate_xyz", "pos")
    g.link("geo", "position", "pos", "vector")
    mask = box_mask(g, "pos", 0.012)
    parts = []
    deficit = None
    if a.look in ("wake", "combined") or a.q_gate[1] > a.q_gate[0]:
        deficit = deficit_node(g, "pos")
    if a.look in ("wake", "combined"):
        parts.append(wake_part(g, b, a, deficit, mask))
    if a.look in ("vortex", "combined"):
        parts.append(vortex_part(g, b, a, mask, deficit if a.q_gate[1] > a.q_gate[0] else None))
    if len(parts) == 2:
        g.node("add_closure", "vol_add")
        g.link(parts[0][0], parts[0][1], "vol_add", "closure1")
        g.link(parts[1][0], parts[1][1], "vol_add", "closure2")
        g.link("vol_add", "closure", "output", "volume")
    else:
        g.link(parts[0][0], parts[0][1], "output", "volume")
    grids = {"wake": ["U_mag"], "vortex": ["Q", "vorticity_mag"],
             "combined": ["U_mag", "Q", "vorticity_mag"]}[a.look]
    if deficit is not None and "U_mag" not in grids:
        grids = ["U_mag"] + grids
    return g.xml(), grids


# ------------------------------------------------------------------ static scene parts
def surface_shaders(a):
    t = Graph("turbine_mat")
    t.node("principled_bsdf", "t_bsdf", base_color=[0.86, 0.87, 0.89], roughness=0.32,
           metallic=0.0)
    t.link("t_bsdf", "BSDF", "output", "surface")
    gr = Graph("ground_mat")
    gr.node("texture_coordinate", "g_tc")
    gr.node("checker_texture", "g_chk", color1=a.ground_c1, color2=a.ground_c2, scale=1.0 / 0.15)
    gr.link("g_tc", "object", "g_chk", "vector")
    gr.node("principled_bsdf", "g_bsdf", roughness=a.ground_roughness)
    gr.link("g_chk", "color", "g_bsdf", "base_color")
    gr.link("g_bsdf", "BSDF", "output", "surface")
    return t.xml() + gr.xml()


def world_shader(a):
    g = Graph("default_background")
    g.node("texture_coordinate", "bg_tc")
    g.node("separate_xyz", "bg_sep")
    g.link("bg_tc", "generated", "bg_sep", "vector")
    t = g.maprange("bg_mr", ("bg_sep", "z"), -0.02, a.sky_height, "smoothstep")
    g.node("mix_color", "bg_grad", a=a.sky_horizon, b=a.sky_zenith)
    g.link(t[0], t[1], "bg_grad", "fac")
    g.node("background_shader", "bg_cam", strength=a.sky_strength)
    g.node("background_shader", "bg_lit", strength=a.ambient)
    g.link("bg_grad", "result", "bg_cam", "color")
    g.link("bg_grad", "result", "bg_lit", "color")
    g.node("light_path", "bg_lp")
    g.node("mix_closure", "bg_mix")
    g.link("bg_lp", "is_camera_ray", "bg_mix", "fac")
    g.link("bg_lit", "background", "bg_mix", "closure1")
    g.link("bg_cam", "background", "bg_mix", "closure2")
    g.link("bg_mix", "closure", "output", "surface")
    return g.xml()


def rot_x_tfm(angle, t):
    c, s = math.cos(angle), math.sin(angle)
    return [1, 0, 0, t[0], 0, c, -s, t[1], 0, s, c, t[2]]


def camera_at(a, frame, nframes):
    u = 0.0 if nframes <= 1 else frame / (nframes - 1)
    u = 0.5 - 0.5 * math.cos(math.pi * u)        # ease in/out
    pos = lerp(a.cam_pos0, a.cam_pos1, u)
    tgt = lerp(a.cam_tgt0, a.cam_tgt1, u)
    return look_at(pos, tgt)


def scene_xml(a, vdb, frame, nframes, vol_xml, grids, static_xml):
    cam = camera_at(a, frame, nframes)
    attrs = "\n".join(
        f'\t\t<attribute name="{g}" std="ATTR_STD_NONE" type="float" element="ATTR_ELEMENT_VOXEL" '
        f'flags="0" buffer="{vdb}" volume_type="openvdb" />' for g in grids)
    rotors = []
    for i, x0 in enumerate(ROWS_X):
        for j, y0 in enumerate(COLS_Y):
            ang = math.radians(a.rotor_deg_per_frame * frame + 37.0 * (3 * i + j))
            rotors.append(f"""	<object name="rotor_{i}_{j}">
		<socket name="geometry" value="rotor_mesh" type_name="node" />
		<socket name="tfm" value="{fmt(rot_x_tfm(ang, [x0, y0, HUB_Z]))}" type_name="transform" />
	</object>""")
    sd = norm(a.sun_dir)
    up = [0, 0, 1] if abs(sd[2]) < 0.95 else [1, 0, 0]
    sx = norm(cross(up, sd))
    sy = cross(sd, sx)
    sun_tfm = [sx[0], sy[0], sd[0], 0, sx[1], sy[1], sd[1], 0, sx[2], sy[2], sd[2], 0]
    denoise = ""
    if a.denoise:
        denoise = """
		<socket name="use_denoise" value="true" type_name="boolean" />
		<socket name="denoiser_type" value="openimagedenoise" type_name="enum" />
		<socket name="denoise_use_gpu" value="false" type_name="boolean" />
		<socket name="denoiser_prefilter" value="accurate" type_name="enum" />
		<socket name="denoiser_quality" value="high" type_name="enum" />"""
    return f"""<?xml version="1.0"?>
<!-- make_windfarm_scene.py look={a.look} frame={frame}/{nframes} vdb={vdb} -->
<cycles>
	<shader name="default_surface" />
	<shader name="default_volume" />
	<shader name="default_light" />
	<shader name="default_empty" />
{world_shader(a)}{surface_shaders(a)}{vol_xml}
	<shader name="sun_shader">
		<emission name="sun_em">
			<socket name="color" value="{fmt(a.sun_color + [0])}" type_name="color" />
			<socket name="strength" value="1" type_name="float" />
		</emission>
		<connect from_node="sun_em" from_socket="emission" to_node="output" to_socket="surface" />
	</shader>

	<camera name="camera">
		<socket name="matrix" value="{fmt(cam)}" type_name="transform" />
		<socket name="fov" value="{math.radians(a.fov):.7g}" type_name="float" />
		<socket name="nearclip" value="0.01" type_name="float" />
		<socket name="farclip" value="200" type_name="float" />
	</camera>
	<film name="film">
		<socket name="filter_type" value="blackman_harris" type_name="enum" />
		<socket name="filter_width" value="1.5" type_name="float" />
		<socket name="exposure" value="{a.exposure}" type_name="float" />
	</film>
	<background name="background">
		<socket name="visibility" value="157" type_name="uint" />
	</background>
	<integrator name="integrator">
		<socket name="max_bounce" value="4" type_name="int" />
		<socket name="max_diffuse_bounce" value="2" type_name="int" />
		<socket name="max_glossy_bounce" value="2" type_name="int" />
		<socket name="max_volume_bounce" value="{a.volume_bounces}" type_name="int" />
		<socket name="transparent_max_bounce" value="8" type_name="int" />
		<socket name="volume_ray_marching" value="{'true' if a.ray_marching else 'false'}" type_name="boolean" />
		<socket name="volume_max_steps" value="{a.max_steps}" type_name="int" />
		<socket name="use_adaptive_sampling" value="false" type_name="boolean" />{denoise}
	</integrator>

	<volume name="wf_vdb" geometry_type="2">
		<socket name="used_shaders" value="wf_volume" type_name="array_node" />
		<socket name="object_space" value="true" type_name="boolean" />
		<socket name="step_size" value="{a.step_size}" type_name="float" />
{attrs}
	</volume>
	<object name="wf_vdb_object">
		<socket name="geometry" value="wf_vdb" type_name="node" />
		<socket name="tfm" value="1 0 0 0 0 1 0 0 0 0 1 0" type_name="transform" />
	</object>
{static_xml}
{chr(10).join(rotors)}

	<sunlight name="sun" geometry_type="8">
		<socket name="used_shaders" value="sun_shader" type_name="array_node" />
		<socket name="light_type" value="sun" type_name="enum" />
		<socket name="strength" value="{a.sun_strength} {a.sun_strength} {a.sun_strength} 0" type_name="color" />
		<socket name="angle" value="{math.radians(a.sun_angle):.6g}" type_name="float" />
		<socket name="use_mis" value="true" type_name="boolean" />
	</sunlight>
	<object name="sun_object">
		<socket name="geometry" value="sun" type_name="node" />
		<socket name="tfm" value="{fmt(sun_tfm)}" type_name="transform" />
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


LOOK_DEFAULTS = {
    "wake":     dict(wake_density=14.0, wake_emission=0.06),
    "vortex":   dict(q_density=6.0, q_emission=6.0),
    "combined": dict(wake_density=10.0, wake_emission=0.05, q_density=4.0, q_emission=5.0),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--look", choices=["wake", "vortex", "combined"], default="combined")
    ap.add_argument("--outdir", help="per-frame scene directory")
    ap.add_argument("--template", help="write one scene with {VDB_DATA} placeholder to this path")
    ap.add_argument("--vdb", nargs="*", default=[])
    ap.add_argument("--nframes", type=int, default=0, help="frames of the camera path (default: #vdb)")
    ap.add_argument("--frame-from-name", action="store_true",
                    help="frame = (time index in the file name - --first) / --step")
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--step", type=int, default=5)
    # transfer functions
    ap.add_argument("--def-range", type=float, nargs=2, default=[0.05, 0.55])
    ap.add_argument("--q-range", type=float, nargs=2, default=[200.0, 3000.0])
    ap.add_argument("--w-range", type=float, nargs=2, default=[20.0, 120.0])
    ap.add_argument("--vortex-field", choices=["Q", "vorticity"], default="Q",
                    help="field that drives the vortex opacity (the other one colours it)")
    ap.add_argument("--q-gate", type=float, nargs=2, default=[0.0, 0.0],
                    help="vortex opacity x smoothstep(deficit, g0, g1); g1 <= g0 disables")
    ap.add_argument("--q-albedo", type=float, nargs=3, default=[0.9, 0.75, 0.6],
                    help="scattering colour of the vortex volume")
    ap.add_argument("--wake-density", type=float)
    ap.add_argument("--wake-emission", type=float)
    ap.add_argument("--wake-ramp", choices=sorted(WAKE_RAMPS), default="blue", help="albedo ramp")
    ap.add_argument("--wake-emit-ramp", choices=sorted(WAKE_RAMPS), default="ice", help="emission colour ramp")
    ap.add_argument("--wake-alpha", choices=["soft", "crisp", "core"], default="soft")
    ap.add_argument("--wake-anisotropy", type=float, default=0.35)
    ap.add_argument("--q-density", type=float)
    ap.add_argument("--q-emission", type=float)
    # camera: slow dolly between two key positions (metres)
    ap.add_argument("--cam-pos0", type=float, nargs=3, default=[1.25, -1.55, 1.05])
    ap.add_argument("--cam-pos1", type=float, nargs=3, default=[3.6, -1.45, 0.95])
    ap.add_argument("--cam-tgt0", type=float, nargs=3, default=[5.6, 0.95, 0.0])
    ap.add_argument("--cam-tgt1", type=float, nargs=3, default=[7.4, 0.95, 0.0])
    ap.add_argument("--fov", type=float, default=34.0, help="vertical FOV (deg)")
    ap.add_argument("--rotor-deg-per-frame", type=float, default=11.0,
                    help="visual rotor rotation per frame (physical 1070 rpm = 64 deg per 0.01 s would strobe)")
    # lighting / look
    ap.add_argument("--sun-dir", type=float, nargs=3, default=[-0.55, 0.62, 0.56])
    ap.add_argument("--sun-strength", type=float, default=3.2)
    ap.add_argument("--sun-angle", type=float, default=3.0)
    ap.add_argument("--sun-color", type=float, nargs=3, default=[1.0, 0.90, 0.76])
    ap.add_argument("--sky-horizon", type=float, nargs=3, default=[0.78, 0.86, 0.95])
    ap.add_argument("--sky-zenith", type=float, nargs=3, default=[0.18, 0.36, 0.72])
    ap.add_argument("--sky-height", type=float, default=0.55, help="sin(elevation) of the zenith colour")
    ap.add_argument("--sky-strength", type=float, default=1.0)
    ap.add_argument("--ambient", type=float, default=0.55)
    ap.add_argument("--ground-c1", type=float, nargs=3, default=[0.16, 0.17, 0.18])
    ap.add_argument("--ground-c2", type=float, nargs=3, default=[0.19, 0.20, 0.21])
    ap.add_argument("--ground-roughness", type=float, default=0.55)
    ap.add_argument("--q-floor", type=float, nargs=2, default=[0.03, 0.06],
                    help="Q volume fades in between these heights (m)")
    ap.add_argument("--top-fade", type=float, default=0.05, help="fade below the box top (m)")
    ap.add_argument("--exposure", type=float, default=1.0)
    ap.add_argument("--volume-bounces", type=int, default=1)
    ap.add_argument("--ray-marching", type=int, default=1)
    ap.add_argument("--max-steps", type=int, default=1024)
    ap.add_argument("--step-size", type=float, default=0.0, help="volume step size (0 = auto from voxels)")
    ap.add_argument("--denoise", type=int, default=1)
    a = ap.parse_args()
    for k, v in LOOK_DEFAULTS[a.look].items():
        if getattr(a, k, None) is None:
            setattr(a, k, v)
    for k in ("wake_density", "wake_emission", "q_density", "q_emission"):
        if getattr(a, k) is None:
            setattr(a, k, 0.0)

    global TOP_FADE
    TOP_FADE = a.top_fade
    b = Bin()
    vol_xml, grids = volume_shader(a, b)
    static_xml = (mesh_xml("static_mesh", build_static(), "turbine_mat", b)
                  + mesh_xml("rotor_mesh", build_rotor(), "turbine_mat", b)
                  + mesh_xml("ground_mesh", build_ground(), "ground_mat", b)
                  + """	<object name="static_object">
		<socket name="geometry" value="static_mesh" type_name="node" />
	</object>
	<object name="ground_object">
		<socket name="geometry" value="ground_mesh" type_name="node" />
	</object>
""")

    if a.template:
        n = max(1, a.nframes)
        with open(a.template, "w") as f:
            f.write(scene_xml(a, "{VDB_DATA}", 0, n, vol_xml, grids, static_xml))
        with open(a.template + ".bin", "wb") as f:
            f.write(b.d)
        print("wrote", a.template)
    if a.outdir:
        os.makedirs(a.outdir, exist_ok=True)
        common = os.path.join(a.outdir, "common.bin")
        with open(common, "wb") as f:
            f.write(b.d)
        n = a.nframes or len(a.vdb)
        for i, v in enumerate(a.vdb):
            fr = i
            if a.frame_from_name:
                idx = int(re.findall(r"(\d+)\.vdb$", v)[0])
                fr = (idx - a.first) // a.step
            name = os.path.splitext(os.path.basename(v))[0]
            x = os.path.join(a.outdir, name + ".xml")
            with open(x, "w") as f:
                f.write(scene_xml(a, os.path.abspath(v), fr, n, vol_xml, grids, static_xml))
            lb = x + ".bin"
            if not os.path.lexists(lb):
                os.symlink("common.bin", lb)
        print("wrote %d scenes to %s" % (len(a.vdb), a.outdir))


if __name__ == "__main__":
    main()
