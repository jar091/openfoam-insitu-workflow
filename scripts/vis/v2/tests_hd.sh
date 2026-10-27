#!/bin/bash
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
T=$S/renders/pitzDaily3D/v2/tests; V=$S/runs/pitzDaily3D/62M/VDB_v2/pitz_193280.vdb
CAM="--az0 132 --el0 32 --dist0 0.25 --target0 0.15 -0.004 0 --exposure 2.83"
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --vdb $V $CAM --look combined --vortex-density 300 --vortex-emission 30 --flame-emission 40 --flame-density 1.0"
$G --outdir $T/HDdn --denoise 1
$G --outdir $T/HDno --denoise 0
