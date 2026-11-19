# Node-level DiskANN trace

Build with `-DDISKANN_IO_BENCH=ON`. Node tracing is **opt-in** via the environment variable `DISKANN_NODE_TRACE_PATH`; it works with the existing `--io_trace_path` CSV (independent files). Do not use the same path for both traces.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DDISKANN_IO_BENCH=ON
cmake --build build -j8
mkdir -p /mnt/gds/cwd_test/node_trace
export DISKANN_NODE_TRACE_PATH=/mnt/gds/cwd_test/node_trace/nodes.csv
DATASET_CONFIG=/mnt/gds2/cwd_test/diskann_paths.env \
RESULTS_ROOT=/mnt/gds/cwd_test/node_trace/run \
BACKENDS=libaio BEAMS=64 THREAD_COUNTS=1 CACHES=0 L=100 K=10 \
REPEATS=1 CACHE_STATE=warm TRACE=1 RESUME=0 scripts/run_diskann_matrix.sh
python3 scripts/analyze_node_trace.py "$DISKANN_NODE_TRACE_PATH" \
  --out /mnt/gds/cwd_test/node_trace/analysis
```

**Important:** Delete or rename the node CSV before a fresh experiment; the writer appends. A matrix run contains warm-up and measured queries, often with reused query IDs; to avoid mixing runs, run the executable directly once or set a distinct node trace file per process. The matrix command above is useful for a smoke test but **not** a valid per-run analysis when warm-up and measurement are appended to the same CSV.

The event columns are `query_id,batch_id,node_id,offset,event_type,degree,timestamp_ns`.
- ENTRY: selected medoid, not necessarily disk-read.
- EXPAND: node popped from search queue; a real node-level visit, not necessarily SSD I/O.
- CACHE_HIT: expansion served by DiskANN's node cache.
- IO_SUBMIT: expansion selected for a physical read request (software submission; not necessarily one NVMe command).
- NEIGHBORS: adjacency list consumed; `degree` is the **out-degree**, not in-degree. A high-frequency node is not necessarily a structural hub.

The analyzer outputs `node_metrics.csv`, `node_metrics.json`, `node_frequency.csv`, `node_frequency_rank.png`, `node_topk_coverage.png`, and `node_degree_frequency.png`. Frequency is the count of **distinct queries** expanding each node; repeated expansion fraction uses this unique-query count. To quantify actual node-level cross-query *in-flight* overlap, join IO_SUBMIT with per-request completion timestamps, which the current trace does not capture.

Instrumentation is buffered per query and flushed under a mutex. It adds CPU and memory overhead; use an uninstrumented run for baseline performance measurements.
