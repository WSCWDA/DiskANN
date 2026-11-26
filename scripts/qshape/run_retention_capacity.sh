#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${BENCH_BIN:?}"
python3 "$(dirname "$0")/run_retention_capacity.py" --out "$OUT" --bench "$BENCH_BIN" --profile "${PROFILE:-smoke}" --repeats "${REPEATS:-3}" --timeout "${TIMEOUT:-900}" --retries "${RETRIES:-1}"
