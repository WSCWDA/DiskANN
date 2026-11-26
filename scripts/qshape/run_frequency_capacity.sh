#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${SEARCH_BIN:?}" "${INDEX_PREFIX:?}" "${QUERY_FILE:?}" "${GT_FILE:?}"
python3 "$(dirname "$0")/frequency_capacity_runner.py"
