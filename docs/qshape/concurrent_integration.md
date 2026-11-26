# C2-D concurrent integration
All ten configurations use QShape stats instrumentation; A0 is the instrumented baseline, not a pristine binary. Run on isolated SSD with same immutable index and fixed 10k SIFT1M queries. No production changes. Smoke is one full repeat; formal three randomized repeats. Resume verifies manifest and completed receipts; failed incomplete cases rerun. Index content is not hashed; keep index unchanged. No device statistics automatically collected. Timing excludes process startup and result writing. Existing validator checks query conservation, budgets, frequency, recall, exact output hashes and logical request equality. Paired comparisons are descriptive, not statistical significance.
```bash
g++ -std=c++14 -O2 -pthread -Iinclude tests/qshape/test_concurrent_integration.cpp -o /tmp/test_concurrent_integration
timeout 60 /tmp/test_concurrent_integration
python3 scripts/qshape/test_concurrent_integration.py -v
# export SEARCH_BIN INDEX_PREFIX QUERY_FILE GT_FILE
python3 scripts/qshape/concurrent_integration.py run --out "$OUT" --repeats 1
# separate OUT for formal
python3 scripts/qshape/concurrent_integration.py run --out "$OUT" --repeats 3
python3 scripts/qshape/concurrent_integration.py validate --out "$OUT"
```
Compile unit separately with -fsanitize=address,undefined and -fsanitize=thread; run under timeout. Tests cover same-key sharing, independent misses, READY hit, reset, owner error; not exhaustive eviction stress or exact CMS count verification. Retain logs. Outputs integration_metrics.csv, integration_summary.csv, integration_paired.csv. Freeze based on real E2E QPS, recall, tails, reads and memory; no automatic winner.
