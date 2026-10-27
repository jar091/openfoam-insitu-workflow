#!/usr/bin/env python3
"""
CyclesPhi scene generator for the pitzDaily3D 62M v2 animations (mesioVDB grids
b, T, Q, U_mag in one .vdb per frame).

Looks (--look):
  flame     emissive flame front: grid b (regress variable) -> fire ramp
            (dark red -> orange -> yellow-white peaked at b = 0.5), light black absorption;
            grid T masks the box faces / solid (inactive voxels = background 0).
  vortex    Q-criterion volume (opacity from Q), coloured by U_mag with a cool ramp,
            lit by a key sun light + a little self-emission.
  combined  both closures added in one volume (all four grids loaded).

One shared .xml.bin (ramps) per scene directory and one XML per frame (the camera may
move along a slow orbit: --az0/--az1, --el0/--el1, --dist0/--dist1 over the frame range).

Usage:
  make_pitz_scene.py --look flame --outdir DIR --vdb a.vdb [b.vdb ...] [--nframes N]
      [camera/look options]
  Frame index of a file = position in --vdb list, unless --frame-from-name (time index:
  (idx - FIRST) / STEP, see --first/--step) so that follow-mode renders get the right
  camera before all files exist.
"""
import argparse
import math
import os
import re
import struct

RAMP = 257

# ------------------------------------------------------------------ geometry
# VDB box (world metres): x -0.004..0.29, y -0.0254..0.0254, z -0.01905..0.01905
BOX = ((-0.004, -0.0254, -0.01905), (0.29, 0.0254, 0.01905))
CENTER = [(BOX[0][i] + BOX[1][i]) * 0.5 for i in range(3)]
DIAG = math.sqrt(sum((BOX[1][i] - BOX[0][i]) ** 2 for i in range(3)))
SCALE = 10.0 / DIAG  # scene units per metre


def to_scene(p):
    return [SCALE * (p[i] - CENTER[i]) for i in range(3)]


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
def norm(a):
    l = math.sqrt(sum(x * x for x in a))
    return [x / l for x in a]


def look_at(pos, target, up=(0, 1, 0)):
    f = norm(sub(target, pos))
    r = norm(cross(f, list(up)))
    u = cross(r, f)
    m = []
    for row in range(3):
        m += [r[row], u[row], f[row], pos[row]]
    return m


def fmt(v):
    return " ".join("%.7g" % x for x in v)


# ------------------------------------------------------------------ ramps
def parse_pts(spec, ncomp):
    """'t:v[,v,v];t:...' -> sorted list of (t, [v..])"""
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
            # smoothstep inside each segment -> no visible kinks in the sheets
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

    def colors(self, rgbs):
        off = len(self.data)
        self.data += struct.pack("<Q", len(rgbs))
        for c in rgbs:
            self.data += struct.pack("<4f", c[0], c[1], c[2], 0.0)
        return off


# Fire ramp over b (1 unburnt, 0 burnt; front at 0.5). Linear RGB.
FLAME_COLORS = ("0:0.18,0.012,0.0;0.12:0.45,0.04,0.003;0.28:1.0,0.22,0.02;"
                "0.42:1.0,0.55,0.12;0.5:1.0,0.85,0.5;0.56:1.0,0.62,0.2;0.7:0.9,0.25,0.03;1:0.5,0.05,0")
FLAME_ALPHA = "0:0;0.03:0;0.12:0.035;0.3:0.12;0.42:0.55;0.5:1;0.57:0.45;0.66:0;1:0"
# Cool ramp over U_mag (normalised): deep blue -> blue -> cyan -> ice white. Linear RGB.
VORTEX_COLORS = "0:0.02,0.05,0.35;0.3:0.03,0.18,0.85;0.55:0.05,0.55,1.0;0.8:0.35,0.85,1.0;1:0.85,0.97,1.0"
VORTEX_ALPHA = "0:0;0.02:0;0.25:0.25;0.6:0.75;1:1"


