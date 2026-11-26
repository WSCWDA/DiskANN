# P3.3-A2.2 A/B/C
Offline only. Requires NumPy and validated A2.1 formal directory. Reads D0/D1/D2 repeat 1 receipts, extracts D0 logical access multiset and verifies A2.1 digest before deduplication. Group size 256, including final partial group. Rank by distinct query frequency descending, offset ascending ties. Full-trace static top-K is an offline reference, not dynamic CMS or online cache. 21 configurations, no statistical repeats because deterministic. Signed gain preservation only when raw gain positive. Frequency bands report positive and negative contributions separately.
```bash
python3 scripts/qshape/test_residual_locality.py -v
python3 scripts/qshape/run_residual_overlap.py --source "$ROOT/p33a2_formal" --out "$ROOT/p33a2_overlap"
python3 scripts/qshape/validate_residual_overlap.py --source "$ROOT/p33a2_formal" --out "$ROOT/p33a2_overlap"
```
Use a fresh output directory. Upload overlap.csv, gains.csv, frequency_bands.csv, extraction_manifest.json, validation_summary.json and logs. Keep compact NPZ and per-region/group CSVs local. Validator recomputes outputs from compact sets, not raw multiset; extraction checks raw digest. No independent historical cache model or runtime attribution in this stage.
