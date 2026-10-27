#!/bin/bash
# camera exploration (flame look), one scene dir per camera
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; S=/scratch/project/eu-25-121/milanjaros/openfoam
T=$S/renders/pitzDaily3D/v2/tests; V=$S/runs/pitzDaily3D/62M/VDB_v2/pitz_193100.vdb
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --look flame --vdb $V"
$G --outdir $T/camA --az0 60 --el0 22 --dist0 0.33
$G --outdir $T/camB --az0 75 --el0 18 --dist0 0.32
$G --outdir $T/camC --az0 40 --el0 25 --dist0 0.28 --target0 0.13 -0.002 0
$G --outdir $T/camD --az0 115 --el0 22 --dist0 0.30
$G --outdir $T/camE --az0 90 --el0 6 --dist0 0.36
$G --outdir $T/camF --az0 28 --el0 30 --dist0 0.25 --target0 0.12 -0.002 0
