#!/bin/bash
# combined look: blackbody flame (BB1) + Q vortices with key/rim light
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; T=/scratch/project/eu-25-121/milanjaros/openfoam/renders/pitzDaily3D/v2/tests; V=/scratch/project/eu-25-121/milanjaros/openfoam/runs/pitzDaily3D/62M/VDB_v2/pitz_194120.vdb
CAM="--az0 132 --el0 32 --dist0 0.25 --target0 0.15 -0.004 0 --exposure 2.83"
FL="--flame-model blackbody --bb-power 25 --flame-emission 40 --flame-density 1.0 --glow-emission 0.15 --bb-tlo 1000 --bb-thi 3000"
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --vdb $V $CAM --look combined $FL --sun-dir -0.3 -1 -0.5"
$G --outdir $T/CC1 --vortex-density 400 --vortex-emission 5 --sun-strength 5 --rim-strength 25
$G --outdir $T/CC2 --vortex-density 300 --vortex-emission 15 --sun-strength 5 --rim-strength 25
$G --outdir $T/CC3 --vortex-density 200 --vortex-emission 25 --sun-strength 3 --rim-strength 15