def shader_flame(a, p, bin_offs):
    return f"""
		<attribute name="{p}attr_b"><socket name="attribute" value="b" type_name="string" /></attribute>
		<attribute name="{p}attr_T"><socket name="attribute" value="T" type_name="string" /></attribute>
		<map_range name="{p}mr_T">
			<socket name="from_min" value="{a.tmask[0]}" type_name="float" />
			<socket name="from_max" value="{a.tmask[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<rgb_ramp name="{p}ramp">
			<socket name="ramp" value="{bin_offs['flame_c']}" type_name="array_color" />
			<socket name="ramp_alpha" value="{bin_offs['flame_a']}" type_name="array_float" />
		</rgb_ramp>
		<math name="{p}alpha"><socket name="math_type" value="multiply" type_name="enum" /></math>
		<math name="{p}dens"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.flame_density}" type_name="float" /></math>
		<math name="{p}emis"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.flame_emission}" type_name="float" /></math>
		<principled_volume name="{p}pv">
			<socket name="color" value="0 0 0 0" type_name="color" />
		</principled_volume>
		<connect from_node="{p}attr_b" from_socket="fac" to_node="{p}ramp" to_socket="fac" />
		<connect from_node="{p}attr_T" from_socket="fac" to_node="{p}mr_T" to_socket="value" />
		<connect from_node="{p}ramp" from_socket="alpha" to_node="{p}alpha" to_socket="value1" />
		<connect from_node="{p}mr_T" from_socket="result" to_node="{p}alpha" to_socket="value2" />
		<connect from_node="{p}alpha" from_socket="value" to_node="{p}dens" to_socket="value1" />
		<connect from_node="{p}alpha" from_socket="value" to_node="{p}emis" to_socket="value1" />
		<connect from_node="{p}ramp" from_socket="color" to_node="{p}pv" to_socket="emission_color" />
		<connect from_node="{p}dens" from_socket="value" to_node="{p}pv" to_socket="density" />
		<connect from_node="{p}emis" from_socket="value" to_node="{p}pv" to_socket="emission_strength" />
"""


def shader_vortex(a, p, bin_offs):
    return f"""
		<attribute name="{p}attr_Q"><socket name="attribute" value="Q" type_name="string" /></attribute>
		<attribute name="{p}attr_U"><socket name="attribute" value="U_mag" type_name="string" /></attribute>
		<map_range name="{p}mr_Q">
			<socket name="from_min" value="{a.qrange[0]}" type_name="float" />
			<socket name="from_max" value="{a.qrange[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<map_range name="{p}mr_U">
			<socket name="from_min" value="{a.urange[0]}" type_name="float" />
			<socket name="from_max" value="{a.urange[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<rgb_ramp name="{p}ramp_Q">
			<socket name="ramp" value="{bin_offs['vort_c']}" type_name="array_color" />
			<socket name="ramp_alpha" value="{bin_offs['vort_a']}" type_name="array_float" />
		</rgb_ramp>
		<rgb_ramp name="{p}ramp_U">
			<socket name="ramp" value="{bin_offs['vort_c']}" type_name="array_color" />
			<socket name="ramp_alpha" value="{bin_offs['vort_a']}" type_name="array_float" />
		</rgb_ramp>
		<math name="{p}dens"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.vortex_density}" type_name="float" /></math>
		<math name="{p}emis"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.vortex_emission}" type_name="float" /></math>
		<principled_volume name="{p}pv">
			<socket name="anisotropy" value="{a.vortex_aniso}" type_name="float" />
		</principled_volume>
		<connect from_node="{p}attr_Q" from_socket="fac" to_node="{p}mr_Q" to_socket="value" />
		<connect from_node="{p}attr_U" from_socket="fac" to_node="{p}mr_U" to_socket="value" />
		<connect from_node="{p}mr_Q" from_socket="result" to_node="{p}ramp_Q" to_socket="fac" />
		<connect from_node="{p}mr_U" from_socket="result" to_node="{p}ramp_U" to_socket="fac" />
		<connect from_node="{p}ramp_Q" from_socket="alpha" to_node="{p}dens" to_socket="value1" />
		<connect from_node="{p}ramp_Q" from_socket="alpha" to_node="{p}emis" to_socket="value1" />
		<connect from_node="{p}ramp_U" from_socket="color" to_node="{p}pv" to_socket="color" />
		<connect from_node="{p}ramp_U" from_socket="color" to_node="{p}pv" to_socket="emission_color" />
		<connect from_node="{p}dens" from_socket="value" to_node="{p}pv" to_socket="density" />
		<connect from_node="{p}emis" from_socket="value" to_node="{p}pv" to_socket="emission_strength" />
"""


