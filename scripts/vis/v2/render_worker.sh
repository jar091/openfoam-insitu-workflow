#!/bin/bash
# Follow-mode / batch render worker for the v2 animations (runs on one compute node).
# Dynamic work queue shared by all workers: items (frame, shot) in frame order; an item is
# taken when its VDB is complete (no .tmp), its PNG is missing and the claim directory
# <R>/claims<TAG>/<shot>_<frame> can be created (atomic mkdir). New workers can join any time.
# Exits when the solver log has "End"/FATAL and no unclaimed item is left.
# Usage: render_worker.sh <solver_log> <spp> <WxH> <shot...>     (CLAIMTAG=x for a new claim set)
# Env: VER (v2|v3), FIRST, STEP, NF (frame list), defaults = v2 series
VER=${VER:-v2}; FIRST=${FIRST:-193010}; STEP=${STEP:-10}; NF=${NF:-260}
R=/scratch/project/eu-25-121/milanjaros/openfoam/renders/pitzDaily3D/$VER
V=/scratch/project/eu-25-121/milanjaros/openfoam/runs/pitzDaily3D/62M/VDB_$VER
W=/mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/vis/v2/render_xml.sh
LOG=$1; SPP=$2; RES=$3; shift 3; SHOTS="$@"
C=$R/claims${CLAIMTAG:-}; mkdir -p $C
while true; do
    ended=0; grep -qE "^End|FATAL" $LOG && ended=1
    did=0; pending=0
    for i in $(seq $FIRST $STEP $((FIRST + STEP * (NF - 1)))); do
        for s in $SHOTS; do
            [ -f $R/$s/pitz_$i.png ] && continue
            [ -f $V/pitz_$i.vdb ] || { pending=1; continue; }
            mkdir $C/${s}_$i 2>/dev/null || continue
            bash $W filmic_mhc $RES $SPP $R/$s $R/$s/scene/pitz_$i.xml
            did=1; break 2
        done
    done
    [ $did = 1 ] && continue
    [ $ended = 1 ] && { echo "$(hostname -s): no work left"; break; }
    sleep 10
done
