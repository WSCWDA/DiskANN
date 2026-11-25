#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?set fresh output directory}"
[[ ! -e "$OUT" ]] || { echo "OUT already exists"; exit 1; }
for ((r=1;r<=${REPEATS:-5};r++)); do
 for policy in $(python3 -c 'import random,sys; a=["none","bounded","bounded-local","lru"]; random.Random(42+int(sys.argv[1])).shuffle(a); print(" ".join(a))' "$r"); do
  OUT="$OUT/$policy/$r" REPEATS=1 MODES=stats CACHE_ONLY=1 RETENTION="$policy" bash scripts/qshape/run_sharing.sh
 done
done
