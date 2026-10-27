#!/usr/bin/env python3
"""
Convert the occDrivAer car surface (OBJ from surfaceMeshExtract, one 'g <patch>' group per
OpenFOAM wall patch, metres, z up) into a CyclesPhi XML + .xml.bin mesh include:

    <outdir>/car_mesh.xml      <mesh name="car" geometry_type="0"> + <object name="car_object">
    <outdir>/car_mesh.xml.bin  positions (packed float3), triangles, shader slot, smooth flags

The include is referenced from the frame scenes (make_drivaer_scene.py) as the LAST element:
    <include src="/abs/path/car_mesh.xml" />
(the xml_bin reader switches to the include's .bin and closes it afterwards).

Material slots (shader names must be defined in the including scene):
    0 car_paint     body panels, mirrors, door handles, roof, trunk, pillars
    1 car_glass     windscreen, side and rear windows (closed body: opaque dark glass)
    2 car_trim      window frames, grill inserts (black satin plastic)
    3 car_tyre      tyres (rubber)
    4 car_metal     rims, brake discs (machined aluminium)
    5 car_under     underbody, engine undershield, powertrain, exhaust, wheel supports,
                    control surfaces (dark grey)
    6 car_lamp      headlamps (clear chrome-like)

Faces are fan-triangulated and their winding is reversed: OpenFOAM boundary faces point out
of the fluid domain, i.e. into the car; the reversed faces have outward normals.

Usage (bundled python with numpy, on a compute node):
    bash scripts/vis/pyvdb.sh data/cyclesphi/scenes/occDrivAer/make_car_mesh.py \
        --obj runs/occDrivAer/geometry/car.obj --outdir runs/occDrivAer/geometry
"""
import argparse
import os
import struct
import time

import numpy as np

SLOTS = ["car_paint", "car_glass", "car_trim", "car_tyre", "car_metal", "car_under", "car_lamp"]


def slot_of(patch):
    p = patch
    if "frame" in p or p.startswith("ClosedGrill"):
        return 2
    if "Window" in p:
        return 1
    if p.startswith("Tires"):
        return 3
    if p.startswith("Rims") or p.startswith("BrakeDisc"):
        return 4
    if p.startswith("BodyHeadlamps"):
        return 6
    if (p.startswith("Engine") or p.startswith("OCDA") or p.startswith("Powertrain")
            or p.startswith("Exhaust") or p.startswith("WheelSupport") or p.startswith("CTRL")):
        return 5
    return 0  # Body*, Notchback*, Mirrors*


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--obj", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--name", default="car_mesh")
    a = ap.parse_args()

    t0 = time.time()
    verts = []
    tris = []
    shd = []
    counts = {}
    slot = 0
    with open(a.obj) as f:
        for line in f:
            c = line[0]
            if c == "v" and line[1] == " ":
                verts.append(line[2:])
            elif c == "f":
                idx = [int(t.split("/")[0]) - 1 for t in line.split()[1:]]
                idx.reverse()  # outward normals
                for k in range(1, len(idx) - 1):
                    tris.append((idx[0], idx[k], idx[k + 1]))
                    shd.append(slot)
                counts[slot] = counts.get(slot, 0) + len(idx) - 2
            elif c == "g":
                slot = slot_of(line.split()[1])
    V = np.fromstring(" ".join(verts), sep=" ", dtype=np.float64).astype(np.float32).reshape(-1, 3)
    T = np.asarray(tris, dtype=np.int32).reshape(-1)
    S = np.asarray(shd, dtype=np.int32)
    print("parsed %d verts, %d tris in %.1f s" % (len(V), len(S), time.time() - t0))
    for k, n in sorted(counts.items()):
        print("  slot %d %-10s %9d tris" % (k, SLOTS[k], n))
    print("  bounds", V.min(0), V.max(0))

    os.makedirs(a.outdir, exist_ok=True)
    xml = os.path.join(a.outdir, a.name + ".xml")
    data = bytearray()

    def put(header_count, arr):
        off = len(data)
        data.extend(struct.pack("<Q", header_count))
        data.extend(arr.tobytes())
        return off

    o_P = put(V.nbytes, V)                 # raw byte buffer: uint64 byte count + packed float3
    o_T = put(T.size, T)
    o_S = put(S.size, S)
    o_sm = put(S.size, np.ones(S.size, dtype=np.uint8))
    with open(xml + ".bin", "wb") as f:
        f.write(data)
    with open(xml, "w") as f:
        f.write(f"""<?xml version="1.0"?>
<!-- occDrivAer car surface (47 OpenFOAM wall patches, {len(V)} vertices, {len(S)} triangles),
     made by data/cyclesphi/scenes/occDrivAer/make_car_mesh.py. Shader slots: {' '.join(SLOTS)} -->
<cycles>
	<mesh name="car" geometry_type="0">
		<socket name="used_shaders" value="{' '.join(SLOTS)}" type_name="array_node" />
		<socket name="triangles" value="{o_T}" type_name="array_int" />
		<socket name="shader" value="{o_S}" type_name="array_int" />
		<socket name="smooth" value="{o_sm}" type_name="array_boolean" />
		<attribute name="P" std="ATTR_STD_POSITION" type="point" element="ATTR_ELEMENT_VERTEX" flags="0" size="{len(V)}" buffer="{o_P}" />
	</mesh>
	<object name="car_object">
		<socket name="geometry" value="car" type_name="node" />
		<socket name="tfm" value="1 0 0 0 0 1 0 0 0 0 1 0" type_name="transform" />
	</object>
</cycles>
""")
    print("wrote %s (+ .bin %.1f MB) in %.1f s" % (xml, len(data) / 1e6, time.time() - t0))


if __name__ == "__main__":
    main()
