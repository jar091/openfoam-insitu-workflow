#!/bin/bash
# look iteration 2: crisp blackbody flame (high power), Tv from shaped weight
P=/mnt/proj2/eu-25-121/milanjaros/openfoam; T=/scratch/project/eu-25-121/milanjaros/openfoam/renders/pitzDaily3D/v2/tests; V=/scratch/project/eu-25-121/milanjaros/openfoam/runs/pitzDaily3D/62M/VDB_v2/pitz_194120.vdb
CAM="--az0 132 --el0 32 --dist0 0.25 --target0 0.15 -0.004 0 --exposure 2.83"
G="bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/v2/make_pitz_scene.py --vdb $V $CAM --look flame --flame-model blackbody"
$G --outdir $T/BB1 --bb-power 25 --flame-emission 40 --flame-density 1.0 --glow-emission 0.15 --bb-tlo 1000 --bb-thi 3000
$G --outdir $T/BB2 --bb-power 25 --flame-emission 25 --flame-density 1.5 --glow-emission 0.15 --bb-tlo 1000 --bb-thi 3600
$G --outdir $T/BB3 --bb-power 40 --flame-emission 60 --flame-density 1.5 --glow-emission 0.25 --bb-tlo 1000 --bb-thi 3200
$G --outdir $T/BB4 --bb-power 15 --flame-emission 20 --flame-density 1.0 --glow-emission 0.1 --bb-tlo 900 --bb-thi 2800
$G --outdir $T/BB5 --bb-power 25 --flame-emission 40 --flame-density 1.0 --glow-emission 0 --bb-tlo 1000 --bb-thi 3000 --bb-tv-src w1
