#!/bin/bash
# Start render_queue.sh on several nodes of job 5275975 (one srun step per node, background)
# and wait (JOBID overrides the job). Usage: NODES="cn001 cn002 ..." render_all_nodes.sh <ocio> <WxH> <spp> <out_dir> <xml...>
Q=/mnt/proj2/eu-25-121/milanjaros/openfoam/scripts/vis/occdrivaer/render_queue.sh
NODES=${NODES:-"cn001 cn002 cn003 cn004 cn005"}
for n in $NODES; do
    srun --jobid=${JOBID:-5275975} --overlap -N1 -n1 -c 128 -w $n bash $Q "$@" &
    sleep 1
done
wait
