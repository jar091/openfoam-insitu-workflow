#!/bin/bash
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
T=$S/renders/pitzDaily3D/v2/tests; V=$S/runs/pitzDaily3D/62M/VDB_v2/pitz_193220.vdb
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --look flame --vdb $V"
$G --outdir $T/c2D --az0 115 --el0 22 --dist0 0.27
$G --outdir $T/c2G --az0 130 --el0 35 --dist0 0.23 --target0 0.15 -0.004 0
$G --outdir $T/c2H --az0 105 --el0 28 --dist0 0.24 --target0 0.145 -0.004 0
$G --outdir $T/c2I --az0 140 --el0 24 --dist0 0.22 --target0 0.16 -0.002 0
