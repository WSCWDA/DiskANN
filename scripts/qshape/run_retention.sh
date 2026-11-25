#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
[[ ! -e "$OUT" ]] || { echo "OUT must be fresh"; exit 1; }
for ((r=1;r<=${REPEATS:-5};r++)); do
 for policy in ${POLICIES:-none bounded ttl lru ttl-lru}; do
  OUT="$OUT/$policy/$r" REPEATS=1 RETENTION="$policy" MODES=stats REUSE_STATS=0 bash scripts/qshape/run_sharing.sh
 done
done
