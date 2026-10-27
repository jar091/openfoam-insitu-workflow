#!/bin/bash
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
T=$S/renders/pitzDaily3D/v2/tests; V=$S/runs/pitzDaily3D/62M/VDB_v2/pitz_193280.vdb
CAM="--az0 105 --el0 22 --dist0 0.29 --target0 0.145 -0.004 0"
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --look vortex --vdb $V $CAM"
$G --outdir $T/V1a --vortex-density 30 --vortex-emission 0.6 --sun-strength 3
$G --outdir $T/V1b --vortex-density 60 --vortex-emission 1.5 --sun-strength 2
$G --outdir $T/V1c --qrange 1e6 2e7 --vortex-density 60 --vortex-emission 1.0 --sun-strength 3
$G --outdir $T/V1d --vortex-density 40 --vortex-emission 3 --sun-strength 0
