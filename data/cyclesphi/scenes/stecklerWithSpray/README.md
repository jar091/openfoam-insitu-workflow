# CyclesPhi scene: Steckler room fire (fireFoam stecklerWithSpray)

Scene for the mesioVDB frames of `combustion/fireFoam/RAS/stecklerWithSpray`
(OpenFOAM v2606, notes: `docs/notes/animations_stecklerWithSpray.md`).
Each VDB holds the grids `T`, `CH4` and `U_mag` (box (-1.4 0 -1.4) .. (4.2 4.6 1.4) m,
h = 12.5 mm, 27M active voxels). The scene uses `T` and `CH4`.

## Files

| File | Content |
|---|---|
| `make_steckler_scene.py` | Generator: one XML per frame + one shared `.xml.bin` (ramps, meshes). All looks and the camera orbit are command-line options. |
| `steckler_template.xml` + `.xml.bin` | The final look as a single template (`{VDB_DATA}` = absolute .vdb path, camera of frame 0). |
| `scripts/vis/fire/steckler_scenes.sh` | The exact options of the final animation (writes the per-frame XMLs). |

Render: `cycles --device CPU --samples 48 --width 1920 --height 1080 --output f.png f.xml`
(the PNG writer applies the OCIO view; we use `config_standard.ocio`, i.e.
`scripts/vis/v2/render_xml.sh standard ...`). OIDN denoising is switched on in the integrator.

## World and geometry

World units are metres, y up, the volume object has the identity transform (VDB world = scene).
Meshes (all `principled_bsdf`, roughness 0.7-0.9, written as triangle meshes into the .bin):

- room floor slab (warm brown 0.30/0.24/0.19) and a large dark ground plane (0.10);
- room walls: back wall z = -1.4, left wall x = -1.4, ceiling y = 2.13 (warm grey 0.55/0.53/0.50),
  the viewer side z = +1.4 is cut away (dollhouse view);
- facade x = 1.4 (2.4 cm slab centred on the baffle) up to y = 4.6 with the doorway
  (z -0.37..0.37, y 0..1.83);
- black burner tray 0.32 x 0.32 m at the floor centre;
- backdrop wall z = -1.4 behind the exterior region (x 1.4..7, y 0..6, blue grey 0.22/0.23/0.26).
  The walls lie outside the fluid cells, so they never hide voxels.

## Volume shader `fire_shader` (one `principled_volume`)

```
CH4 --map_range(3e-4..0.004, clamp)--> s --power(0.9)--> *25 --> * fade --> density
   fade = map_range(y: 4.55 -> 3.7) * map_range(x: 4.15 -> 3.5)   (geometry.position; smoke
          dissolves before the open outlet boundaries y = 4.6 and x = 4.2)
T --map_range(300..600)--> rgb_ramp (grey 0.10/0.10/0.11 -> warm 0.14/0.10/0.07) --> color (albedo)
T --map_range(450..1400 -> 1000..2300 K)--> blackbody --> emission_color
T --map_range(450..1400)--> h --power(2)--> *80 ----------------+--> add --> emission_strength
T --map_range(400..700)--> g --power(2)--> * s^0.9 --> *1.0 ----+   (ember glow of the hot smoke layer)
anisotropy 0.35, absorption_color 0.05 (dark soot)
```

- CH4 is the smoke proxy: the case has `combustionModel none` and a volumetric heat source
  (`HRRzone`, 62.9 kW), the burner injects CH4 that is transported passively, so its mass
  fraction marks the fire effluent (plume, ceiling layer, door outflow, exterior plume).
- The blackbody temperature is artistic (the RAS heat-source zone reaches ~1900 K only in a
  few cells; 450..1400 K is spread over 1000..2300 K so the plume reads as a flame).

## Lights, camera, integrator

- World: near-black gradient for camera rays (0.002 -> 0.010/0.013/0.022), ambient 0.01.
- Key light: elliptical area light 4 m, strength 1100, cool white (0.75/0.85/1.0) at (10, 6, 0.5)
  aimed at (1.5, 2, 0): rakes across the facade, so the dark smoke reads in silhouette and with
  self-shadowing. The fire itself is the second light (volume emission, warm interior).
- Camera: fov 33 deg, target (1.45, 2.2, 0); eased orbit azimuth 22 -> 38 deg (about +y,
  0 = from +z), elevation 7 -> 9 deg, distance 9.4 -> 9.0 m over the 250 frames.
- Integrator: max bounce 3, 1 volume bounce (flame light scattered in the smoke layer),
  ray marching with object step 0.02 m, max 1024 steps, OIDN (accurate prefilter, high quality).
- 1920x1080, 48 spp: ~107 s per frame on one 128-core node.
