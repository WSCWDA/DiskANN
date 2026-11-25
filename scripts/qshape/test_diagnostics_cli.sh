#!/usr/bin/env bash
set -euo pipefail
bin=${1:-./build-qshape/apps/search_disk_index}
help=$("$bin" --help 2>&1)
for flag in qshape-breakdown qshape-reuse-stats; do
    grep -F -- "--$flag" <<< "$help"
done
echo "PASS: P3.0 CLI registration"
