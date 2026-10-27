#!/bin/bash
# flame look iteration 1: saturated fire ramps, emission variants (camera G')
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
T=$S/renders/pitzDaily3D/v2/tests; V=$S/runs/pitzDaily3D/62M/VDB_v2/pitz_193280.vdb
CAM="--az0 132 --el0 32 --dist0 0.25 --target0 0.15 -0.004 0"
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --look flame --vdb $V $CAM"
R1C="0:0.25,0.01,0;0.15:0.6,0.05,0.0;0.3:1.0,0.18,0.01;0.42:1.0,0.38,0.04;0.5:1.0,0.6,0.15;0.56:1.0,0.35,0.04;0.65:0.7,0.08,0;1:0.3,0.02,0"
R1A="0:0;0.04:0;0.15:0.02;0.3:0.06;0.42:0.35;0.5:1;0.56:0.35;0.63:0;1:0"
R2C="0:0.25,0.01,0;0.15:0.6,0.05,0.0;0.3:1.0,0.18,0.01;0.42:1.0,0.38,0.04;0.5:1.0,0.65,0.2;0.55:0.5,0.4,0.6;0.6:0.08,0.2,1.0;1:0.05,0.1,0.8"
R2A="0:0;0.04:0;0.15:0.02;0.3:0.06;0.42:0.35;0.5:1;0.55:0.5;0.6:0.25;0.68:0;1:0"
R3A="0:0;0.05:0;0.2:0.015;0.35:0.04;0.45:0.3;0.5:1;0.54:0.3;0.6:0;1:0"
$G --outdir $T/L1a --flame-colors "$R1C" --flame-alpha "$R1A" --flame-emission 20 --flame-density 1.5
$G --outdir $T/L1b --flame-colors "$R1C" --flame-alpha "$R1A" --flame-emission 40 --flame-density 1.0
$G --outdir $T/L1c --flame-colors "$R2C" --flame-alpha "$R2A" --flame-emission 25 --flame-density 1.5
$G --outdir $T/L1d --flame-colors "$R1C" --flame-alpha "$R3A" --flame-emission 40 --flame-density 2.0
