#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
root="$OUT"
[[ ! -e "$root" ]] || { echo "OUT exists"; exit 1; }
mkdir -p "$root"
for ((r=1;r<=${REPEATS:-3};r++)); do
 for mode in exact cms; do
  OUT="$root/$mode/$r" FREQUENCY_MODE="$mode" RETENTION=frequency CACHE_ONLY=1 REPEATS=1 MODES=stats bash "$(dirname "$0")/run_sharing.sh"
 done
done
