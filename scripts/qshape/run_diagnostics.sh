#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?set fresh OUT}"
for mode in control breakdown reuse; do
 b=0; r=0
 [[ "$mode" == breakdown ]] && b=1
 [[ "$mode" == reuse ]] && r=1
 OUT="$OUT/$mode" BREAKDOWN="$b" REUSE_STATS="$r" HASH_POLICY=mixed SHARD_STATS=0 MODES=stats bash scripts/qshape/run_sharing.sh
done
