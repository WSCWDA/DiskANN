#!/usr/bin/env bash
set -euo pipefail

build_root="${BUILD_ROOT:-build}"
data_root="${DATA_ROOT:-data}"
index_root="${INDEX_ROOT:-indexes}"
threads="${THREADS:-32}"
mkdir -p "${index_root}"

build_one() {
  local name=$1 dim=$2 ram=$3
  local src="${data_root}/${name}"
  "${build_root}/apps/utils/fvecs_to_bin" float "${src}/${name}_base.fvecs" "${src}/${name}_base.fbin"
  "${build_root}/apps/utils/fvecs_to_bin" float "${src}/${name}_query.fvecs" "${src}/${name}_query.fbin"
  "${build_root}/apps/utils/ivecs_to_bin" "${src}/${name}_groundtruth.ivecs" "${src}/${name}_groundtruth.ibin"
  "${build_root}/apps/build_disk_index" --data_type float --dist_fn l2 \
    --data_path "${src}/${name}_base.fbin" --index_path_prefix "${index_root}/${name}1m_R64_L100" \
    -R 64 -L 100 -B "${ram}" -M 8 -T "${threads}"
  echo "Built ${name^^}1M (${dim} dimensions) from official vectors"
}

build_one sift 128 "${SIFT_BUILD_RAM_GB:-8}"
build_one gist 960 "${GIST_BUILD_RAM_GB:-32}"
