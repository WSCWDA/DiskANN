#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${BENCH_BIN:?}"
mkdir "$OUT"
python3 - "$OUT" "$BENCH_BIN" "${PROFILE:-smoke}" "${REPEATS:-3}" <<'PY'
import csv,sys,random,subprocess
from pathlib import Path
out=Path(sys.argv[1]);bin=sys.argv[2];profile=sys.argv[3];reps=int(sys.argv[4])
assert reps>0
if profile=='smoke': n,ops,modes,skews=10000,20000,['correctness','perf','diag'],[1]
elif profile=='formal': n,ops,modes,skews=100000,1000000,['perf','diag'],[0,1]
else: raise ValueError(profile)
cases=[]
for r in range(reps):
 batch=[(p,n,ops,s,42+r,16777216,524288 if p=='cms' else 0,m) for p in ['none','bounded-local','lru','exact','cms'] for s in skews for m in modes]
 random.Random(42+r).shuffle(batch)
 cases.extend(batch)
with (out/'manifest.csv').open('w') as f:
 w=csv.writer(f);w.writerow('file policy n ops skew seed ready_budget meta_budget mode'.split());w.writerows([[f'{i}.csv',*c] for i,c in enumerate(cases)])
for i,c in enumerate(cases):
 with (out/f'{i}.csv').open('w') as f:subprocess.run([bin,*map(str,c)],stdout=f,check=True)
 print('DONE',i,flush=True)
(out/'complete').write_text(str(len(cases)))
PY
