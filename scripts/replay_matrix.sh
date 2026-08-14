#!/usr/bin/env bash
set -euo pipefail
: "${TRACE:?TRACE is required}"; : "${INDEX_FILE:?INDEX_FILE is required}"
build_root="${BUILD_ROOT:-build}"; out="${RESULTS_ROOT:-results}/replay"; mkdir -p "${out}"
baseline="${out}/libaio.hashes.csv"
"${build_root}/apps/replay_diskann_trace" --trace "${TRACE}" --index_file "${INDEX_FILE}" --io_backend libaio \
  --hash_output "${baseline}" --metrics_output "${out}/libaio.metrics.csv"
for backend in pread-direct pread-buffered io-uring; do
  "${build_root}/apps/replay_diskann_trace" --trace "${TRACE}" --index_file "${INDEX_FILE}" --io_backend "${backend}" \
    --verify_hashes "${baseline}" --metrics_output "${out}/${backend}.metrics.csv"
done
if [[ "${GDS_REPLAY:-0}" == 1 ]]; then
  "${build_root}/apps/replay_diskann_trace" --trace "${TRACE}" --index_file "${INDEX_FILE}" --io_backend gds \
    --device_id "${CUDA_DEVICE:-0}" --verify_hashes "${baseline}" --metrics_output "${out}/gds.metrics.csv"
fi
