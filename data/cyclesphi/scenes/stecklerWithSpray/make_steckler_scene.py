#!/usr/bin/env python3
"""
CyclesPhi scene generator for the Steckler room fire (OpenFOAM fireFoam
combustion/fireFoam/RAS/stecklerWithSpray, mesioVDB grids T, CH4, U_mag in one .vdb per frame).

World units are metres (the VDB is in metres, object transform = identity, y up).
Geometry of the case: room x -1.4..1.4, y 0..2.13, z -1.4..1.4; doorway in the wall x = 1.4
(z -0.37..0.37, y 0..1.83); exterior region x 1.4..4.2, y 0..4.6 in front of the facade.

Volume shader (one principled_volume, two grids):
  smoke   s = clamp((CH4 - c0) / (c1 - c0))^gamma          (CH4 = passive fire-gas tracer)
          density   = D_smoke * s
          colour    = grey albedo, warmed slightly by temperature (ramp over T)
          absorption colour dark, anisotropy g (forward scattering)
  flame   h = clamp((T - Tf0) / (Tf1 - Tf0))
          emission colour    = blackbody( Tbb0 + (Tbb1 - Tbb0) * h )   [artistic temperature]
          emission strength  = E_flame * h^p   +   E_glow * clamp((T - Tg0)/(Tg1 - Tg0))^2 * s
                               (the second term: faint ember glow of the hot smoke layer)
Surfaces: floor / ground, room walls and ceiling, facade with the doorway, burner tray,
          back wall behind the exterior region (all principled_bsdf, diffuse).
Lights:   dim sky-like world (camera sees a dark gradient), one soft cool area/sun fill light,
          the flame itself (volume emission, lights the walls and the smoke via volume bounces).

One shared .xml.bin (ramps + meshes) per output directory, one XML per frame (orbiting camera).

Usage:
  make_steckler_scene.py --outdir DIR --vdb f0.vdb [f1.vdb ...] [--nframes N] [options]
  The frame index used for the camera = position in the --vdb list (or --frame-index).
"""
import argparse
import math
import os
import re
import struct

RAMP = 257


# ------------------------------------------------------------------ small helpers
def sub(a, b): return [a[i] - b[i] for i in range(3)]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a):
    l = math.sqrt(sum(x * x for x in a))
    return [x / l for x in a]


def fmt(v):
    return " ".join("%.7g" % x for x in v)


def look_at(pos, target, up=(0, 1, 0)):
    """Cycles camera matrix (3x4 row-major; columns right, up, forward, position)."""
    f = norm(sub(target, pos))
    r = norm(cross(f, list(up)))
    u = cross(r, f)
    m = []
    for row in range(3):
        m += [r[row], u[row], f[row], pos[row]]
    return m


def parse_pts(spec, ncomp):
    pts = []
    for item in spec.split(";"):
        item = item.strip()
        if item:
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
            f = f * f * (3 - 2 * f)
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

    def packed3(self, pts):  # byte buffer (uint64 byte count) of packed float3 (vertex positions)
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


# ------------------------------------------------------------------ geometry
class MeshBuilder:
    def __init__(self):
        self.verts, self.tris = [], []

    def quad(self, p0, p1, p2, p3):
        i = len(self.verts)
        self.verts.extend([p0, p1, p2, p3])
        self.tris.extend([i, i + 1, i + 2, i, i + 2, i + 3])

    def box(self, x0, x1, y0, y1, z0, z1, skip=()):
        """Axis-aligned box, outward facing quads; skip: faces to omit ('-x','+x',...)."""
        P = lambda x, y, z: [x, y, z]
        if "-x" not in skip: self.quad(P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0))
        if "+x" not in skip: self.quad(P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1))
        if "-y" not in skip: self.quad(P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1))
        if "+y" not in skip: self.quad(P(x0, y1, z0), P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0))
        if "-z" not in skip: self.quad(P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0), P(x1, y0, z0))
        if "+z" not in skip: self.quad(P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1))


