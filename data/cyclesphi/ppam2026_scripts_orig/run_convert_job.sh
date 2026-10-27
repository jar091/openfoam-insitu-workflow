#!/bin/bash

cd /mnt/proj1/open-36-34/milanjaros/projects/blender

for dataset in aircraft changa_galaxy  gadget_grid  gadget_piccolo  jhtdb_pressure jhtdb_velocity  wdas; do
    sbatch /mnt/proj1/open-36-34/milanjaros/projects/blender/scripts/ppam2026/run_convert.sh $dataset
done