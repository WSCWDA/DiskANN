# A2.2-D1/D2
Run offline with validated A2.1 and A2.2 directories. All 18 traces, 12 within-repeat comparisons (random and similarity vs original, with/without retention). Same-query joins separate from cross-query same-group joins. Static residual uses fixed top4096 for CMS cases, not actual residency. Quadrants are signed region-level associations, not causal matching. No temporal attribution. Keep all runs; timing outliers do not invalidate count conservation.
```bash
python3 scripts/qshape/test_runtime_attribution.py -v
python3 scripts/qshape/run_runtime_attribution.py --source "$ROOT/p33a2_formal" --static "$ROOT/p33a2_overlap" --out "$ROOT/p33a2_runtime"
python3 scripts/qshape/validate_runtime_attribution.py --out "$ROOT/p33a2_runtime"
```
Fresh output directory required. Validator checks compact arrays and aggregate conservation, not independent raw trace replay. Upload CSVs, manifests, validation and test logs; retain NPZs locally.
