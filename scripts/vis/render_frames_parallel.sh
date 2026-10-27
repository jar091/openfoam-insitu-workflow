#!/bin/bash
# Frame-parallel CyclesPhi rendering of a VDB series: one cycles process per node,
# frames distributed round-robin (frame i -> node i mod N). Runs from the login node
# and starts one `srun --overlap` per node inside job 5270670 (no compute on the login node).
#
# Usage: render_frames_parallel.sh <template.xml> <grid> <out_dir> <WxH> <spp> <node,node,...> <vdb files...>
#   The template must be a CyclesPhi template with {VDB_DATA}/{GRID_NAME} placeholders
#   (data/cyclesphi/make_vdb_scene.py [+ scripts/vis/set_tf.py]).
#   Existing PNGs are skipped (FORCE=1 re-renders), so an interrupted run can be resumed.
# Per-node logs: <out_dir>/log/node_<node>.log; per-frame timings in the cycles logs.
set -u
JOB=${JOB:-5270670}
TPL=$1; GRID=$2; OUT=$3; RES=$4; SPP=$5; NODES=$6; shift 6
S=/mnt/proj2/eu-25-121/milanjaros/openfoam/data/cyclesphi/render_vdb_series.sh
IFS=, read -r -a NL <<< "$NODES"
N=${#NL[@]}
mkdir -p "$OUT/log"
FILES=("$@")
start=$(date +%s)
for k in $(seq 0 $((N - 1))); do
    mine=()
    for i in $(seq $k $N $((${#FILES[@]} - 1))); do mine+=("${FILES[$i]}"); done
    [ ${#mine[@]} -gt 0 ] || continue
    srun --jobid=$JOB --overlap -N1 -n1 -c 128 -w "${NL[$k]}" bash -c '
        export HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome
        S=$1; TPL=$2; GRID=$3; OUT=$4; RES=$5; SPP=$6; shift 6
        for f in "$@"; do TEMPLATE=$TPL bash $S "$f" $GRID $OUT $RES $SPP; done' \
        _ "$S" "$TPL" "$GRID" "$OUT" "$RES" "$SPP" "${mine[@]}" > "$OUT/log/node_${NL[$k]}.log" 2>&1 &
done
wait
echo "rendered ${#FILES[@]} frames on $N nodes in $(( $(date +%s) - start )) s -> $OUT"
