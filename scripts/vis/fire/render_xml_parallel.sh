#!/bin/bash
# Frame-parallel CyclesPhi rendering of ready-made per-frame scene XMLs (make_steckler_scene.py,
# make_jhc_scene.py): one cycles process per node, frames round-robin, existing PNGs skipped.
# Runs from the login node; every node gets one `srun --overlap` step inside its job
# (5270670: cn356-cn358, 5275975: cn516-cn523, cn319-cn321).
# Usage: render_xml_parallel.sh <ocio view> <WxH> <spp> <out_dir> <node,node,...> <scene.xml...>
#   THREADS=<n> per node (default all cores), FORCE=1 re-renders.
set -u
CM=$1; RES=$2; SPP=$3; OUT=$4; NODES=$5; shift 5
R=/mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/vis/v2/render_xml.sh
IFS=, read -r -a NL <<< "$NODES"
N=${#NL[@]}
mkdir -p "$OUT/log"
FILES=("$@")
start=$(date +%s)
for k in $(seq 0 $((N - 1))); do
    mine=()
    for i in $(seq $k $N $((${#FILES[@]} - 1))); do mine+=("${FILES[$i]}"); done
    [ ${#mine[@]} -gt 0 ] || continue
    case ${NL[$k]} in cn35[678]) JOB=5270670 ;; *) JOB=5275975 ;; esac  # job of the node
    srun --jobid=$JOB --overlap -N1 -n1 -c ${THREADS:-128} -w "${NL[$k]}" \
        env HOME=/scratch/project/eu-25-121/milanjaros/openfoam/fakehome THREADS=${THREADS:-128} FORCE=${FORCE:-0} \
        bash $R "$CM" "$RES" "$SPP" "$OUT" "${mine[@]}" > "$OUT/log/node_${NL[$k]}.log" 2>&1 &
done
wait
echo "rendered ${#FILES[@]} frames on $N nodes in $(( $(date +%s) - start )) s -> $OUT"
