#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?set fresh output directory}"
[[ ! -e "$OUT" ]] || { echo "OUT already exists"; exit 1; }
for ((r=1;r<=${REPEATS:-5};r++)); do
 for policy in none lru; do
  OUT="$OUT/$policy/$r" REPEATS=1 MODES=stats CACHE_ONLY=1 RETENTION="$policy" bash scripts/qshape/run_sharing.sh
 done
done
