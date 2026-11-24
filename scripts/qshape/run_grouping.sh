#!/usr/bin/env bash
set -euo pipefail
: "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
OUT=${OUT:-qshape-p1}
mkdir -p "$OUT"
for ((r=1;r<=${REPEATS:-5};r++)); do
 for policy in original random similarity; do
  for mode in stats trace; do
   trace=0; [[ "$mode" == trace ]] && trace=1
   prefix="$OUT/${r}_${policy}_${mode}"
   "$SEARCH_BIN" --data_type "${DATA_TYPE:-uint8}" --dist_fn "${DIST_FN:-l2}" --index_path_prefix "$INDEX_PREFIX" --query_file "$QUERY_FILE" --gt_file "$GT_FILE" --result_path "$prefix" -K "${K:-10}" -L "${L:-100}" -T "${T:-64}" -W "${W:-64}" --num_nodes_to_cache "${CACHES:-0}" --qshape-enable 1 --qshape-trace "$trace" --qshape-grouping "$policy" --qshape-group-size "${GROUP_SIZE:-64}" --qshape-candidate-pool "${POOL:-256}" --qshape-seed "$((${SEED:-42}+r-1))" --qshape-output-prefix "$prefix" 2>&1 | tee "$prefix.log"
   cmp "$OUT/${r}_original_stats_${L:-100}_idx_uint32.bin" "${prefix}_${L:-100}_idx_uint32.bin"
  done
 done
done
