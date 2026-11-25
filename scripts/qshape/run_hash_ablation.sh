#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?set OUT to a fresh directory}"
for hash in legacy mixed; do
 for profile in 0 1; do
  OUT="$OUT/${hash}_${profile}" HASH_POLICY="$hash" SHARD_STATS="$profile" MODES=stats bash scripts/qshape/run_sharing.sh
 done
done
