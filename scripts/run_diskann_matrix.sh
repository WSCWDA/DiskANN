#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${DATASET_CONFIG:-}" ]]; then
  # shellcheck source=/dev/null
  source "${DATASET_CONFIG}"
fi

: "${INDEX:?INDEX is required}"
: "${QUERY:?QUERY is required}"
: "${GT:?GT is required}"
dataset="${DATASET:-sift1m}"; build_root="${BUILD_ROOT:-build}"; results="${RESULTS_ROOT:-results}"
read -r -a backends <<< "${BACKENDS:-libaio pread-direct pread-buffered io-uring}"
read -r -a beams <<< "${BEAMS:-1 2 4 8 16}"
read -r -a threads <<< "${THREAD_COUNTS:-1}"
read -r -a caches <<< "${CACHES:-0}"
repeats="${REPEATS:-5}"; L="${L:-100}"; K="${K:-10}"; cache_state="${CACHE_STATE:-cold}"
resume="${RESUME:-1}"; run_timeout="${RUN_TIMEOUT:-20m}"; continue_on_error="${CONTINUE_ON_ERROR:-1}"
mkdir -p "${results}/raw" "${results}/traces" "${results}/figures"
mkdir -p "${results}/incomplete"

search_binary="${build_root}/apps/search_disk_index"
[[ -x "${search_binary}" ]] || { echo "Search binary is missing or not executable: ${search_binary}" >&2; exit 2; }
[[ -f "${QUERY}" ]] || { echo "Query file not found: ${QUERY}" >&2; exit 2; }
[[ -f "${GT}" ]] || { echo "Ground-truth file not found: ${GT}" >&2; exit 2; }

total_runs=$(( ${#backends[@]} * ${#beams[@]} * ${#threads[@]} * ${#caches[@]} * (repeats + 1) ))
current_run=0
failed_runs=0
skipped_runs=0
echo "Starting DiskANN matrix: ${total_runs} processes (${repeats} measured + 1 warm-up per configuration)"
echo "INDEX=${INDEX}"
echo "QUERY=${QUERY}"
echo "GT=${GT}"
echo "Results: ${results}/raw"

{
  git rev-parse HEAD; uname -a; lscpu; command -v numactl >/dev/null && numactl --hardware || true; lsblk
} > "${results}/environment.txt"

for backend in "${backends[@]}"; do for W in "${beams[@]}"; do for T in "${threads[@]}"; do for C in "${caches[@]}"; do
  for run in $(seq 0 "${repeats}"); do
    current_run=$((current_run + 1))
    phase=measure; [[ ${run} == 0 ]] && phase=warmup
    stem="${results}/raw/${dataset}_${backend}_L${L}_W${W}_T${T}_C${C}_${cache_state}_r${run}"
    echo "[${current_run}/${total_runs}] ${phase}: backend=${backend} L=${L} W=${W} T=${T} C=${C} run=${run}"
    result_ids="${stem}_${L}_idx_uint32.bin"
    result_dists="${stem}_${L}_dists_float.bin"
    if [[ "${resume}" == 1 && -s "${stem}.metrics.csv" && -s "${result_ids}" && -s "${result_dists}" ]]; then
      echo "Skipping complete run: ${stem}"
      skipped_runs=$((skipped_runs + 1))
      continue
    fi
    existing=("${stem}"*)
    if [[ -e "${existing[0]}" ]]; then
      archive="${results}/incomplete/$(basename "${stem}")_$(date +%Y%m%d_%H%M%S)"
      mkdir -p "${archive}"
      mv -- "${existing[@]}" "${archive}/"
      echo "Archived incomplete run to: ${archive}"
    fi
    if [[ "${cache_state}" == cold ]]; then
      sync
      if [[ -w /proc/sys/vm/drop_caches ]]; then echo 3 > /proc/sys/vm/drop_caches
      elif command -v sudo >/dev/null; then echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null
      else echo "Cannot drop page cache" >&2; exit 1; fi
    fi
    trace_arg=(); [[ "${TRACE:-0}" == 1 ]] && trace_arg=(--io_trace_path "${results}/traces/$(basename "${stem}").csv")
    search_command=("${search_binary}" --data_type float --dist_fn l2 --index_path_prefix "${INDEX}" \
      --query_file "${QUERY}" --gt_file "${GT}" --result_path "${stem}" -K "${K}" -L "${L}" -W "${W}" -T "${T}" \
      --num_nodes_to_cache "${C}" --io_backend "${backend}" --metrics_output "${stem}.metrics.csv" "${trace_arg[@]}")
    if [[ "${run_timeout}" == 0 ]]; then
      "${search_command[@]}" > "${stem}.stdout" 2> "${stem}.stderr" & pid=$!
    else
      timeout --foreground --signal=TERM --kill-after=30s "${run_timeout}" "${search_command[@]}" \
        > "${stem}.stdout" 2> "${stem}.stderr" & pid=$!
    fi
    monitor=""
    if command -v pidstat >/dev/null; then
      pidstat -u -r -d -w -C search_disk_index 1 > "${stem}.pidstat" & monitor=$!
    fi
    if wait "${pid}"; then
      status=0
    else
      status=$?
      [[ -n "${monitor}" ]] && kill "${monitor}" 2>/dev/null || true
      failed_runs=$((failed_runs + 1))
      echo "DiskANN search failed (status=${status}). Last stderr lines:" >&2
      tail -n 40 "${stem}.stderr" >&2 || true
      echo "Full logs: ${stem}.stdout and ${stem}.stderr" >&2
      if [[ "${continue_on_error}" != 1 ]]; then exit 1; fi
      continue
    fi
    [[ -n "${monitor}" ]] && kill "${monitor}" 2>/dev/null || true
    echo "Completed: ${stem}"
  done
done; done; done; done

echo "Matrix finished: completed_or_attempted=$((total_runs - skipped_runs)), skipped=${skipped_runs}, failed=${failed_runs}"
[[ ${failed_runs} -eq 0 ]]