def sun_xml(name, direction, strength, color, angle):
    """Sun light travelling along 'direction' (world/scene axes, y up); +Z of the light
    object = travel direction (checked: (-0.3,-1,-0.5) lights the camera-facing side)."""
    sd = norm(direction)
    up = [0, 1, 0] if abs(sd[1]) < 0.95 else [1, 0, 0]
    sx = norm(cross(up, sd)); sy = cross(sd, sx)
    tfm = [sx[0], sy[0], sd[0], 0, sx[1], sy[1], sd[1], 0, sx[2], sy[2], sd[2], 0]
    return f"""
	<shader name="{name}_shader">
		<emission name="{name}_em">
			<socket name="color" value="{fmt(list(color) + [0])}" type_name="color" />
			<socket name="strength" value="1" type_name="float" />
		</emission>
		<connect from_node="{name}_em" from_socket="emission" to_node="output" to_socket="surface" />
	</shader>
	<sunlight name="{name}_light" geometry_type="8">
		<socket name="used_shaders" value="{name}_shader" type_name="array_node" />
		<socket name="light_type" value="sun" type_name="enum" />
		<socket name="strength" value="{strength} {strength} {strength} 0" type_name="color" />
		<socket name="angle" value="{angle}" type_name="float" />
		<socket name="use_mis" value="true" type_name="boolean" />
	</sunlight>
	<object name="{name}_object">
		<socket name="geometry" value="{name}_light" type_name="node" />
		<socket name="tfm" value="{fmt(tfm)}" type_name="transform" />
	</object>
"""


