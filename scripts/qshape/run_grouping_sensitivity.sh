#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
[[ ! -e "$OUT" ]] || { echo "OUT exists"; exit 1; }
root="$OUT"
mkdir -p "$root"
export READY_BUDGET=16777216 BUDGET=67108864 HASH_POLICY=mixed
export READY_STATS=0 BREAKDOWN=0 REUSE_STATS=0 SHARD_STATS=0
for ((r=1;r<=${REPEATS:-3};r++)); do
 while read -r g p order retention; do
  OUT="$root/g${g}_p${p}/$retention/$r" GROUP_SIZE="$g" CANDIDATE_POOL="$p" ORDERS="$order" SHARING_MODES=inflight RETENTION="$retention" REPEATS=1 MODES=stats bash scripts/qshape/run_sharing.sh
 done < <(python3 - "$r" "${GROUP_SIZES:-64 128 256 512}" "${POOL_SIZES:-512}" <<'PY'
import sys, random
r=int(sys.argv[1])
cases=[(g,512,'similarity',p) for g in map(int,sys.argv[2].split()) for p in ('none','bounded-local','lru')]
cases += [(256,pool,'similarity',p) for pool in map(int,sys.argv[3].split()) if pool!=512 for p in ('none','bounded-local','lru')]
cases += [(256,512,'original',p) for p in ('none','bounded-local','lru')]
random.Random(42+r).shuffle(cases)
for c in cases: print(*c)
PY
 )
done
