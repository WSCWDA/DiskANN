#!/usr/bin/env bash
set -euo pipefail

data_root="${DATA_ROOT:-data}"
if (( $# )); then datasets=("$@"); else datasets=(sift gist); fi
mkdir -p "${data_root}"

for dataset in "${datasets[@]}"; do
  case "${dataset}" in
    sift) archive=sift.tar.gz; url=https://ftp.irisa.fr/local/texmex/corpus/sift.tar.gz ;;
    gist) archive=gist.tar.gz; url=https://ftp.irisa.fr/local/texmex/corpus/gist.tar.gz ;;
    *) echo "Unknown dataset: ${dataset}" >&2; exit 2 ;;
  esac
  if [[ ! -f "${data_root}/${archive}" ]]; then
    curl --fail --location --retry 3 --output "${data_root}/${archive}" "${url}"
  fi
  tar -xzf "${data_root}/${archive}" -C "${data_root}"
done

echo "Downloaded official TexMex datasets under ${data_root}"