def shader_flame_bb(a, p):
    """Blender-fire-style flame: reaction-zone weight w = (4 b (1-b))^p (crisp sheet at b = 0.5),
    blackbody emission colour from a visual temperature Tv = map(4b(1-b) -> Tlo..Thi),
    plus a faint blackbody glow of the hot products (map_range(T)) with light absorption.
    Grid T also masks inactive voxels (box faces / solid)."""
    return f"""
		<attribute name="{p}attr_b"><socket name="attribute" value="b" type_name="string" /></attribute>
		<attribute name="{p}attr_T"><socket name="attribute" value="T" type_name="string" /></attribute>
		<map_range name="{p}mr_T">
			<socket name="from_min" value="{a.tmask[0]}" type_name="float" />
			<socket name="from_max" value="{a.tmask[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<math name="{p}one_minus_b"><socket name="math_type" value="subtract" type_name="enum" />
			<socket name="value1" value="1" type_name="float" /></math>
		<math name="{p}bb1"><socket name="math_type" value="multiply" type_name="enum" /></math>
		<math name="{p}w1"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="4" type_name="float" /></math>
		<math name="{p}wpow"><socket name="math_type" value="power" type_name="enum" />
			<socket name="value2" value="{a.bb_power}" type_name="float" /></math>
		<math name="{p}w"><socket name="math_type" value="multiply" type_name="enum" /></math>
		<map_range name="{p}tvis">
			<socket name="from_min" value="0" type_name="float" />
			<socket name="from_max" value="1" type_name="float" />
			<socket name="to_min" value="{a.bb_tlo}" type_name="float" />
			<socket name="to_max" value="{a.bb_thi}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<blackbody name="{p}bbody" />
		<math name="{p}dens"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.flame_density}" type_name="float" /></math>
		<math name="{p}emis"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.flame_emission}" type_name="float" /></math>
		<principled_volume name="{p}pv_front">
			<socket name="color" value="0 0 0 0" type_name="color" />
		</principled_volume>
		<map_range name="{p}mr_glow">
			<socket name="from_min" value="{a.glow_trange[0]}" type_name="float" />
			<socket name="from_max" value="{a.glow_trange[1]}" type_name="float" />
			<socket name="clamp" value="true" type_name="boolean" />
		</map_range>
		<math name="{p}glow_e"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.glow_emission}" type_name="float" /></math>
		<math name="{p}glow_d"><socket name="math_type" value="multiply" type_name="enum" />
			<socket name="value2" value="{a.glow_density}" type_name="float" /></math>
		<blackbody name="{p}glow_bb"><socket name="temperature" value="{a.glow_temp}" type_name="float" /></blackbody>
		<principled_volume name="{p}pv_glow">
			<socket name="color" value="0 0 0 0" type_name="color" />
		</principled_volume>
		<add_closure name="{p}add" />
		<connect from_node="{p}attr_T" from_socket="fac" to_node="{p}mr_T" to_socket="value" />
		<connect from_node="{p}attr_b" from_socket="fac" to_node="{p}one_minus_b" to_socket="value2" />
		<connect from_node="{p}attr_b" from_socket="fac" to_node="{p}bb1" to_socket="value1" />
		<connect from_node="{p}one_minus_b" from_socket="value" to_node="{p}bb1" to_socket="value2" />
		<connect from_node="{p}bb1" from_socket="value" to_node="{p}w1" to_socket="value1" />
		<connect from_node="{p}w1" from_socket="value" to_node="{p}wpow" to_socket="value1" />
		<connect from_node="{p}wpow" from_socket="value" to_node="{p}w" to_socket="value1" />
		<connect from_node="{p}mr_T" from_socket="result" to_node="{p}w" to_socket="value2" />
		<connect from_node="{p}{'w1' if a.bb_tv_src == 'w1' else 'wpow'}" from_socket="value" to_node="{p}tvis" to_socket="value" />
		<connect from_node="{p}tvis" from_socket="result" to_node="{p}bbody" to_socket="temperature" />
		<connect from_node="{p}w" from_socket="value" to_node="{p}dens" to_socket="value1" />
		<connect from_node="{p}w" from_socket="value" to_node="{p}emis" to_socket="value1" />
		<connect from_node="{p}bbody" from_socket="color" to_node="{p}pv_front" to_socket="emission_color" />
		<connect from_node="{p}dens" from_socket="value" to_node="{p}pv_front" to_socket="density" />
		<connect from_node="{p}emis" from_socket="value" to_node="{p}pv_front" to_socket="emission_strength" />
		<connect from_node="{p}attr_T" from_socket="fac" to_node="{p}mr_glow" to_socket="value" />
		<connect from_node="{p}mr_glow" from_socket="result" to_node="{p}glow_e" to_socket="value1" />
		<connect from_node="{p}mr_glow" from_socket="result" to_node="{p}glow_d" to_socket="value1" />
		<connect from_node="{p}glow_bb" from_socket="color" to_node="{p}pv_glow" to_socket="emission_color" />
		<connect from_node="{p}glow_e" from_socket="value" to_node="{p}pv_glow" to_socket="emission_strength" />
		<connect from_node="{p}glow_d" from_socket="value" to_node="{p}pv_glow" to_socket="density" />
		<connect from_node="{p}pv_front" from_socket="volume" to_node="{p}add" to_socket="closure1" />
		<connect from_node="{p}pv_glow" from_socket="volume" to_node="{p}add" to_socket="closure2" />
"""


def camera_for(a, t):
    """t in [0,1] over the sequence; eased orbit around the target."""
    e = 0.5 - 0.5 * math.cos(math.pi * t)  # ease in/out
    az = a.az0 + (a.az1 - a.az0) * e
    el = a.el0 + (a.el1 - a.el0) * e
    dist = a.dist0 + (a.dist1 - a.dist0) * e
    tgt = [a.target0[i] + (a.target1[i] - a.target0[i]) * e for i in range(3)]
    azr, elr = math.radians(az), math.radians(el)
    d = [math.cos(elr) * math.cos(azr), math.sin(elr), math.cos(elr) * math.sin(azr)]
    pos_w = [tgt[i] + dist * d[i] for i in range(3)]
    return look_at(to_scene(pos_w), to_scene(tgt))


