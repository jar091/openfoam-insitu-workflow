#!/bin/bash
# look iteration: blackbody flame (crisp power shaping) vs ramp flame; vortex key+rim lighting
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; T=/scratch/project/eu-25-121/milanjaros/openfoam/renders/pitzDaily3D/v2/tests; V=/scratch/project/eu-25-121/milanjaros/openfoam/runs/pitzDaily3D/62M/VDB_v2/pitz_194120.vdb
CAM="--az0 132 --el0 32 --dist0 0.25 --target0 0.15 -0.004 0 --exposure 2.83"
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --vdb $V $CAM"
FC="0:0.25,0.01,0;0.15:0.6,0.05,0.0;0.3:1.0,0.18,0.01;0.42:1.0,0.38,0.04;0.5:1.0,0.6,0.15;0.56:1.0,0.35,0.04;0.65:0.7,0.08,0;1:0.3,0.02,0"
FA="0:0;0.04:0;0.15:0.02;0.3:0.06;0.42:0.35;0.5:1;0.56:0.35;0.63:0;1:0"
$G --look flame --outdir $T/B0 --flame-colors "$FC" --flame-alpha "$FA" --flame-emission 40 --flame-density 1.0
$G --look flame --outdir $T/B1 --flame-model blackbody --bb-power 3 --flame-emission 40 --flame-density 1.0 --glow-emission 0.3
$G --look flame --outdir $T/B2 --flame-model blackbody --bb-power 6 --flame-emission 60 --flame-density 1.5 --glow-emission 0.6
$G --look flame --outdir $T/B3 --flame-model blackbody --bb-power 3 --bb-thi 4500 --flame-emission 30 --flame-density 1.0 --glow-emission 0.3 --glow-temp 1500
$G --look flame --outdir $T/B4 --flame-model blackbody --bb-power 2 --flame-emission 25 --flame-density 1.0 --glow-emission 0
$G --look vortex --outdir $T/R1 --vortex-density 300 --vortex-emission 10 --sun-strength 8 --sun-dir -0.3 -1 -0.5 --rim-strength 15
$G --look vortex --outdir $T/R2 --vortex-density 400 --vortex-emission 5 --sun-strength 5 --sun-dir -0.3 -1 -0.5 --rim-strength 25
