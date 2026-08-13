# Real DiskANN I/O Path Benchmark

This benchmark records and replays only I/O requests emitted by the C++ `PQFlashIndex::cached_beam_search` path. It does not synthesize offsets, request sizes, query popularity, or cache outcomes, and it does not modify candidate selection or graph traversal.

## Build

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DDISKANN_IO_BENCH=ON
cmake --build build -j
```

`liburing` is detected independently. If unavailable, all non-io_uring CPU paths still build. CUDA and cuFile are not dependencies of the CPU benchmark.

## Data and index

```bash
scripts/download_real_datasets.sh
scripts/build_real_indexes.sh
```

These scripts download the official TexMex SIFT1M and GIST1M vectors and invoke DiskANN's own converters and `build_disk_index` application. They do not generate vectors or index files.

Existing datasets may remain outside the repository. For example, with SIFT1M
under `/home/cwd/dataset/sift_1M`:

```bash
export DATASET_ROOT=/home/cwd/dataset
scripts/build_real_indexes.sh sift
```

The script derives `SIFT_DIR=${DATASET_ROOT}/sift_1M`, reuses existing `.fbin`
files, and computes `sift_groundtruth.bin` with DiskANN when neither a binary
nor official `.ivecs` ground truth is present. For persistent machine-local
configuration, copy `scripts/dataset_paths.env.example` outside the repository,
edit it, and run with `DATASET_CONFIG=/path/to/dataset_paths.env`. The same
configuration mechanism is accepted by `run_diskann_matrix.sh`.

## Capture and performance runs

Tracing is a characterization phase and its latency must not be reported as backend performance:

```bash
TRACE=1 BACKENDS=libaio REPEATS=1 CACHE_STATE=cold INDEX=indexes/sift1m_R64_L100 \
QUERY=data/sift/sift_query.fbin GT=data/sift/sift_groundtruth.ibin scripts/run_diskann_matrix.sh

TRACE=0 REPEATS=5 CACHE_STATE=cold INDEX=indexes/sift1m_R64_L100 \
QUERY=data/sift/sift_query.fbin GT=data/sift/sift_groundtruth.ibin scripts/run_diskann_matrix.sh
```

The script stores the DiskANN commit, kernel, CPU, NUMA topology, and block devices in `results/environment.txt`. Record the filesystem, exact SSD model/firmware, mount options, CPU affinity, NUMA binding, CUDA/cuFile versions, and controller-cache limitations alongside it before publishing results.

## Replay correctness

Set `INDEX_FILE` to the physical disk-index file opened by `PQFlashIndex` (normally the prefix plus `_disk.index`), then replay one captured trace:

```bash
TRACE=results/traces/trace.csv INDEX_FILE=indexes/sift1m_R64_L100_disk.index scripts/replay_matrix.sh
```

The libaio pass writes XXH64 checksums for each real `(offset,len)` request. Other backends must match. Replay isolates storage-path cost; it is not DiskANN end-to-end query latency.

## Summaries

```bash
scripts/summarize_trace.py results/traces/trace.csv
scripts/summarize_results.py --raw results/raw --output results/summary.csv
scripts/plot_results.py results/summary.csv --trace results/traces/trace.csv
```

Only trace-disabled runs belong in final performance figures. Compare identical dataset, index, query order, L, beam width, cache-node request, thread count, affinity, NUMA policy, filesystem, and SSD. The sole independent variable is the I/O backend. Buffered runs must be labeled cold or warm; dropping Linux page cache does not flush an NVMe controller cache.

## Current scope

The first phase implements libaio + `O_DIRECT`, synchronous pread + `O_DIRECT`, buffered pread, and io_uring + `O_DIRECT`. GDS is reserved for a separately compiled trace-replay module because its destination is GPU HBM, whereas CPU DiskANN requires the returned bytes in DRAM. A GDS replay result therefore answers SSD-to-GPU cost for real DiskANN requests, not whether GPU DiskANN is faster.
