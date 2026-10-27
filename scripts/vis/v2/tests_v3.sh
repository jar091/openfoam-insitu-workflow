#!/bin/bash
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
T=$S/renders/pitzDaily3D/v2/tests; V=$S/runs/pitzDaily3D/62M/VDB_v2/pitz_193280.vdb
CAM="--az0 132 --el0 32 --dist0 0.25 --target0 0.15 -0.004 0 --exposure 2.83"
R1C="0:0.25,0.01,0;0.15:0.6,0.05,0.0;0.3:1.0,0.18,0.01;0.42:1.0,0.38,0.04;0.5:1.0,0.6,0.15;0.56:1.0,0.35,0.04;0.65:0.7,0.08,0;1:0.3,0.02,0"
R1A="0:0;0.04:0;0.15:0.02;0.3:0.06;0.42:0.35;0.5:1;0.56:0.35;0.63:0;1:0"
FL="--flame-colors $R1C --flame-alpha $R1A --flame-emission 40 --flame-density 1.0"
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --vdb $V $CAM"
$G --look vortex --outdir $T/V3a --vortex-density 300 --vortex-emission 15 --sun-strength 8
$G --look vortex --outdir $T/V3b --vortex-density 300 --vortex-emission 15 --sun-strength 8 --sun-dir -0.3 -1 -0.5
$G --look combined --outdir $T/C1a $FL --vortex-density 300 --vortex-emission 30
$G --look combined --outdir $T/C1b $FL --vortex-density 120 --vortex-emission 12