def build_meshes(a):
    """Returns {material: MeshBuilder}. Walls are slabs outside the fluid region so that they
    do not hide voxels next to the walls."""
    t = 0.06          # wall thickness (m)
    Lr, Hr = 1.4, 2.13
    door_z, door_h = 0.37, 1.83
    zf = a.cut_z      # cut-away: walls end at z = cut_z (viewer side open)
    M = {"mat_wall": MeshBuilder(), "mat_floor": MeshBuilder(), "mat_ground": MeshBuilder(),
         "mat_burner": MeshBuilder(), "mat_backdrop": MeshBuilder()}
    w, f, g, b, bd = (M["mat_wall"], M["mat_floor"], M["mat_ground"], M["mat_burner"], M["mat_backdrop"])
    # room floor (slab under y = 0) and exterior ground (large)
    f.box(-Lr - t, Lr, -0.05, 0.0, -Lr - t, zf)
    g.box(-30.0, 30.0, -0.06, -0.001, -30.0, 30.0)
    # room walls: back (z = -1.4), left (x = -1.4), ceiling (y = 2.13)
    w.box(-Lr - t, Lr + t, 0.0, Hr + t, -Lr - t, -Lr)
    w.box(-Lr - t, -Lr, 0.0, Hr + t, -Lr - t, zf)
    if a.ceiling:
        w.box(-Lr - t, Lr + t, Hr, Hr + t, -Lr - t, zf)
    # facade x = 1.4 (thin slab centred on the baffle), doorway z -0.37..0.37, y 0..1.83
    hx = 0.012
    ytop = a.facade_top
    w.box(Lr - hx, Lr + hx, 0.0, ytop, -Lr - t, -door_z)
    w.box(Lr - hx, Lr + hx, 0.0, ytop, door_z, zf)
    w.box(Lr - hx, Lr + hx, door_h, ytop, -door_z, door_z)
    # burner tray (0.3 x 0.3 m) at the floor centre
    b.box(-0.16, 0.16, 0.0, 0.035, -0.16, 0.16)
    # back wall behind the exterior region (slip wall z = -1.4 of the domain), as a backdrop
    if a.backdrop:
        bd.box(Lr + hx, a.backdrop_x1, 0.0, a.backdrop_top, -Lr - t, -Lr)
    return M


# ------------------------------------------------------------------ ramps
# Smoke albedo over normalised temperature (cool grey -> warm brownish grey). Linear RGB.
SMOKE_COLORS = "0:0.20,0.205,0.215;0.5:0.22,0.19,0.165;1:0.26,0.17,0.10"


