# P3.2-A1
Exact cumulative frequency per shard, updated once per acquire including bypass and joins. Strict candidate > every required LRU victim, ties reject. Publish-time decision; no aging. History cleared at quiescent file boundaries. Exact metadata is unbounded by READY budget; max observed shard entries is not total metadata. Allocation failure skips frequency update and is flagged by validator. Gate accepts count comparison success, not necessarily admission. No global lock. Tracking timing only with READY diagnostics.

Run from repository root:
```bash
g++ -std=c++14 -O2 -pthread -Iinclude tests/qshape/test_frequency.cpp -o /tmp/test_frequency
/tmp/test_frequency
cmake --build build-qshape -j$(nproc)
# Set SEARCH_BIN INDEX_PREFIX QUERY_FILE GT_FILE and fresh OUT as in prior experiments.
bash scripts/qshape/run_frequency_ablation.sh
python3 scripts/qshape/validate_frequency.py --out "$OUT"
```
Repeat with fresh OUT and READY_STATS=1, validator --ready-stats. Separate diagnostic QPS. Compare original bounded-local and similarity LRU. Target >=90% admission reduction, no read or tail regression, improved E2E QPS. These are research goals, not correctness assertions. Additional concurrency, variable-length and sanitizer tests remain required.
