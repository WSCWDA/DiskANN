#!/usr/bin/env bash
set -euo pipefail
: "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
OUT=${OUT:-qshape-results}
mkdir -p "$OUT"
for ((r=1;r<=${REPEATS:-5};r++)); do
 for mode in off stats trace; do
  flags=()
  case "$mode" in
   stats) flags=(--qshape-enable 1);;
   trace) flags=(--qshape-enable 1 --qshape-trace 1);;
  esac
  prefix="$OUT/${r}_$mode"
  "$SEARCH_BIN" --data_type "${DATA_TYPE:-uint8}" --dist_fn "${DIST_FN:-l2}" --index_path_prefix "$INDEX_PREFIX" --query_file "$QUERY_FILE" --gt_file "$GT_FILE" --result_path "$prefix" -K "${K:-10}" -L "${L:-100}" -T "${T:-64}" -W "${W:-64}" --num_nodes_to_cache "${CACHES:-0}" --qshape-output-prefix "$prefix" "${flags[@]}" 2>&1 | tee "$prefix.log"
 done
 cmp "$OUT/${r}_off_${L:-100}_idx_uint32.bin" "$OUT/${r}_stats_${L:-100}_idx_uint32.bin"
 cmp "$OUT/${r}_off_${L:-100}_idx_uint32.bin" "$OUT/${r}_trace_${L:-100}_idx_uint32.bin"
done
