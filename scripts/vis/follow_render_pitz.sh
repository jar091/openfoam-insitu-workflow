#!/bin/bash
# Follow a running mesioVDB export and render new frames with CyclesPhi while the
# solver is still running (login-node driver; all work runs via srun inside the job).
# Each round: (1) copy grid b of every new VDB with background 1 (unburnt) into BGDIR
# (vdb_set_background.py, on CONV_NODE), (2) render all converted frames that have no
# PNG yet, frame-parallel on NODES (render_frames_parallel.sh skips existing PNGs).
# Stops when the solver log contains "End" (or FATAL) and no new frames are left.
# Usage: follow_render_pitz.sh <vdb_dir> <solver_log> <template.xml> <out_dir> <nodes> [WxH] [spp]
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
VDB=$1; LOG=$2; TPL=$3; OUT=$4; NODES=$5; RES=${6:-1920x1080}; SPP=${7:-128}
BGDIR=${BGDIR:-/scratch/project/eu-25-121/milanjaros/openfoam/renders/pitzDaily3D/vdb_b_bg1}
CONV_NODE=${CONV_NODE:-cn358}
GRID=${GRID:-b}; BG=${BG:-1}
mkdir -p $BGDIR $OUT
while true; do
    done_run=0; grep -qE "^End|FATAL" $LOG && done_run=1
    new=()
    for f in $(ls $VDB/*.vdb 2>/dev/null | sort -V); do
        [ -f $BGDIR/$(basename $f) ] || new+=($f)
    done
    if [ ${#new[@]} -gt 0 ]; then
        srun --jobid=5270670 --overlap -N1 -n1 -c 16 -w $CONV_NODE bash -c '
            P=$1; GRID=$2; BG=$3; D=$4; shift 4
            for f in "$@"; do bash $P/scripts/vis/pyvdb.sh $P/scripts/vis/vdb_set_background.py $f $GRID $BG $D/$(basename $f) >/dev/null; done' \
            _ $P $GRID $BG $BGDIR "${new[@]}"
    fi
    todo=()
    for f in $(ls $BGDIR/*.vdb 2>/dev/null | sort -V); do
        b=$(basename ${f%.vdb}); [ -f $OUT/$b.png ] || todo+=($f)
    done
    if [ ${#todo[@]} -gt 0 ]; then
        bash $P/scripts/vis/render_frames_parallel.sh $TPL $GRID $OUT $RES $SPP $NODES "${todo[@]}"
    elif [ $done_run = 1 ]; then
        echo "all frames rendered"; break
    else
        sleep 30
    fi
done
