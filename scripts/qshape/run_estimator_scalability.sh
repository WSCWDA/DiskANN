#!/usr/bin/env bash
set -euo pipefail
: "${OUT:?}" "${BENCH_BIN:?}"
mkdir "$OUT"
export OUT BENCH_BIN
python3 - "${PROFILE:-smoke}" "${REPEATS:-3}" <<'PY'
import os,sys,csv,subprocess,random
from pathlib import Path
profile=sys.argv[1];reps=int(sys.argv[2]);out=Path(os.environ['OUT'])
cases=set()
def add(mode,n,ops,b,skew,t,cover,backends=('cms','exact')):
 for backend in backends:cases.add((mode,backend,n,ops,b if backend=='cms' else 0,skew,t,cover))
if profile=='smoke':
 for mode in ('update','estimate','mixed','diagnostic'):add(mode,10000,100000,524288,1,1,1)
elif profile=='formal':
 for n in (10000,100000,1000000,10000000):
  add('update',n,n,524288,0,1,1)
  for b in (65536,262144,524288,1048576,2097152):
   for skew in (0,1):add('diagnostic',n,max(n,10000000),b,skew,1,0)
 for t in (1,8,32,64):
  for skew in (0,1):
   for mode in ('update','estimate','mixed'):add(mode,1000000,10000000,524288,skew,t,0)
 for b in (262144,524288,2097152):
  for skew in (0,.8,1,1.2):add('diagnostic',1000000,10000000,b,skew,1,0)
else:raise ValueError(profile)
manifest=[]
for r in range(reps):
 ordered=sorted(cases);random.Random(42+r).shuffle(ordered)
 for j,(mode,backend,n,ops,b,skew,t,cover) in enumerate(ordered):
  name=f'{r}_{j}.csv';args=[mode,backend,n,ops,b,skew,t,42+r,cover]
  manifest.append([name,*args])
with (out/'manifest.csv').open('w') as f:
 w=csv.writer(f);w.writerow('file mode backend n ops budget skew threads seed cover'.split());w.writerows(manifest)
for name,*args in manifest:
 with (out/name).open('w') as f:subprocess.run([os.environ['BENCH_BIN'],*map(str,args)],stdout=f,check=True)
 print('DONE',name,flush=True)
(out/'complete').write_text(str(len(manifest)))
PY
