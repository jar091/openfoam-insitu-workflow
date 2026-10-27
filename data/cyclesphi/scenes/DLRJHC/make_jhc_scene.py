#!/usr/bin/env python3
"""
CyclesPhi scene generator for the DLR jet-in-hot-coflow flame (OpenFOAM reactingFoam
combustion/reactingFoam/LES/DLRJHC, mesioVDB grids T, OH, Qdot, CH4 in one .vdb per frame).

The simulation covers one quarter of the burner (symmetry planes x = 0 and y = 0, jet along +z,
nozzle exit region at z = 0..8 mm). The scene instances the same VDB volume four times with
mirror transforms diag(+-1, +-1, 1), so the full round jet flame is shown.
Scene units: data metres x SCALE (default 50: the 120 mm chamber height becomes 6 units).

Volume shader (one principled_volume; all grids in the same file):
  flame   h  = clamp((T - Tf0) / (Tf1 - Tf0))                       (coflow 1490 K -> 0)
          emission colour (part 1) = blackbody(Tbb0 + (Tbb1 - Tbb0) * h)
          emission strength (1)    = E_flame * h^p
  OH      w  = window ramp over clamp((OH - o0) / (o1 - o0))   (peaked: a thin sheath look)
          emission colour (part 2) = blue-violet (OH chemiluminescence-like tint)
          emission strength (2)    = E_oh * w
          (colour = (E1 * c1 + E2 * c2) / (E1 + E2) and strength = E1 + E2, done with
           vector math so both emissions add in one closure)
  fuel    c  = clamp((CH4 - c0) / (c1 - c0))^0.7 * (1 - h)       cold jet core
          density = D_fuel * c (+ D_flame * h for a slight self-shadowing of the flame)
          colour  = pale steel blue scattering, lit by the flame and a weak rim light
Surfaces: fuel nozzle tube (brushed steel) and the coflow base plate (dark ceramic).
Background: near-black vertical gradient, no visible horizon.

Usage:
  make_jhc_scene.py --outdir DIR --vdb f0.vdb [f1.vdb ...] [--nframes N] [options]
"""
import argparse
import math
import os
import re
import struct

RAMP = 257


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def add(a, b): return [a[i] + b[i] for i in range(3)]
def scl(a, s): return [x * s for x in a]
def dot(a, b): return sum(a[i] * b[i] for i in range(3))
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a):
    l = math.sqrt(sum(x * x for x in a))
    return [x / l for x in a]


def fmt(v):
    return " ".join("%.7g" % x for x in v)


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


# ------------------------------------------------------------------ geometry (scene units)
class MeshBuilder:
    def __init__(self):
        self.verts, self.tris, self.smooth = [], [], []

    def tri(self, a, b, c, smooth=False):
        i = len(self.verts)
        self.verts.extend([a, b, c])
        self.tris.extend([i, i + 1, i + 2])
        self.smooth.append(smooth)

    def quad(self, a, b, c, d, smooth=False):
        self.tri(a, b, c, smooth)
        self.tri(a, c, d, smooth)

    def tube(self, r0, r1, z0, z1, n=96, caps=True):
        """Thick-walled tube (inner r0, outer r1) along z."""
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
            # outer (normal outwards)
            self.quad([r1 * c0, r1 * s0, z0], [r1 * c1, r1 * s1, z0], [r1 * c1, r1 * s1, z1], [r1 * c0, r1 * s0, z1], True)
            # inner (normal inwards)
            self.quad([r0 * c0, r0 * s0, z0], [r0 * c0, r0 * s0, z1], [r0 * c1, r0 * s1, z1], [r0 * c1, r0 * s1, z0], True)
            if caps:  # annulus at z1 (top) and z0
                self.quad([r0 * c0, r0 * s0, z1], [r1 * c0, r1 * s0, z1], [r1 * c1, r1 * s1, z1], [r0 * c1, r0 * s1, z1])
                self.quad([r0 * c0, r0 * s0, z0], [r0 * c1, r0 * s1, z0], [r1 * c1, r1 * s1, z0], [r1 * c0, r1 * s0, z0])

    def disc(self, r0, r1, z, n=128):
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
            self.quad([r0 * c0, r0 * s0, z], [r1 * c0, r1 * s0, z], [r1 * c1, r1 * s1, z], [r0 * c1, r0 * s1, z])


