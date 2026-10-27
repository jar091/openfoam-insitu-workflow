#!/bin/bash
# Follow a running mesioVDB export: every round, write scene XMLs for all new VDB files
# (mesioVDB renames <file>.tmp -> <file>.vdb when complete) and render the frames without a PNG.
# Stops after a round in which the solver log contains "End" and nothing was left to render.
# Usage: follow_render.sh <scene_script> <vdb_dir> <solver_log> <out_dir> <WxH> <spp> <nodes>
SCN=$1; VDB=$2; LOG=$3; OUT=$4; RES=$5; SPP=$6; NODES=$7
R=/mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/vis/fire/render_xml_parallel.sh
mkdir -p $OUT/scene $OUT/png
while true; do
    done_sim=0; grep -q '^End' $LOG && done_sim=1
    new=()
    for f in $VDB/*.vdb; do b=$(basename ${f%.vdb}); [ -f $OUT/scene/$b.xml ] || new+=($f); done
    [ ${#new[@]} -gt 0 ] && bash $SCN $OUT/scene "${new[@]}" > /dev/null
    todo=()
    for x in $OUT/scene/*.xml; do b=$(basename ${x%.xml}); [ -f $OUT/png/$b.png ] || todo+=($x); done
    if [ ${#todo[@]} -gt 0 ]; then
        echo "$(date +%T) rendering ${#todo[@]} frames"
        bash $R standard $RES $SPP $OUT/png $NODES "${todo[@]}"
    elif [ $done_sim = 1 ]; then
        echo "$(date +%T) all frames rendered"; break
    else
        sleep 60
    fi
done
