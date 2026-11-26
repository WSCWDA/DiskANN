#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
root="$OUT"; mkdir "$root"
export T=64 W=64 L=100 K=10 CACHES=0 GROUP_SIZE=256 CANDIDATE_POOL=512 BUDGET=67108864 READY_BUDGET=16777216 HASH_POLICY=mixed FREQUENCY_DEPTH=4 FREQUENCY_MODE=cms FREQUENCY_SHADOW=1 RETENTION=frequency SHARING_MODES=inflight MODES=stats CACHE_ONLY=0 READY_STATS=0 BREAKDOWN=0 REUSE_STATS=0 REGION_TRACE=0 SHARD_STATS=0
repeats="${REPEATS:-3}"
for ((r=1;r<=repeats;r++)); do
 for b in 64 256 512 2048; do
  for o in original similarity; do
   OUT="$root/${b}k/$r/$o" ORDERS="$o" REPEATS=1 FREQUENCY_BUDGET="$((b*1024))" bash "$(dirname "$0")/run_sharing.sh"
  done
 done
done
echo "$repeats" > "$root/runner_complete"
