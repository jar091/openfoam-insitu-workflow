#!/bin/bash
# Render worker (runs ON a compute node via srun): claims frames of the DLRCJH looks from a
# shared queue (atomic mkdir in <out_root>/claims) and renders them with CyclesPhi until
# <out_root>/ALLGEN exists and no unclaimed frame is left. Any number of workers on any nodes.
# Scenes: <out_root>/<look>/scene/<frame>.xml (written by queue_gen.sh). Output <look>/<frame>.png.
# Usage: worker.sh <out_root> <WxH> <spp> <look...>
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
OUT=$1; RES=$2; SPP=$3; shift 3; LOOKS="$@"
export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
ulimit -c 0
source $P/scripts/env_cyclesphi.sh >/dev/null 2>&1
export OCIO=$P/data/cyclesphi/colormanagement/config_standard.ocio
mkdir -p $OUT/claims
H=$(hostname -s)
while true; do
    got=""
    for look in $LOOKS; do
        for x in $(ls $OUT/$look/scene/*.xml 2>/dev/null | sort -V); do
            b=$(basename ${x%.xml})
            [ -f $OUT/$look/$b.png ] && continue
            mkdir $OUT/claims/${look}_$b 2>/dev/null || continue
            got=$x; break 2
        done
    done
    if [ -z "$got" ]; then
        [ -f $OUT/ALLGEN ] && break
        sleep 15; continue
    fi
    mkdir -p $OUT/$look/log
    t0=$(date +%s.%N)
    if $CYCLES_BIN --device CPU --threads $(nproc) --samples $SPP --width ${RES%x*} --height ${RES#*x} \
        --output $OUT/$look/$b.tmp.png $got > $OUT/$look/log/$b.log 2>&1; then
        mv $OUT/$look/$b.tmp.png $OUT/$look/$b.png
        echo "$b $H $(echo "$(date +%s.%N) - $t0" | bc) s" >> $OUT/$look/log/times.txt
    else
        echo "$b $H FAILED" >> $OUT/$look/log/times.txt; rmdir $OUT/claims/${look}_$b
    fi
done
echo "$H: no work left"
