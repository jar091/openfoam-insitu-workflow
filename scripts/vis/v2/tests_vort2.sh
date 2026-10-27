#!/bin/bash
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
T=$S/renders/pitzDaily3D/v2/tests; V=$S/runs/pitzDaily3D/62M/VDB_v2/pitz_193280.vdb
CAM="--az0 132 --el0 32 --dist0 0.25 --target0 0.15 -0.004 0 --exposure 2.83"
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --look vortex --vdb $V $CAM"
$G --outdir $T/V2a --vortex-density 300 --vortex-emission 10 --sun-strength 0
$G --outdir $T/V2b --vortex-density 300 --vortex-emission 30 --sun-strength 0
$G --outdir $T/V2c --vortex-density 300 --vortex-emission 3 --sun-strength 10
$G --outdir $T/V2d --vortex-density 300 --vortex-emission 3 --sun-strength 10 --sun-dir -0.3 -1 -0.5
$G --outdir $T/V2e --vortex-density 600 --vortex-emission 20 --qrange 1e6 3e7
$G --outdir $T/V2f --vortex-density 150 --vortex-emission 20 --qrange 1e5 1e7
