# P3.3-A1 fixed-order characterization
No production changes. Run from repository root, with SEARCH_BIN, INDEX_PREFIX, QUERY_FILE, GT_FILE and DATA_TYPE=float exported. Use the same float binary/index as C2-D. Source must be the completed three-repeat C2-D formal directory with A7 receipts and manifest policy mapping.

```bash
python3 scripts/qshape/test_grouping_characterization.py -v
python3 scripts/qshape/grouping_characterization.py prepare --source "$ROOT/p32b2c2d_formal" --out "$ROOT/p33a1_order"
python3 scripts/qshape/grouping_characterization.py run --out "$ROOT/p33a1_smoke" --permutation "$ROOT/p33a1_order/similarity_order.txt" --repeats 1
python3 scripts/qshape/grouping_characterization.py validate --out "$ROOT/p33a1_smoke"
python3 scripts/qshape/grouping_characterization.py run --out "$ROOT/p33a1_formal" --permutation "$ROOT/p33a1_order/similarity_order.txt" --repeats 3
python3 scripts/qshape/grouping_characterization.py validate --out "$ROOT/p33a1_formal"
```
Z0–Z3: original/random/similarity/oracle with CMS. Z4–Z7 same without retention. Sharing on throughout. Oracle means precomputed similarity, not future trace. T64 W64 L100 K10 G256 P512 seed42, static cache zero. Randomized within each repeat. No simultaneous runners in one output directory. Resume requires identical manifest and receipts. Use new output directory if inputs change. Index prefix recorded but index contents not hashed. Source manifest lacks data type; verify source was float separately. Identical permutation does not guarantee identical runtime schedule.

Outputs grouping_metrics.csv, grouping_summary.csv, grouping_paired.csv. grouping_ms is computation for similarity and load/validation for oracle (includes setup). full_precomputed_ms adds paired online grouping cost to precomputed E2E as an estimate, not a separately timed run. Historical source costs in provenance. PASS requires 8/24 valid runs, exact permutation for similarity/oracle, fixed random order, recall/results/logical requests equality, conservation and budgets. No performance threshold for characterization. Device reads not measured. Logs per case. Pack output directories and unit logs. No C++ rebuild required if existing binary supports oracle.