def build_meshes(a):
    S = a.scale
    nozzle, plate = MeshBuilder(), MeshBuilder()
    R, Rext = 1.0e-3 * S, 1.5e-3 * S
    nozzle.tube(R, Rext, a.nozzle_z[0] * S, a.nozzle_z[1] * S)
    if a.plate_r <= 0:
        return {"mat_nozzle": nozzle}
    plate.disc(Rext, a.plate_r * S, a.plate_z * S)
    # plate rim (short cylinder below the plate)
    plate.tube(a.plate_r * S - 1e-3, a.plate_r * S, a.plate_z * S - 0.004 * S, a.plate_z * S, caps=False)
    return {"mat_nozzle": nozzle, "mat_plate": plate}


# ------------------------------------------------------------------ ramps
# OH window: transparent in the coflow, strongest at intermediate OH (thin sheath), weaker in
# the fully burnt core.
OH_ALPHA = "0:0;0.08:0;0.3:0.35;0.55:1;0.8:0.7;1:0.45"


def scene_xml(a, o, vdb, cam):
    grids = ["T", "OH", "CH4"]
    attrs = "\n".join(
        f'\t\t<attribute name="{g}" std="ATTR_STD_NONE" type="float" element="ATTR_ELEMENT_VOXEL" '
        f'flags="0" buffer="{vdb}" volume_type="openvdb" />' for g in grids)
    S = a.scale
    objs = ""
    for i, (sx, sy) in enumerate([(1, 1), (-1, 1), (-1, -1), (1, -1)]):
        if i >= a.quadrants:
            break
        # shift every copy towards the axis by mirror_shift (data metres) so that the copies
        # overlap at the symmetry planes (no dark seam from the interpolation towards the
        # background value at the box faces x = 0 and y = 0)
        sh = a.mirror_shift * S
        tfm = [sx * S, 0, 0, -sx * sh, 0, sy * S, 0, -sy * sh, 0, 0, S, 0]
        objs += f"""
	<object name="flame_object_{i}">
		<socket name="geometry" value="flame_volume" type_name="node" />
		<socket name="tfm" value="{fmt(tfm)}" type_name="transform" />
		<socket name="visibility" value="1693" type_name="uint" />
	</object>"""
    fov = math.radians(a.fov)
    denoise = ""
    if a.denoise:
        denoise = """
		<socket name="use_denoise" value="true" type_name="boolean" />
		<socket name="denoiser_type" value="openimagedenoise" type_name="enum" />
		<socket name="denoise_use_gpu" value="false" type_name="boolean" />
		<socket name="denoiser_prefilter" value="accurate" type_name="enum" />
		<socket name="denoiser_quality" value="high" type_name="enum" />"""
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
    # rim light (area light) behind / above the flame
    lp, lt = a.rim_pos, a.rim_target
    fd = norm(sub(lt, lp))
    upv = [0, 0, 1] if abs(fd[2]) < 0.95 else [1, 0, 0]
    fx = norm(cross(upv, fd)); fy = cross(fd, fx)
    rim_tfm = [fx[0], fy[0], -fd[0], lp[0], fx[1], fy[1], -fd[1], lp[1], fx[2], fy[2], -fd[2], lp[2]]
    rim = ""
    if a.rim_strength > 0:
        rim = f"""
	<shader name="rim_shader">
		<emission name="em">
			<socket name="color" value="{fmt(a.rim_color + [0])}" type_name="color" />
			<socket name="strength" value="1" type_name="float" />
		</emission>
		<connect from_node="em" from_socket="emission" to_node="output" to_socket="surface" />
	</shader>
	<arealight name="rim_light" geometry_type="4">
		<socket name="used_shaders" value="rim_shader" type_name="array_node" />
		<socket name="light_type" value="area" type_name="enum" />
		<socket name="strength" value="{a.rim_strength} {a.rim_strength} {a.rim_strength} 0" type_name="color" />
		<socket name="sizeu" value="{a.rim_size}" type_name="float" />
		<socket name="sizev" value="{a.rim_size}" type_name="float" />
		<socket name="ellipse" value="true" type_name="boolean" />
		<socket name="use_mis" value="true" type_name="boolean" />
	</arealight>
	<object name="rim_object">
		<socket name="geometry" value="rim_light" type_name="node" />
		<socket name="tfm" value="{fmt(rim_tfm)}" type_name="transform" />
	</object>"""

    return f"""<?xml version="1.0"?>
<!-- DLR jet-in-hot-coflow flame (reactingFoam DLRJHC), data/cyclesphi/scenes/DLRJHC/make_jhc_scene.py
     grids T (blackbody flame), OH (blue-violet sheath), CH4 (cold fuel core); quarter domain mirrored x4 -->
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
			<socket name="from_min" value="-0.6" type_name="float" />
			<socket name="from_max" value="0.8" type_name="float" />
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
		<connect from_node="bg_sep" from_socket="{a.bg_axis}" to_node="bg_mr" to_socket="value" />
		<connect from_node="bg_mr" from_socket="result" to_node="bg_grad" to_socket="fac" />
		<connect from_node="bg_grad" from_socket="result" to_node="bg_camera" to_socket="color" />
		<connect from_node="bg_lightpath" from_socket="is_camera_ray" to_node="bg_mix" to_socket="fac" />
		<connect from_node="bg_light" from_socket="background" to_node="bg_mix" to_socket="closure1" />
		<connect from_node="bg_camera" from_socket="background" to_node="bg_mix" to_socket="closure2" />
		<connect from_node="bg_mix" from_socket="closure" to_node="output" to_socket="surface" />
	</shader>
	<shader name="default_empty" />

	<shader name="mat_nozzle">
		<principled_bsdf name="bsdf">
			<socket name="base_color" value="0.62 0.62 0.64 0" type_name="color" />
			<socket name="metallic" value="1" type_name="float" />
			<socket name="roughness" value="0.28" type_name="float" />
		</principled_bsdf>
		<connect from_node="bsdf" from_socket="BSDF" to_node="output" to_socket="surface" />
	</shader>
	<shader name="mat_plate">
		<principled_bsdf name="bsdf">
			<socket name="base_color" value="{fmt(a.plate_color + [0])}" type_name="color" />
			<socket name="roughness" value="0.6" type_name="float" />
		</principled_bsdf>
		<connect from_node="bsdf" from_socket="BSDF" to_node="output" to_socket="surface" />
	</shader>

	<!-- Flame volume -->
	<shader name="flame_shader">
		<attribute name="a_T"><socket name="attribute" value="T" type_name="string" /></attribute>
		<attribute name="a_OH"><socket name="attribute" value="OH" type_name="string" /></attribute>
		<attribute name="a_F"><socket name="attribute" value="CH4" type_name="string" /></attribute>
		<!-- T: heat fraction h and blackbody colour -->
		<map_range name="h_range">
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
		<math name="h_pow"><socket name="math_type" value="power" type_name="enum" />
			<socket name="value2" value="{a.flame_gamma}" type_name="float" /></math>
		<math name="e1"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.flame_emission}" type_name="float" /></math>
		<!-- OH sheath -->
		<map_range name="oh_range">
			<socket name="from_min" value="{a.oh_range[0]}" type_name="float" />
			<socket name="from_max" value="{a.oh_range[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<rgb_ramp name="oh_ramp">
			<socket name="ramp" value="{o['oh_c']}" type_name="array_color" />
			<socket name="ramp_alpha" value="{o['oh_a']}" type_name="array_float" />
		</rgb_ramp>
		<math name="e2"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.oh_emission}" type_name="float" /></math>
		<!-- OH sheath weight: oh_alpha * (1 - oh_edge * h): OH shows at the flame edges and tip,
		     not under the hot blackbody core -->
		<math name="edge_k"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.oh_edge}" type_name="float" /></math>
		<math name="edge_w"><socket name="math_type" value="subtract" type_name="enum" />
			<socket name="value1" value="1" type_name="float" /></math>
		<math name="edge_c"><socket name="math_type" value="maximum" type_name="enum" />
			<socket name="value2" value="0" type_name="float" /></math>
		<math name="oh_w"><socket name="math_type" value="multiply" type_name="enum" /></math>
		<!-- emission = e1 * bb + e2 * oh_colour ; strength 1 -->
		<vector_math name="c1"><socket name="math_type" value="scale" type_name="enum" /></vector_math>
		<vector_math name="c2"><socket name="math_type" value="scale" type_name="enum" /></vector_math>
		<vector_math name="csum"><socket name="math_type" value="add" type_name="enum" /></vector_math>
		<!-- faint cold-jet glow: fuel_emission * c * fuel_glow_color (shows the jet core waves) -->
		<math name="e3"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.fuel_emission}" type_name="float" /></math>
		<vector_math name="c3"><socket name="math_type" value="scale" type_name="enum" />
			<socket name="vector1" value="{fmt(a.fuel_glow_color + [0])}" type_name="vector" /></vector_math>
		<vector_math name="csum2"><socket name="math_type" value="add" type_name="enum" /></vector_math>
		<!-- density: cold fuel core (scattering) + a little flame extinction -->
		<map_range name="f_range">
			<socket name="from_min" value="{a.fuel_range[0]}" type_name="float" />
			<socket name="from_max" value="{a.fuel_range[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<math name="f_pow"><socket name="math_type" value="power" type_name="enum" />
			<socket name="value2" value="0.7" type_name="float" /></math>
		<math name="f_d"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.fuel_density}" type_name="float" /></math>
		<math name="h_d"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.flame_density}" type_name="float" /></math>
		<math name="d_sum"><socket name="math_type" value="add" type_name="enum" /></math>
		<principled_volume name="pv">
			<socket name="color" value="{fmt(a.fuel_color + [0])}" type_name="color" />
			<socket name="anisotropy" value="0.5" type_name="float" />
			<socket name="emission_strength" value="1" type_name="float" />
		</principled_volume>
		<connect from_node="a_T" from_socket="fac" to_node="h_range" to_socket="value" />
		<connect from_node="a_T" from_socket="fac" to_node="bb_range" to_socket="value" />
		<connect from_node="bb_range" from_socket="result" to_node="bb" to_socket="temperature" />
		<connect from_node="h_range" from_socket="result" to_node="h_pow" to_socket="value1" />
		<connect from_node="h_pow" from_socket="value" to_node="e1" to_socket="value1" />
		<connect from_node="a_OH" from_socket="fac" to_node="oh_range" to_socket="value" />
		<connect from_node="oh_range" from_socket="result" to_node="oh_ramp" to_socket="fac" />
		<connect from_node="h_range" from_socket="result" to_node="edge_k" to_socket="value1" />
		<connect from_node="edge_k" from_socket="value" to_node="edge_w" to_socket="value2" />
		<connect from_node="edge_w" from_socket="value" to_node="edge_c" to_socket="value1" />
		<connect from_node="oh_ramp" from_socket="alpha" to_node="oh_w" to_socket="value1" />
		<connect from_node="edge_c" from_socket="value" to_node="oh_w" to_socket="value2" />
		<connect from_node="oh_w" from_socket="value" to_node="e2" to_socket="value1" />
		<connect from_node="bb" from_socket="color" to_node="c1" to_socket="vector1" />
		<connect from_node="e1" from_socket="value" to_node="c1" to_socket="scale" />
		<connect from_node="oh_ramp" from_socket="color" to_node="c2" to_socket="vector1" />
		<connect from_node="e2" from_socket="value" to_node="c2" to_socket="scale" />
		<connect from_node="c1" from_socket="vector" to_node="csum" to_socket="vector1" />
		<connect from_node="c2" from_socket="vector" to_node="csum" to_socket="vector2" />
		<connect from_node="f_pow" from_socket="value" to_node="e3" to_socket="value1" />
		<connect from_node="e3" from_socket="value" to_node="c3" to_socket="scale" />
		<connect from_node="csum" from_socket="vector" to_node="csum2" to_socket="vector1" />
		<connect from_node="c3" from_socket="vector" to_node="csum2" to_socket="vector2" />
		<connect from_node="csum2" from_socket="vector" to_node="pv" to_socket="emission_color" />
		<connect from_node="a_F" from_socket="fac" to_node="f_range" to_socket="value" />
		<connect from_node="f_range" from_socket="result" to_node="f_pow" to_socket="value1" />
		<connect from_node="f_pow" from_socket="value" to_node="f_d" to_socket="value1" />
		<connect from_node="h_range" from_socket="result" to_node="h_d" to_socket="value1" />
		<connect from_node="f_d" from_socket="value" to_node="d_sum" to_socket="value1" />
		<connect from_node="h_d" from_socket="value" to_node="d_sum" to_socket="value2" />
		<connect from_node="d_sum" from_socket="value" to_node="pv" to_socket="density" />
		<connect from_node="pv" from_socket="volume" to_node="output" to_socket="volume" />
	</shader>
{rim}
{meshes}

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
		<socket name="max_bounce" value="3" type_name="int" />
		<socket name="max_volume_bounce" value="{a.volume_bounces}" type_name="int" />
		<socket name="transparent_max_bounce" value="8" type_name="int" />
		<socket name="volume_ray_marching" value="true" type_name="boolean" />
		<socket name="volume_max_steps" value="{a.max_steps}" type_name="int" />
		<socket name="use_adaptive_sampling" value="false" type_name="boolean" />{denoise}
	</integrator>

	<volume name="flame_volume" geometry_type="2">
		<socket name="used_shaders" value="flame_shader" type_name="array_node" />
		<socket name="object_space" value="true" type_name="boolean" />
		<socket name="step_size" value="{a.step_size}" type_name="float" />
{attrs}
	</volume>
{objs}

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
    """Orbit around the jet axis (z). phi = azimuth around z, el = angle of the view direction
    to the plane normal to the axis (looking slightly up/downstream). 'roll' tilts the jet on
    screen (0 = jet horizontal, left -> right)."""
    e = 0.5 - 0.5 * math.cos(math.pi * t)
    phi = math.radians(a.phi0 + (a.phi1 - a.phi0) * e)
    el = math.radians(a.el0 + (a.el1 - a.el0) * e)
    dist = (a.dist0 + (a.dist1 - a.dist0) * e) * a.scale
    tz = (a.tz0 + (a.tz1 - a.tz0) * e) * a.scale
    tgt = [0.0, 0.0, tz]
    radial = [math.cos(phi), math.sin(phi), 0.0]
    d = add(scl(radial, math.cos(el)), [0, 0, -math.sin(el)])  # camera offset direction
    pos = add(tgt, scl(d, dist))
    f = norm(sub(tgt, pos))
    zax = [0, 0, 1]
    r = norm(sub(zax, scl(f, dot(zax, f))))          # jet axis -> screen right
    u = cross(r, f)
    roll = math.radians(a.roll)
    r2 = add(scl(r, math.cos(roll)), scl(u, math.sin(roll)))
    u2 = cross(r2, f)
    m = []
    for row in range(3):
        m += [r2[row], u2[row], f[row], pos[row]]
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--vdb", nargs="+", required=True)
    ap.add_argument("--nframes", type=int, default=0)
    ap.add_argument("--frame-from-name", action="store_true")
    ap.add_argument("--name", default="")
    ap.add_argument("--scale", type=float, default=50.0)
    ap.add_argument("--quadrants", type=int, default=4)
    ap.add_argument("--mirror-shift", type=float, default=0.0)
    # camera (data metres / degrees)
    ap.add_argument("--tz0", type=float, default=0.056)
    ap.add_argument("--tz1", type=float, default=None)
    ap.add_argument("--phi0", type=float, default=-60.0)
    ap.add_argument("--phi1", type=float, default=None)
    ap.add_argument("--el0", type=float, default=12.0)
    ap.add_argument("--el1", type=float, default=None)
    ap.add_argument("--dist0", type=float, default=0.24)
    ap.add_argument("--dist1", type=float, default=None)
    ap.add_argument("--roll", type=float, default=0.0)
    ap.add_argument("--fov", type=float, default=22.0)
    # flame
    ap.add_argument("--flame-range", type=float, nargs=2, default=[1530.0, 2150.0])
    ap.add_argument("--bb-range", type=float, nargs=2, default=[1200.0, 2600.0])
    ap.add_argument("--flame-gamma", type=float, default=1.6)
    ap.add_argument("--flame-emission", type=float, default=8.0)
    ap.add_argument("--flame-density", type=float, default=0.3)
    ap.add_argument("--oh-range", type=float, nargs=2, default=[0.0008, 0.004])
    ap.add_argument("--oh-emission", type=float, default=3.0)
    ap.add_argument("--oh-edge", type=float, default=0.0, help="0: OH everywhere, 1: OH only where h < 1")
    ap.add_argument("--oh-colors", default="0:0.25,0.08,1.0;0.6:0.30,0.20,1.0;1:0.55,0.45,1.0")
    ap.add_argument("--oh-alpha", default=OH_ALPHA)
    ap.add_argument("--fuel-range", type=float, nargs=2, default=[0.05, 0.9])
    ap.add_argument("--fuel-density", type=float, default=4.0)
    ap.add_argument("--fuel-emission", type=float, default=0.0)
    ap.add_argument("--fuel-glow-color", type=float, nargs=3, default=[0.15, 0.45, 1.0])
    ap.add_argument("--fuel-color", type=float, nargs=3, default=[0.55, 0.65, 0.8])
    # environment
    ap.add_argument("--nozzle-z", type=float, nargs=2, default=[-0.03, 0.008])
    ap.add_argument("--plate-z", type=float, default=0.0)
    ap.add_argument("--plate-r", type=float, default=0.03)
    ap.add_argument("--plate-color", type=float, nargs=3, default=[0.05, 0.05, 0.055])
    ap.add_argument("--ambient", type=float, nargs=3, default=[0.004, 0.005, 0.008])
    ap.add_argument("--bg-top", type=float, nargs=3, default=[0.006, 0.007, 0.012])
    ap.add_argument("--bg-bottom", type=float, nargs=3, default=[0.0005, 0.0005, 0.001])
    ap.add_argument("--bg-axis", default="z")
    ap.add_argument("--rim-strength", type=float, default=0.0)
    ap.add_argument("--rim-size", type=float, default=2.0)
    ap.add_argument("--rim-pos", type=float, nargs=3, default=[-4.0, 4.0, 8.0])
    ap.add_argument("--rim-target", type=float, nargs=3, default=[0.0, 0.0, 2.5])
    ap.add_argument("--rim-color", type=float, nargs=3, default=[0.6, 0.75, 1.0])
    ap.add_argument("--exposure", type=float, default=1.0)
    ap.add_argument("--volume-bounces", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=2048)
    ap.add_argument("--step-size", type=float, default=0.0)
    ap.add_argument("--denoise", type=int, default=1)
    a = ap.parse_args()
    for k in ("tz", "phi", "el", "dist"):
        if getattr(a, k + "1") is None:
            setattr(a, k + "1", getattr(a, k + "0"))

    os.makedirs(a.outdir, exist_ok=True)
    binw = Bin()
    o = {"oh_c": binw.colors(table(a.oh_colors, 3)), "oh_a": binw.floats([x[0] for x in table(a.oh_alpha, 1)]),
         "meshes": {}}
    for name, mb in build_meshes(a).items():
        ntri = len(mb.tris) // 3
        o["meshes"][name] = (binw.packed3(mb.verts), binw.ints(mb.tris), binw.ints([0] * ntri),
                             binw.bools(mb.smooth), len(mb.verts))
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
