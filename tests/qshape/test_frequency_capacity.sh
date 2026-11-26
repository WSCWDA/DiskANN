#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHONPATH=scripts/qshape python3 - <<'PY'
from frequency_capacity_runner import plan
p=plan(5,42)
assert len(p)==100 and p==plan(5,42) and p!=plan(5,43)
for r in range(1,6):
 z=[x for x in p if x['run']==r]
 assert len({(x['policy'],x['order']) for x in z})==20
 assert [x['position'] for x in z]==list(range(1,21))
print('PASS capacity plan')
PY
