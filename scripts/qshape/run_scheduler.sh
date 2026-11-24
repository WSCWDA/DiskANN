#!/usr/bin/env bash
set -euo pipefail
: "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
OUT=${OUT:-qshape-p12}
mkdir -p "$OUT"
for g in ${GROUP_SIZES:-64 128 256}; do
 for ((r=1;r<=${REPEATS:-5};r++)); do
  for mode in stats trace; do
   trace=0; [[ "$mode" == trace ]] && trace=1
   for policy in original similarity; do
    for scheduler in reorder group-aware; do
     prefix="$OUT/g${g}_${r}_${policy}_${scheduler}_${mode}"
     "$SEARCH_BIN" --data_type "${DATA_TYPE:-uint8}" --dist_fn "${DIST_FN:-l2}" --index_path_prefix "$INDEX_PREFIX" --query_file "$QUERY_FILE" --gt_file "$GT_FILE" --result_path "$prefix" -K "${K:-10}" -L "${L:-100}" -T "${T:-64}" -W "${W:-64}" --num_nodes_to_cache "${CACHES:-0}" --qshape-enable 1 --qshape-trace "$trace" --qshape-grouping "$policy" --qshape-group-size "$g" --qshape-candidate-pool "${POOL:-512}" --qshape-scheduler "$scheduler" --qshape-lookahead "${LOOKAHEAD:-4}" --qshape-output-prefix "$prefix" 2>&1 | tee "$prefix.log"
     for suffix in idx_uint32 dists_float; do
      cmp "$OUT/g${g}_${r}_original_reorder_${mode}_${L:-100}_${suffix}.bin" "${prefix}_${L:-100}_${suffix}.bin"
     done
    done
   done
  done
 done
done
