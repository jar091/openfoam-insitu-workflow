#!/bin/bash
# Login-node driver of the render queue: writes the per-frame scene XMLs of every new VDB for
# each look (make_dlrcjh_scene.py on GEN_NODE via srun) until the solver log has "End", then
# touches <out_root>/ALLGEN so that the workers (worker.sh) stop when the queue is empty.
# Usage: queue_gen.sh <vdb_dir> <solver_log> <out_root> [look...]
#   GEN_NODE="job/node", FIRST/STEP/NFRAMES (orbit), EXTRA="..." look args appended
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
VDB=$1; LOG=$2; OUT=$3; shift 3; LOOKS=${@:-flame vortex combined}
source $P/data/cyclesphi/scenes/DLRCJH/looks.sh
GN=${GEN_NODE:-5275975/cn316}
while true; do
    done_run=0; grep -qE "^End$|FOAM FATAL" $LOG && done_run=1
    for look in $LOOKS; do
        case $look in flame) A=$DLR_FLAME ;; vortex) A=$DLR_VORTEX ;; combined) A=$DLR_COMBINED ;; esac
        mkdir -p $OUT/$look/scene
        new=(); for f in $(ls $VDB/*.vdb 2>/dev/null | sort -V); do
            [ -f $OUT/$look/scene/$(basename ${f%.vdb}).xml ] || new+=($f); done
        [ ${#new[@]} -gt 0 ] || continue
        eval srun --jobid=${GN%/*} --overlap -N1 -n1 -c 2 -w ${GN#*/} bash $P/scripts/vis/pyvdb.sh \
            $P/data/cyclesphi/scenes/DLRCJH/make_dlrcjh_scene.py --look $look --outdir $OUT/$look/scene \
            --frame-from-name --first ${FIRST:-40} --step ${STEP:-40} --nframes ${NFRAMES:-225} \
            $DLR_COMMON $A $DLR_RENDER ${EXTRA:-} --vdb "${new[@]}" > /dev/null
        echo "$(date +%T) $look: +${#new[@]} scenes"
    done
    [ $done_run = 1 ] && { touch $OUT/ALLGEN; echo "$(date +%T) solver ended, ALLGEN"; break; }
    sleep 30
done