def scene_xml(a, o, vdb, cam):
    grids = ["T", "CH4"]
    interp = {"linear": "", "cubic": ' interpolation="INTERPOLATION_CUBIC"'}[a.interpolation]
    attrs = "\n".join(
        f'\t\t<attribute name="{g}" std="ATTR_STD_NONE" type="float" element="ATTR_ELEMENT_VOXEL" '
        f'flags="0" buffer="{vdb}" volume_type="openvdb"{interp} />' for g in grids)
    fov = math.radians(a.fov)
    denoise = ""
    if a.denoise:
        denoise = """
		<socket name="use_denoise" value="true" type_name="boolean" />
		<socket name="denoiser_type" value="openimagedenoise" type_name="enum" />
		<socket name="denoise_use_gpu" value="false" type_name="boolean" />
		<socket name="denoiser_prefilter" value="accurate" type_name="enum" />
		<socket name="denoiser_quality" value="high" type_name="enum" />"""

    def mat(name, color, rough=0.85):
        return f"""
	<shader name="{name}">
		<principled_bsdf name="bsdf">
			<socket name="base_color" value="{fmt(list(color) + [0])}" type_name="color" />
			<socket name="roughness" value="{rough}" type_name="float" />
		</principled_bsdf>
		<connect from_node="bsdf" from_socket="BSDF" to_node="output" to_socket="surface" />
	</shader>"""

    mats = (mat("mat_wall", a.wall_color) + mat("mat_floor", a.floor_color, 0.7) +
            mat("mat_ground", a.ground_color, 0.9) + mat("mat_burner", [0.03, 0.03, 0.03], 0.4) +
            mat("mat_backdrop", a.backdrop_color))
    meshes = ""
    for name, (off_p, off_t, off_s, off_sm, nv) in o["meshes"].items():
        meshes += f"""
	<mesh name="{name}_mesh" geometry_type="0">
		<socket name="used_shaders" value="{name}" type_name="array_node" />
		<socket name="triangles" value="{off_t}" type_name="array_int" />
		<socket name="shader" value="{off_s}" type_name="array_int" />
		<socket name="smooth" value="{off_sm}" type_name="array_boolean" />
		<attribute name="P" std="ATTR_STD_POSITION" type="point" element="ATTR_ELEMENT_VERTEX" flags="0" size="{nv}" buffer="{off_p}" />
	</mesh>
	<object name="{name}_object">
		<socket name="geometry" value="{name}_mesh" type_name="node" />
		<socket name="tfm" value="1 0 0 0 0 1 0 0 0 0 1 0" type_name="transform" />
	</object>"""

    # fill light: area light (disk) placed at fill_pos, pointing at fill_target
    fp, ft = a.fill_pos, a.fill_target
    fd = norm(sub(ft, fp))
    upv = [0, 1, 0] if abs(fd[1]) < 0.95 else [1, 0, 0]
    fx = norm(cross(upv, fd)); fy = cross(fd, fx)
    # Cycles area light emits along its local -Z axis
    fill_tfm = [fx[0], fy[0], -fd[0], fp[0], fx[1], fy[1], -fd[1], fp[1], fx[2], fy[2], -fd[2], fp[2]]
    fill = ""
    if a.fill_strength > 0:
        fill = f"""
	<shader name="fill_shader">
		<emission name="em">
			<socket name="color" value="{fmt(a.fill_color + [0])}" type_name="color" />
			<socket name="strength" value="1" type_name="float" />
		</emission>
		<connect from_node="em" from_socket="emission" to_node="output" to_socket="surface" />
	</shader>
	<arealight name="fill_light" geometry_type="4">
		<socket name="used_shaders" value="fill_shader" type_name="array_node" />
		<socket name="light_type" value="area" type_name="enum" />
		<socket name="strength" value="{a.fill_strength} {a.fill_strength} {a.fill_strength} 0" type_name="color" />
		<socket name="sizeu" value="{a.fill_size}" type_name="float" />
		<socket name="sizev" value="{a.fill_size}" type_name="float" />
		<socket name="ellipse" value="true" type_name="boolean" />
		<socket name="use_mis" value="true" type_name="boolean" />
	</arealight>
	<object name="fill_object">
		<socket name="geometry" value="fill_light" type_name="node" />
		<socket name="tfm" value="{fmt(fill_tfm)}" type_name="transform" />
	</object>"""

    return f"""<?xml version="1.0"?>
<!-- Steckler room fire (fireFoam stecklerWithSpray), data/cyclesphi/scenes/stecklerWithSpray/make_steckler_scene.py
     grids T (flame + hot smoke glow) and CH4 (smoke density); world units = metres -->
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
			<socket name="from_min" value="-0.1" type_name="float" />
			<socket name="from_max" value="0.6" type_name="float" />
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
{mats}

	<!-- Fire volume: smoke from CH4, flame + ember glow from T -->
	<shader name="fire_shader">
		<attribute name="a_T"><socket name="attribute" value="T" type_name="string" /></attribute>
		<attribute name="a_S"><socket name="attribute" value="CH4" type_name="string" /></attribute>
		<!-- smoke density -->
		<map_range name="s_range">
			<socket name="from_min" value="{a.smoke_range[0]}" type_name="float" />
			<socket name="from_max" value="{a.smoke_range[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<math name="s_pow"><socket name="math_type" value="power" type_name="enum" />
			<socket name="value2" value="{a.smoke_gamma}" type_name="float" /></math>
		<math name="s_dens"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.smoke_density}" type_name="float" /></math>
		<!-- fade the smoke out towards the open outlet boundaries (top y = 4.6, side x = 4.2) -->
		<geometry name="geo" />
		<separate_xyz name="geo_xyz" />
		<map_range name="fade_y">
			<socket name="from_min" value="{a.fade_y[1]}" type_name="float" />
			<socket name="from_max" value="{a.fade_y[0]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<map_range name="fade_x">
			<socket name="from_min" value="{a.fade_x[1]}" type_name="float" />
			<socket name="from_max" value="{a.fade_x[0]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<math name="fade"><socket name="math_type" value="multiply" type_name="enum" /></math>
		<math name="s_densf"><socket name="math_type" value="multiply" type_name="enum" /></math>
		<!-- smoke colour warmed by temperature -->
		<map_range name="c_range">
			<socket name="from_min" value="{a.smoke_tcolor[0]}" type_name="float" />
			<socket name="from_max" value="{a.smoke_tcolor[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<rgb_ramp name="c_ramp">
			<socket name="ramp" value="{o['smoke_c']}" type_name="array_color" />
			<socket name="ramp_alpha" value="{o['ones']}" type_name="array_float" />
		</rgb_ramp>
		<!-- flame: heat fraction h, blackbody colour of an artistic temperature -->
		<map_range name="f_range">
			<socket name="from_min" value="{a.flame_range[0]}" type_name="float" />
			<socket name="from_max" value="{a.flame_range[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<map_range name="bb_range">
			<socket name="from_min" value="{a.flame_range[0]}" type_name="float" />
			<socket name="from_max" value="{a.flame_range[1]}" type_name="float" />
			<socket name="to_min" value="{a.bb_range[0]}" type_name="float" />
			<socket name="to_max" value="{a.bb_range[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<blackbody name="bb" />
		<math name="f_pow"><socket name="math_type" value="power" type_name="enum" />
			<socket name="value2" value="{a.flame_gamma}" type_name="float" /></math>
		<math name="f_em"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.flame_emission}" type_name="float" /></math>
		<!-- ember glow of hot smoke: E_glow * g^2 * s -->
		<map_range name="g_range">
			<socket name="from_min" value="{a.glow_range[0]}" type_name="float" />
			<socket name="from_max" value="{a.glow_range[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<math name="g_sq"><socket name="math_type" value="power" type_name="enum" />
			<socket name="value2" value="2" type_name="float" /></math>
		<math name="g_s"><socket name="math_type" value="multiply" type_name="enum" /></math>
		<math name="g_em"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.glow_emission}" type_name="float" /></math>
		<math name="em_sum"><socket name="math_type" value="add" type_name="enum" /></math>
		<principled_volume name="pv">
			<socket name="anisotropy" value="{a.smoke_aniso}" type_name="float" />
			<socket name="absorption_color" value="{fmt(a.smoke_absorption + [0])}" type_name="color" />
		</principled_volume>
		<connect from_node="a_S" from_socket="fac" to_node="s_range" to_socket="value" />
		<connect from_node="s_range" from_socket="result" to_node="s_pow" to_socket="value1" />
		<connect from_node="s_pow" from_socket="value" to_node="s_dens" to_socket="value1" />
		<connect from_node="geo" from_socket="position" to_node="geo_xyz" to_socket="vector" />
		<connect from_node="geo_xyz" from_socket="y" to_node="fade_y" to_socket="value" />
		<connect from_node="geo_xyz" from_socket="x" to_node="fade_x" to_socket="value" />
		<connect from_node="fade_y" from_socket="result" to_node="fade" to_socket="value1" />
		<connect from_node="fade_x" from_socket="result" to_node="fade" to_socket="value2" />
		<connect from_node="s_dens" from_socket="value" to_node="s_densf" to_socket="value1" />
		<connect from_node="fade" from_socket="value" to_node="s_densf" to_socket="value2" />
		<connect from_node="s_densf" from_socket="value" to_node="pv" to_socket="density" />
		<connect from_node="a_T" from_socket="fac" to_node="c_range" to_socket="value" />
		<connect from_node="c_range" from_socket="result" to_node="c_ramp" to_socket="fac" />
		<connect from_node="c_ramp" from_socket="color" to_node="pv" to_socket="color" />
		<connect from_node="a_T" from_socket="fac" to_node="f_range" to_socket="value" />
		<connect from_node="a_T" from_socket="fac" to_node="bb_range" to_socket="value" />
		<connect from_node="bb_range" from_socket="result" to_node="bb" to_socket="temperature" />
		<connect from_node="bb" from_socket="color" to_node="pv" to_socket="emission_color" />
		<connect from_node="f_range" from_socket="result" to_node="f_pow" to_socket="value1" />
		<connect from_node="f_pow" from_socket="value" to_node="f_em" to_socket="value1" />
		<connect from_node="a_T" from_socket="fac" to_node="g_range" to_socket="value" />
		<connect from_node="g_range" from_socket="result" to_node="g_sq" to_socket="value1" />
		<connect from_node="g_sq" from_socket="value" to_node="g_s" to_socket="value1" />
		<connect from_node="s_pow" from_socket="value" to_node="g_s" to_socket="value2" />
		<connect from_node="g_s" from_socket="value" to_node="g_em" to_socket="value1" />
		<connect from_node="f_em" from_socket="value" to_node="em_sum" to_socket="value1" />
		<connect from_node="g_em" from_socket="value" to_node="em_sum" to_socket="value2" />
		<connect from_node="em_sum" from_socket="value" to_node="pv" to_socket="emission_strength" />
		<connect from_node="pv" from_socket="volume" to_node="output" to_socket="volume" />
	</shader>
{fill}
{meshes}

	<camera name="camera">
		<socket name="matrix" value="{fmt(cam)}" type_name="transform" />
		<socket name="fov" value="{fov:.7g}" type_name="float" />
		<socket name="nearclip" value="0.05" type_name="float" />
		<socket name="farclip" value="500" type_name="float" />
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
		<socket name="max_diffuse_bounce" value="{a.max_bounce}" type_name="int" />
		<socket name="max_volume_bounce" value="{a.volume_bounces}" type_name="int" />
		<socket name="transparent_max_bounce" value="8" type_name="int" />
		<socket name="volume_ray_marching" value="true" type_name="boolean" />
		<socket name="volume_max_steps" value="{a.max_steps}" type_name="int" />
		<socket name="use_adaptive_sampling" value="false" type_name="boolean" />{denoise}
	</integrator>

	<volume name="fire_volume" geometry_type="2">
		<socket name="used_shaders" value="fire_shader" type_name="array_node" />
		<socket name="object_space" value="true" type_name="boolean" />
		<socket name="step_size" value="{a.step_size}" type_name="float" />
{attrs}
	</volume>
	<object name="fire_object">
		<socket name="geometry" value="fire_volume" type_name="node" />
		<socket name="tfm" value="1 0 0 0 0 1 0 0 0 0 1 0" type_name="transform" />
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


def camera_for(a, t):
    """t in [0,1] over the sequence: eased orbit around the target (azimuth about +y,
    0 = looking from +z towards -z, positive = camera moves towards +x)."""
    e = 0.5 - 0.5 * math.cos(math.pi * t)
    az = a.az0 + (a.az1 - a.az0) * e
    el = a.el0 + (a.el1 - a.el0) * e
    dist = a.dist0 + (a.dist1 - a.dist0) * e
    tgt = [a.target0[i] + (a.target1[i] - a.target0[i]) * e for i in range(3)]
    azr, elr = math.radians(az), math.radians(el)
    d = [math.cos(elr) * math.sin(azr), math.sin(elr), math.cos(elr) * math.cos(azr)]
    pos = [tgt[i] + dist * d[i] for i in range(3)]
    return look_at(pos, tgt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--vdb", nargs="+", required=True)
    ap.add_argument("--nframes", type=int, default=0, help="frames of the orbit (default: number of files)")
    ap.add_argument("--frame-from-name", action="store_true",
                    help="camera frame index = trailing number of the file name (steckler_NNNN.vdb)")
    ap.add_argument("--name", default="", help="XML base name (default: VDB base name)")
    # camera (metres / degrees)
    ap.add_argument("--target0", type=float, nargs=3, default=[1.2, 1.55, -0.2])
    ap.add_argument("--target1", type=float, nargs=3, default=None)
    ap.add_argument("--az0", type=float, default=-16.0)
    ap.add_argument("--az1", type=float, default=None)
    ap.add_argument("--el0", type=float, default=4.0)
    ap.add_argument("--el1", type=float, default=None)
    ap.add_argument("--dist0", type=float, default=8.6)
    ap.add_argument("--dist1", type=float, default=None)
    ap.add_argument("--fov", type=float, default=33.0, help="degrees (shorter image side)")
    # smoke
    ap.add_argument("--smoke-range", type=float, nargs=2, default=[2e-4, 0.02])
    ap.add_argument("--smoke-gamma", type=float, default=0.6)
    ap.add_argument("--smoke-density", type=float, default=6.0, help="1/m at s = 1")
    ap.add_argument("--smoke-aniso", type=float, default=0.35)
    ap.add_argument("--smoke-absorption", type=float, nargs=3, default=[0.05, 0.05, 0.05])
    ap.add_argument("--smoke-tcolor", type=float, nargs=2, default=[300.0, 600.0])
    ap.add_argument("--smoke-colors", default=SMOKE_COLORS)
    # flame
    ap.add_argument("--flame-range", type=float, nargs=2, default=[420.0, 1000.0])
    ap.add_argument("--bb-range", type=float, nargs=2, default=[900.0, 2300.0])
    ap.add_argument("--flame-gamma", type=float, default=2.0)
    ap.add_argument("--flame-emission", type=float, default=60.0)
    ap.add_argument("--fade-y", type=float, nargs=2, default=[3.7, 4.55], help="smoke fades out between these heights")
    ap.add_argument("--fade-x", type=float, nargs=2, default=[3.5, 4.15], help="smoke fades out between these x")
    ap.add_argument("--glow-range", type=float, nargs=2, default=[330.0, 600.0])
    ap.add_argument("--glow-emission", type=float, default=0.6)
    # environment
    ap.add_argument("--ceiling", type=int, default=1)
    ap.add_argument("--cut-z", type=float, default=1.4)
    ap.add_argument("--facade-top", type=float, default=4.6)
    ap.add_argument("--backdrop", type=int, default=1)
    ap.add_argument("--backdrop-x1", type=float, default=7.0)
    ap.add_argument("--backdrop-top", type=float, default=6.0)
    ap.add_argument("--wall-color", type=float, nargs=3, default=[0.55, 0.53, 0.50])
    ap.add_argument("--floor-color", type=float, nargs=3, default=[0.30, 0.24, 0.19])
    ap.add_argument("--ground-color", type=float, nargs=3, default=[0.10, 0.10, 0.11])
    ap.add_argument("--backdrop-color", type=float, nargs=3, default=[0.22, 0.23, 0.26])
    ap.add_argument("--ambient", type=float, nargs=3, default=[0.010, 0.012, 0.018])
    ap.add_argument("--bg-top", type=float, nargs=3, default=[0.010, 0.013, 0.022])
    ap.add_argument("--bg-bottom", type=float, nargs=3, default=[0.002, 0.002, 0.003])
    ap.add_argument("--fill-strength", type=float, default=300.0)
    ap.add_argument("--fill-size", type=float, default=3.0)
    ap.add_argument("--fill-pos", type=float, nargs=3, default=[-4.0, 5.0, 7.0])
    ap.add_argument("--fill-target", type=float, nargs=3, default=[0.5, 1.2, -0.5])
    ap.add_argument("--fill-color", type=float, nargs=3, default=[0.75, 0.85, 1.0])
    ap.add_argument("--exposure", type=float, default=1.0)
    # integrator
    ap.add_argument("--volume-bounces", type=int, default=1)
    ap.add_argument("--max-bounce", type=int, default=3)
    ap.add_argument("--max-steps", type=int, default=1024)
    ap.add_argument("--step-size", type=float, default=0.0)
    ap.add_argument("--interpolation", default="linear", choices=["linear", "cubic"])
    ap.add_argument("--denoise", type=int, default=1)
    a = ap.parse_args()
    for k in ("target", "az", "el", "dist"):
        if getattr(a, k + "1") is None:
            setattr(a, k + "1", getattr(a, k + "0"))

    os.makedirs(a.outdir, exist_ok=True)
    binw = Bin()
    o = {"smoke_c": binw.colors(table(a.smoke_colors, 3)), "ones": binw.floats([1.0] * RAMP), "meshes": {}}
    for name, mb in build_meshes(a).items():
        if not mb.tris:
            continue
        ntri = len(mb.tris) // 3
        o["meshes"][name] = (binw.packed3(mb.verts), binw.ints(mb.tris), binw.ints([0] * ntri),
                             binw.bools([False] * ntri), len(mb.verts))
    binpath = os.path.join(a.outdir, "scene_shared.xml.bin")
    with open(binpath, "wb") as f:
        f.write(binw.data)
    n = a.nframes if a.nframes > 0 else len(a.vdb)
    for i, vdb in enumerate(a.vdb):
        idx = i
        if a.frame_from_name:
            idx = int(re.findall(r"(\d+)", os.path.basename(vdb))[-1])
        t = 0.0 if n <= 1 else min(1.0, idx / (n - 1))
        base = a.name or os.path.splitext(os.path.basename(vdb))[0]
        xml = os.path.join(a.outdir, base + ".xml")
        with open(xml, "w") as f:
            f.write(scene_xml(a, o, os.path.abspath(vdb) if not vdb.startswith("{") else vdb, camera_for(a, t)))
        lnk = xml + ".bin"
        if os.path.lexists(lnk):
            os.remove(lnk)
        os.symlink("scene_shared.xml.bin", lnk)
    print("wrote %d scene(s) + %s" % (len(a.vdb), binpath))


if __name__ == "__main__":
    main()
