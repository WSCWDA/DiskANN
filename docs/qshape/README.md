# QShape P0 initial instrumentation
Base 78256bbab4685e1774e78d331e081a153be26823. Linux only. No grouping, sharing or cache changes.
Build with existing DiskANN CMake instructions. Run scripts/qshape/run_baseline.sh with SEARCH_BIN, INDEX_PREFIX, QUERY_FILE, GT_FILE set. OUT, T, W, L, K, CACHES, REPEATS optional. Compare with a separately built cpp_main binary. Record hardware and cache state.
--qshape-enable 1 enables counters; --qshape-trace 1 stores events in memory and writes CSV after search. Trace runs are diagnostic, not throughput measurements.
Query IDs are original IDs; execution_id is identity, not dispatch rank. arrival is batch start. Logical reads count uncached frontier nodes; submitted reads include reranking. Accepted libaio IOCBs are not NVMe commands. Completion timestamps are batch harvest observations, not hardware completion times. Request IDs are unique within each query. Completion errors count short reads and nonzero res2 without changing baseline error handling. Warmup and cache population excluded. Trace memory scales with event count.
Pending: node/beam/group mapping, device counters, target build and benchmark validation.
