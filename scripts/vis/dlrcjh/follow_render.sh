#!/bin/bash
# Follow a running DLRCJH mesioVDB export and render the three looks frame-parallel
# (login-node driver; all work via srun). Each round renders every VDB without a PNG for
# the looks in LOOKS (render_look.sh skips finished frames). The node list is re-read from
# <nodes_file> every round (one line "job/node,job/node,..."), so nodes can be added while
# it runs. Stops when the solver log has "End" and every look has all frames.
# Usage: follow_render.sh <vdb_dir> <solver_log> <out_root> <nodes_file> [WxH=1920x1080] [spp=24]
#   LOOKS="flame vortex combined", EXTRA="..." (look args appended, e.g. --qrange for 3M),
#   FIRST/STEP/NFRAMES (camera orbit, see render_look.sh), PATTERN (default *.vdb)
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
VDB=$1; LOG=$2; OUT=$3; NF=$4; RES=${5:-1920x1080}; SPP=${6:-24}
source $P/data/cyclesphi/scenes/DLRCJH/looks.sh
LOOKS=${LOOKS:-flame vortex combined}
while true; do
    done_run=0; grep -qE "^End$|FOAM FATAL" $LOG && done_run=1
    files=$(ls $VDB/${PATTERN:-*.vdb} 2>/dev/null | sort -V)
    nodes=$(head -1 $NF)
    left=0
    for look in $LOOKS; do
        case $look in flame) A=$DLR_FLAME ;; vortex) A=$DLR_VORTEX ;; combined) A=$DLR_COMBINED ;; esac
        todo=(); for f in $files; do [ -f $OUT/$look/$(basename ${f%.vdb}).png ] || todo+=($f); done
        left=$((left + ${#todo[@]}))
        [ ${#todo[@]} -gt 0 ] || continue
        echo "$(date +%T) $look: ${#todo[@]} frames on $nodes"
        SCENE_ARGS="$DLR_COMMON $A $DLR_RENDER ${EXTRA:-}" bash $P/scripts/vis/dlrcjh/render_look.sh \
            $look $OUT/$look $nodes $RES $SPP "${todo[@]}"
    done
    if [ $left = 0 ]; then
        [ $done_run = 1 ] && { echo "$(date +%T) all frames rendered"; break; }
        sleep 30
    fi
done
