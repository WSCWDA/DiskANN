# P3.2-B2-C2-B1
Reuse C2-A binary; no production changes. 64 shards, depth 4, uint32, 4 KiB, READY 16 MiB, single thread, sharing off. Formal: 100K/1M/10M universe, 10M accesses, uniform/Zipf 1, none/first-fill/LRU/exact and CMS 64/256/512/1024/2048 KiB, seeds 42–44, perf only (162 runs). Pilot uses 1M accesses (54 runs with one repeat); smoke uses 10K universe and 20K accesses (18 runs with one repeat).
Build: g++ -std=c++14 -O3 -pthread -Iinclude tests/qshape/benchmark_retention.cpp -o /tmp/benchmark_retention
Test: python3 scripts/qshape/test_retention_capacity.py
Run: OUT=/tmp/b1-smoke BENCH_BIN=/tmp/benchmark_retention PROFILE=smoke REPEATS=1 bash scripts/qshape/run_retention_capacity.sh
Validate: python3 scripts/qshape/validate_retention_capacity.py --out /tmp/b1-smoke
Analyze: python3 scripts/qshape/analyze_retention_capacity.py --out /tmp/b1-smoke
Resume with identical arguments and binary; receipt hashes and row checks required to skip. Exclusive Linux flock. Timeout and retry configurable; failed runs logged, no completion marker until full validation. If cross-case input mismatch occurs, inspect and remove affected receipts before retry. Python >=3.8. Commit and tracked dirty status recorded, binary SHA recorded; these do not prove binary was built from that commit. Use clean checkout and rebuild. No parallel runs on same machine recommended.
Metrics paired by seed, sample SD across seeds; undefined ratios blank. Incremental ratio only if exact beats LRU, may be unstable for tiny positive denominator. Pressure uses observed distinct keys and actual counter bytes. Perf unused eviction/timing fields are not diagnostic measurements. Mock backend throughput not SSD IOPS. No equal-total-memory claim. C2-B2/B3 and diagnostics deferred. Tests cover matrix, row invariants, receipt corruption and ratio edge cases; actual runner interruption and C++ execution require target-machine validation.

## B2 Skew Sensitivity
Use the original B1 binary (identical SHA256), clean checkout, same machine and settings. No production changes. Run skew-smoke (14 cases, one seed), then skew (42 cases, three seeds, 1M universe, 10M accesses, alpha .8/1.2). Reuse 42 validated B1 formal rows for alpha 0/1. Example:
```bash
OUT=/tmp/b2-smoke BENCH_BIN=/path/to/original/benchmark_retention PROFILE=skew-smoke REPEATS=1 bash scripts/qshape/run_retention_capacity.sh
OUT=/tmp/b2-formal BENCH_BIN=/path/to/original/benchmark_retention PROFILE=skew REPEATS=3 bash scripts/qshape/run_retention_capacity.sh
python3 scripts/qshape/validate_retention_capacity.py --out /tmp/b2-formal
python3 scripts/qshape/analyze_retention_skew.py --b1 /path/to/b1-formal --out /tmp/b2-formal
```
Outputs skew_metrics.csv (84), skew_summary.csv (28), skew_candidates.csv (20), skew_provenance.csv (84). Full historical validation, binary equality, clean commits, ancestor check and tool-only diff required. If binary differs, do not bypass checks; recover original binary or rerun historical cases under matched conditions. Fingerprints are compared within identical inputs, not across different skew values. Reference gain below .001 (0.1 percentage points) makes incremental utility undefined for selection; this is an engineering threshold, not significance. Candidate pass requires all three seeds to satisfy 95% total, 90% incremental, 90% admission reduction, 95% processing efficiency. Low reference gain is not a capacity failure. No automatic algorithm changes. Same hardware/environment must be confirmed manually. B2 ends synthetic sweeps.
