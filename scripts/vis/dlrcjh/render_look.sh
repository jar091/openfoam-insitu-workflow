#!/bin/bash
# Frame-parallel CyclesPhi rendering of a DLRCJH look (login-node driver, all work via srun).
# 1) make_dlrcjh_scene.py writes one XML per VDB (orbit camera from the time index:
#    --frame-from-name --first FIRST --step STEP --nframes NFRAMES) into <out>/scene,
# 2) frames are distributed round-robin over <nodes> x PER_NODE cycles processes
#    (scripts/vis/v2/render_xml.sh; existing PNGs are skipped -> resumable / follow mode).
# Usage: render_look.sh <look> <out_dir> <nodes,..> <WxH> <spp> <vdb...>
#   SCENE_ARGS="..." extra generator args (look parameters, eval'ed: quote ramp specs),
#   PER_NODE=1|2 (threads split). Node entries "cnXXX" use job $JOB (default 5270670),
#   "<jobid>/cnXXX" another job.
P=/mnt/proj2/eu-25-121/milanjaros/openfoam
LOOK=$1; OUT=$2; NODES=$3; RES=$4; SPP=$5; shift 5
FIRST=${FIRST:-0}; STEP=${STEP:-12}; NFRAMES=${NFRAMES:-250}; PER_NODE=${PER_NODE:-1}
IFS=, read -r -a NL <<< "$NODES"
mkdir -p $OUT/scene $OUT/log
# generate the scenes of files without an XML yet (on the first node)
new=(); for f in "$@"; do b=$(basename ${f%.vdb}); [ -f $OUT/scene/$b.xml ] || new+=($f); done
if [ ${#new[@]} -gt 0 ]; then
    n0=${NL[0]}; j0=${JOB:-5270670}; [[ $n0 == */* ]] && { j0=${n0%/*}; n0=${n0#*/}; }
    eval srun --jobid=$j0 --overlap -N1 -n1 -c 8 -w $n0 bash $P/scripts/vis/pyvdb.sh \
        $P/data/cyclesphi/scenes/DLRCJH/make_dlrcjh_scene.py --look $LOOK --outdir $OUT/scene \
        --frame-from-name --first $FIRST --step $STEP --nframes $NFRAMES ${SCENE_ARGS:-} --vdb "${new[@]}" > /dev/null || exit 1
fi
todo=(); for f in "$@"; do b=$(basename ${f%.vdb}); [ -f $OUT/$b.png ] || todo+=($OUT/scene/$b.xml); done
[ ${#todo[@]} -gt 0 ] || { echo "nothing to render"; exit 0; }
N=$(( ${#NL[@]} * PER_NODE )); T=$(( 128 / PER_NODE ))
start=$(date +%s)
for k in $(seq 0 $((N - 1))); do
    mine=(); for i in $(seq $k $N $((${#todo[@]} - 1))); do mine+=(${todo[$i]}); done
    [ ${#mine[@]} -gt 0 ] || continue
    node=${NL[$((k / PER_NODE))]}; job=${JOB:-5270670}
    [[ $node == */* ]] && { job=${node%/*}; node=${node#*/}; }
    srun --jobid=$job --overlap -N1 -n1 -c $T -w $node --export=ALL,THREADS=$T \
        bash $P/scripts/vis/v2/render_xml.sh ${OCIO_CFG:-standard} $RES $SPP $OUT "${mine[@]}" > $OUT/log/proc_${node}_$k.log 2>&1 &
done
wait
echo "rendered ${#todo[@]} frames ($LOOK) on $N processes in $(( $(date +%s) - start )) s -> $OUT"
