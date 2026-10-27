# CyclesPhi scene: DLR jet-in-hot-coflow flame (reactingFoam DLRJHC)

Scene for the mesioVDB frames of `combustion/reactingFoam/LES/DLRJHC/1M`
(OpenFOAM v2606, notes: `docs/notes/animations_DLRJHC.md`). Each VDB holds the grids
`T`, `OH`, `Qdot`, `CH4` on the box (0 0 0) .. (0.025 0.025 0.12) m (quarter domain near the
jet axis), h = 0.13 mm, 193 x 193 x 924 = 34.4M voxels. The scene uses `T`, `OH`, `CH4`.

Note: `make_dlrcjh_scene.py` in `../DLRCJH/` belongs to a different case (the XiFoam DLR
confined jet combustor) and is not related to this scene.

## Files

| File | Content |
|---|---|
| `make_jhc_scene.py` | Generator: one XML per frame + one shared `.xml.bin` (OH ramp, nozzle mesh). |
| `jhc_template.xml` + `.xml.bin` | Final look as one template (`{VDB_DATA}` = absolute .vdb path, camera of frame 0). |
| `scripts/vis/fire/jhc_scenes.sh` | Exact options of the final animation. |

## Geometry and instancing

Scene units = data metres x 50 (120 mm -> 6 units). The simulated quarter (symmetry planes
x = 0, y = 0) is instanced four times: one `volume` geometry, four `object`s with transforms
`diag(+-50, +-50, 50)`. Each copy is shifted by 0.2 mm (1.5 voxels) towards the axis
(`--mirror-shift`), so the copies overlap at the symmetry planes; without the shift a dark seam
appears along the axis (interpolation towards the background value 0 at the box faces).
The fuel nozzle is a thick-walled steel tube mesh (r 1.0/1.5 mm, z -30..8 mm, metallic
`principled_bsdf`, roughness 0.28). No walls: the chamber walls are 37.5 mm away.
The jet axis is shown horizontally (left to right, rolled by -10 deg) to fill the 16:9 frame.

## Volume shader `flame_shader` (one `principled_volume`, emission only)

```
T  --map_range(1520..1850 K, clamp)--> h
T  --map_range(1520..1850 -> 1500..2500 K)--> blackbody --> c_bb
h  --power(2.0)--> *400 --> e1                                   (flame, blackbody colour)
OH --map_range(0.0010..0.0035)--> rgb_ramp (colour: violet 0.10/0.05/1 -> 0.35/0.30/1;
                                           alpha window 0:0, 0.08:0, 0.3:0.35, 0.55:1, 0.8:0.7, 1:0.45)
   alpha * max(0, 1 - 1.0*h) * 1000 --> e2                        (OH sheath: edges and tip only)
CH4 --map_range(0.02..0.9)--> power(0.7) --> *3 --> e3            (faint blue cold-jet glow 0.1/0.4/1)
emission_color    = e1*c_bb + e2*c_OH + e3*c_fuel   (vector_math scale/add)
emission_strength = 1
density           = 0.3*h  (slight self-absorption of the flame; colour irrelevant)
```

- The coflow is at 1490 K, so the blackbody term starts at 1520 K; the artistic temperature
  1500..2500 K gives orange edges and a yellow-white core.
- OH: the initial field has OH = 0.001 everywhere (it relaxes to 2e-4 within ~0.1 ms), so the OH
  window starts above 0.0012; flame OH reaches 3-5e-3.
- World: near-black gradient (0.0005 -> 0.006/0.007/0.012), ambient 0.004 (only lights the nozzle).

## Camera, integrator

- Orbit around the jet axis: azimuth phi -70 -> -20 deg, view elevation 25 -> 18 deg, eased;
  dolly-out with the growing flame: target z 35 -> 58 mm, distance 125 -> 168 mm; fov 22 deg.
- Ray marching, object-space step 0.4 mm (3 voxels), max 2048 steps, no volume bounces, OIDN
  denoising. 1920x1080, 32 spp: ~62 s per frame on one 128-core node (64 spp with the voxel step:
  174 s; side-by-side crops are indistinguishable, `$S/renders/DLRJHC/tests/t11/out/crop_ac.png`).
