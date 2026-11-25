#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
[[ ! -e "$OUT" ]] || { echo "OUT must be fresh"; exit 1; }
for retention in none bounded; do
 OUT="$OUT/$retention" RETENTION="$retention" MODES=stats BREAKDOWN=0 REUSE_STATS=0 bash scripts/qshape/run_sharing.sh
done
