#!/bin/bash

cd /mnt/proj1/open-36-34/milanjaros/projects/blender

for dataset in aircraft; do
    sbatch /mnt/proj1/open-36-34/milanjaros/projects/blender/scripts/ppam2026/run_render.sh $dataset Q_in_nodes
done

for dataset in changa_galaxy  gadget_grid  gadget_piccolo  jhtdb_pressure jhtdb_velocity  wdas; do
    sbatch /mnt/proj1/open-36-34/milanjaros/projects/blender/scripts/ppam2026/run_render.sh $dataset density
done