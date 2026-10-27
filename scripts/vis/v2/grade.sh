#!/bin/bash
# Tone-map a linear EXR (rendered with OCIO config "raw") to PNG with a given exposure
# (stops) and OCIO view config, using oiiotool from the CyclesPhi lib bundle.
# Usage: grade.sh <in.exr> <out.png> <stops> <standard|agx|agx_punchy|filmic_mhc|pbrneutral>
L=/mnt/proj2/eu-25-121/milanjaros/openfoam/install/cyclesphi_libs/linux_x64
CM=/mnt/proj2/eu-25-121/milanjaros/openfoam/data/cyclesphi/colormanagement
case $4 in standard) C=$CM/config_standard.ocio ;; agx) C=$CM/config.ocio ;; *) C=$CM/config_$4.ocio ;; esac
m=$(python3 -c "print(2**$3)")
LD_LIBRARY_PATH=/mnt/proj2/eu-25-121/milanjaros/openfoam/install/cyclesphi_cpu/lib:$L/openimageio/lib:$LD_LIBRARY_PATH \
  $L/openimageio/bin/oiiotool --colorconfig $C "$1" --mulc $m,$m,$m,1 --ociodisplay:from=scene_linear sRGB AgX \
  -d uint8 -o "$2"
