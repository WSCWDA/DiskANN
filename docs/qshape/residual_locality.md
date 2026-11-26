# P3.3-A2.1 Region trace collection
D0/D1/D2 original/random/precomputed without retention; D3/D4/D5 same with CMS512KiB. Sharing on. A1 float settings and fixed permutation. Trace, ready stats and breakdown enabled; performance diagnostic only. No production changes. 4KiB regions only. One run in memory, potentially several GiB; raw CSVs stay local. Event limit4096; zero dropped required. Source A1 formal directory must retain Z0 raw files and receipt. Index prefix checked, index content not hashed. Same per-query region multiset required across trace runs; not compared to A1 region multiset (A1 has no region trace). A1 result hashes and recall checked. No temporal sharing causality claimed.
```bash
python3 scripts/qshape/test_residual_trace.py -v
python3 scripts/qshape/run_residual_locality.py run --source "$ROOT/p33a1_formal" --permutation "$ROOT/p33a1_order/similarity_order.txt" --out "$ROOT/p33a2_smoke" --repeats 1
python3 scripts/qshape/run_residual_locality.py run --source "$ROOT/p33a1_formal" --permutation "$ROOT/p33a1_order/similarity_order.txt" --out "$ROOT/p33a2_formal" --repeats 3
python3 scripts/qshape/validate_residual_locality.py --out "$ROOT/p33a2_formal"
```
Export SEARCH_BIN INDEX_PREFIX QUERY_FILE GT_FILE DATA_TYPE=float as in A1. Resume same manifest, receipts and inputs. Upload only manifest.json, trace_metrics.csv, validation_summary.json and unit/validation logs. Keep all raw traces for A2.2.
