#!/bin/bash
# Run a python script with the bundled python 3.13 + openvdb/numpy of the CyclesPhi lib bundle.
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
L=/mnt/proj2/eu-25-121/milanjaros/openfoam/install/cyclesphi_libs/linux_x64
LD_LIBRARY_PATH=$L/openvdb/lib:$L/tbb/lib:$LD_LIBRARY_PATH PYTHONPATH=$L/python/lib/python3.13/site-packages \
    exec $L/python/bin/python3.13 -I "$@"
