#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
[[ ! -e "$OUT" ]] || { echo "OUT exists"; exit 1; }
root="$OUT"; mkdir -p "$root"
export REGION_TRACE=1 READY_STATS=1 BREAKDOWN=1 REUSE_STATS=0 SHARD_STATS=0
export READY_BUDGET=16777216 BUDGET=67108864 HASH_POLICY=mixed
for ((r=1;r<=${REPEATS:-3};r++)); do
 for case in original_bounded-local_256_512 similarity_bounded-local_256_512 original_lru_256_512 similarity_lru_256_512 similarity_lru_64_512 similarity_lru_256_2048; do
  IFS=_ read -r order policy g p <<< "$case"
  OUT="$root/$case/$r" ORDERS="$order" SHARING_MODES=inflight RETENTION="$policy" GROUP_SIZE="$g" CANDIDATE_POOL="$p" REPEATS=1 MODES=stats bash scripts/qshape/run_sharing.sh
 done
done
