# C2-C trace-driven retention
Reuse D3 region traces (original_lru_256_512 and similarity_lru_256_512, same repeat). Require complete query/meta/region CSVs, zero drops, all logical access types, per-query region multiset equality. Sort by timestamp then query ID and sequence; this is observed event order, not a causal concurrent simulation. Only 4KiB aligned regions. Preserve physical page IDs (offset/4096), no dense remapping. Verify original search result hashes with validate_regions.py before preparation. Use the same index/query set and parameters. Smoke prefixes are not matched multisets after truncation and are correctness-only. Full replay has 18 runs, 3 timing repeats of each fixed stream/policy, not independent trace samples. No real SSD or sharing. No production changes.
```bash
g++ -std=c++14 -O3 -pthread -Iinclude tests/qshape/benchmark_retention_trace.cpp -o build-qshape/benchmarks/benchmark_retention_trace
python3 scripts/qshape/test_retention_trace.py -v
python3 scripts/qshape/retention_trace.py prepare --original "$ORIGINAL" --similarity "$SIMILARITY" --out "$OUT"
python3 scripts/qshape/retention_trace.py run --bench build-qshape/benchmarks/benchmark_retention_trace --out "$OUT"
python3 scripts/qshape/retention_trace.py validate --out "$OUT"
```
ORIGINAL/SIMILARITY are stems ending _L100_run0, without suffix. For smoke use separate OUT, prepare --limit 20000, run --repeats 1 --mode correctness. Outputs trace_metrics.csv, trace_summary.csv, interaction.json. Positive interaction is descriptive for these fixed streams, not proof of causal synergy. Negative interaction does not trigger new algorithm work. Run directory is intentionally fresh-only; failed runs require a new prepared directory.
