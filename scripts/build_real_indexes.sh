#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${DATASET_CONFIG:-}" ]]; then
  # shellcheck source=/dev/null
  source "${DATASET_CONFIG}"
fi

build_root="${BUILD_ROOT:-build}"
dataset_root="${DATASET_ROOT:-data}"
if [[ -n "${SIFT_DIR:-}" ]]; then sift_dir=${SIFT_DIR}
elif [[ -d "${dataset_root}/sift_1M" ]]; then sift_dir="${dataset_root}/sift_1M"
else sift_dir="${dataset_root}/sift"; fi
if [[ -n "${GIST_DIR:-}" ]]; then gist_dir=${GIST_DIR}
elif [[ -d "${dataset_root}/gist_1M" ]]; then gist_dir="${dataset_root}/gist_1M"
else gist_dir="${dataset_root}/gist"; fi
index_root="${INDEX_ROOT:-indexes}"
threads="${THREADS:-32}"
gt_k="${GT_K:-100}"
if (( $# )); then datasets=("$@"); else datasets=(sift); fi
mkdir -p "${index_root}"

require_file() {
  [[ -f "$1" ]] || { echo "Required file not found: $1" >&2; exit 2; }
}

ensure_fbin() {
  local vecs=$1 bin=$2
  if [[ -f "${bin}" ]]; then
    echo "Using existing binary vectors: ${bin}"
  else
    require_file "${vecs}"
    "${build_root}/apps/utils/fvecs_to_bin" float "${vecs}" "${bin}"
  fi
}

build_one() {
  local name=$1 src=$2 dim=$3 ram=$4
  local base="${src}/${name}_base.fbin"
  local query="${src}/${name}_query.fbin"
  local gt="${GT_FILE:-${src}/${name}_groundtruth.bin}"
  local prefix="${INDEX_PREFIX:-${index_root}/${name}1m_R64_L100}"

  ensure_fbin "${src}/${name}_base.fvecs" "${base}"
  ensure_fbin "${src}/${name}_query.fvecs" "${query}"

  if [[ ! -f "${gt}" ]]; then
    local ivecs="${src}/${name}_groundtruth.ivecs"
    if [[ -f "${ivecs}" ]]; then
      "${build_root}/apps/utils/ivecs_to_bin" "${ivecs}" "${gt}"
    else
      echo "Ground truth not found; computing exact top-${gt_k}: ${gt}"
      local gt_prefix=${gt%.bin}
      "${build_root}/apps/utils/compute_groundtruth" \
        --data_type float --dist_fn l2 --base_file "${base}" \
        --query_file "${query}" --gt_file "${gt_prefix}" --K "${gt_k}"
    fi
  else
    echo "Using existing ground truth: ${gt}"
  fi

  "${build_root}/apps/build_disk_index" --data_type float --dist_fn l2 \
    --data_path "${base}" --index_path_prefix "${prefix}" \
    -R 64 -L 100 -B "${ram}" -M 8 -T "${threads}"

  echo "Built ${name^^}1M (${dim} dimensions)"
  echo "INDEX=${prefix}"
  echo "INDEX_FILE=${prefix}_disk.index"
  echo "QUERY=${query}"
  echo "GT=${gt}"
}

for dataset in "${datasets[@]}"; do
  case "${dataset}" in
    sift) build_one sift "${sift_dir}" 128 "${SIFT_BUILD_RAM_GB:-8}" ;;
    gist) build_one gist "${gist_dir}" 960 "${GIST_BUILD_RAM_GB:-32}" ;;
    *) echo "Unknown dataset: ${dataset}" >&2; exit 2 ;;
  esac
done