def scene_xml(a, offs, vdb, cam):
    look = a.look
    grids = {"flame": ["b", "T"], "vortex": ["Q", "U_mag"], "combined": ["b", "T", "Q", "U_mag"]}[look]
    body = ""
    fout = ("f_add", "closure") if a.flame_model == "blackbody" else ("f_pv", "volume")
    if look in ("flame", "combined"):
        body += shader_flame_bb(a, "f_") if a.flame_model == "blackbody" else shader_flame(a, "f_", offs)
    if look in ("vortex", "combined"):
        body += shader_vortex(a, "v_", offs)
    if look == "flame":
        body += '\t\t<connect from_node="%s" from_socket="%s" to_node="output" to_socket="volume" />\n' % fout
    elif look == "vortex":
        body += '\t\t<connect from_node="v_pv" from_socket="volume" to_node="output" to_socket="volume" />\n'
    else:
        body += ('\t\t<add_closure name="addc" />\n'
                 + '\t\t<connect from_node="%s" from_socket="%s" to_node="addc" to_socket="closure1" />\n' % fout
                 + '\t\t<connect from_node="v_pv" from_socket="volume" to_node="addc" to_socket="closure2" />\n'
                 '\t\t<connect from_node="addc" from_socket="closure" to_node="output" to_socket="volume" />\n')
    interp = {"linear": "", "cubic": ' interpolation="INTERPOLATION_CUBIC"'}[a.interpolation]
    attrs = "\n".join(
        f'\t\t<attribute name="{g}" std="ATTR_STD_NONE" type="float" element="ATTR_ELEMENT_VOXEL" '
        f'flags="0" buffer="{vdb}" volume_type="openvdb"{interp} />' for g in grids)
    s = SCALE
    tfm = [s, 0, 0, -s * CENTER[0], 0, s, 0, -s * CENTER[1], 0, 0, s, -s * CENTER[2]]
    fov = math.radians(a.fov)
    sun = ""
    if a.sun_strength > 0:
        sun += sun_xml("key", a.sun_dir, a.sun_strength, a.sun_color, a.sun_angle)
    if a.rim_strength > 0:
        sun += sun_xml("rim", a.rim_dir, a.rim_strength, a.rim_color, a.sun_angle)
    denoise = ""
    if a.denoise:
        denoise = """
		<socket name="use_denoise" value="true" type_name="boolean" />
		<socket name="denoiser_type" value="openimagedenoise" type_name="enum" />
		<socket name="denoise_use_gpu" value="false" type_name="boolean" />
		<socket name="denoiser_prefilter" value="accurate" type_name="enum" />
		<socket name="denoiser_quality" value="high" type_name="enum" />"""
    return f"""<?xml version="1.0"?>
<!-- make_pitz_scene.py look={look} -->
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
			<socket name="from_min" value="-0.45" type_name="float" />
			<socket name="from_max" value="0.35" type_name="float" />
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
{sun}
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
		<socket name="max_bounce" value="4" type_name="int" />
		<socket name="max_volume_bounce" value="{a.volume_bounces}" type_name="int" />
		<socket name="transparent_max_bounce" value="8" type_name="int" />
		<socket name="volume_ray_marching" value="{'true' if a.ray_marching else 'false'}" type_name="boolean" />
		<socket name="volume_max_steps" value="{a.max_steps}" type_name="int" />
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
		<socket name="tfm" value="{fmt(tfm)}" type_name="transform" />
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
    ap.add_argument("--vdb", nargs="+", required=True)
    ap.add_argument("--frame-from-name", action="store_true")
    ap.add_argument("--first", type=int, default=193010)
    ap.add_argument("--step", type=int, default=10)
    ap.add_argument("--nframes", type=int, default=0, help="frames of the orbit (default: number of files)")
    # camera (world metres / degrees; y up, azimuth in the x-z plane, 0 = +x)
    ap.add_argument("--target0", type=float, nargs=3, default=[0.14, -0.002, 0.0])
    ap.add_argument("--target1", type=float, nargs=3, default=None)
    ap.add_argument("--az0", type=float, default=60.0)
    ap.add_argument("--az1", type=float, default=None)
    ap.add_argument("--el0", type=float, default=22.0)
    ap.add_argument("--el1", type=float, default=None)
    ap.add_argument("--dist0", type=float, default=0.30)
    ap.add_argument("--dist1", type=float, default=None)
    ap.add_argument("--fov", type=float, default=30.0, help="degrees, vertical for landscape")
    # look
    ap.add_argument("--exposure", type=float, default=1.0)
    ap.add_argument("--flame-density", type=float, default=2.0)
    ap.add_argument("--flame-emission", type=float, default=6.0)
    ap.add_argument("--flame-colors", default=FLAME_COLORS)
    ap.add_argument("--flame-alpha", default=FLAME_ALPHA)
    ap.add_argument("--tmask", type=float, nargs=2, default=[250.0, 288.0])
    ap.add_argument("--qrange", type=float, nargs=2, default=[3e5, 1.2e7])
    ap.add_argument("--urange", type=float, nargs=2, default=[2.0, 28.0])
    ap.add_argument("--vortex-colors", default=VORTEX_COLORS)
    ap.add_argument("--vortex-alpha", default=VORTEX_ALPHA)
    ap.add_argument("--vortex-density", type=float, default=30.0)
    ap.add_argument("--vortex-emission", type=float, default=0.6)
    ap.add_argument("--vortex-aniso", type=float, default=0.3)
    ap.add_argument("--sun-strength", type=float, default=0.0)
    ap.add_argument("--sun-dir", type=float, nargs=3, default=[0.3, 1.0, 0.5])
    ap.add_argument("--sun-color", type=float, nargs=3, default=[1.0, 0.95, 0.9])
    ap.add_argument("--sun-angle", type=float, default=0.2, help="sun angular diameter (rad)")
    ap.add_argument("--rim-strength", type=float, default=0.0)
    ap.add_argument("--rim-dir", type=float, nargs=3, default=[-0.45, -0.25, 0.85])
    ap.add_argument("--rim-color", type=float, nargs=3, default=[0.75, 0.88, 1.0])
    ap.add_argument("--flame-model", default="ramp", choices=["ramp", "blackbody"])
    ap.add_argument("--bb-power", type=float, default=3.0, help="w = (4 b (1-b))^power")
    ap.add_argument("--bb-tv-src", default="wpow", choices=["w1", "wpow"],
                    help="visual temperature from 4b(1-b) (w1) or from the shaped weight (wpow)")
    ap.add_argument("--bb-tlo", type=float, default=1100.0)
    ap.add_argument("--bb-thi", type=float, default=3200.0)
    ap.add_argument("--glow-trange", type=float, nargs=2, default=[1000.0, 1700.0])
    ap.add_argument("--glow-emission", type=float, default=0.3)
    ap.add_argument("--glow-density", type=float, default=0.3)
    ap.add_argument("--glow-temp", type=float, default=1300.0)
    ap.add_argument("--ambient", type=float, nargs=3, default=[0.05, 0.055, 0.07])
    ap.add_argument("--bg-top", type=float, nargs=3, default=[0.018, 0.022, 0.035])
    ap.add_argument("--bg-bottom", type=float, nargs=3, default=[0.002, 0.002, 0.004])
    ap.add_argument("--volume-bounces", type=int, default=0)
    ap.add_argument("--ray-marching", type=int, default=1)
    ap.add_argument("--max-steps", type=int, default=1024)
    ap.add_argument("--step-size", type=float, default=0.0)
    ap.add_argument("--interpolation", default="linear", choices=["linear", "cubic"])
    ap.add_argument("--denoise", type=int, default=1)
    a = ap.parse_args()
    for k in ("target", "az", "el", "dist"):
        if getattr(a, k + "1") is None:
            setattr(a, k + "1", getattr(a, k + "0"))

    os.makedirs(a.outdir, exist_ok=True)
    b = Bin()
    offs = {"flame_c": b.colors(table(a.flame_colors, 3)),
            "flame_a": b.floats([v[0] for v in table(a.flame_alpha, 1)]),
            "vort_c": b.colors(table(a.vortex_colors, 3)),
            "vort_a": b.floats([v[0] for v in table(a.vortex_alpha, 1)])}
    binpath = os.path.join(a.outdir, "scene.xml.bin")
    with open(binpath, "wb") as f:
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
            f.write(scene_xml(a, offs, os.path.abspath(vdb), camera_for(a, t)))
        lnk = xml + ".bin"
        if os.path.lexists(lnk):
            os.remove(lnk)
        os.symlink("scene.xml.bin", lnk)
    print("wrote %d scene(s) to %s" % (len(a.vdb), a.outdir))


if __name__ == "__main__":
    main()
