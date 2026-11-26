import argparse,csv,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--repeats',type=int,default=3);p.add_argument('--budget',type=int,default=1048576);p.add_argument('--depth',type=int,default=4);p.add_argument('--L',type=int,default=100);p.add_argument('--queries',type=int,default=10000);a=p.parse_args()
ref=None;rows=[]
for mode in ('exact','cms'):
 for r in range(1,a.repeats+1):
  for order in ('original','similarity'):
   for sharing in ('off','inflight'):
    prefix=a.out/mode/str(r)/f'1_{order}_{sharing}_stats'
    with Path(str(prefix)+f'_L{a.L}_run0_queries.csv').open() as f:q=list(csv.DictReader(f))
    assert len(q)==a.queries and len({x['query_id'] for x in q})==a.queries
    def total(k):return sum(int(x[k]) for x in q)
    for x in q:
     v=lambda k:int(x[k])
     assert v('reader_requests')==v('submitted_reads')+v('shared_hits')
     assert v('reader_bytes')==v('submitted_bytes')+v('shared_bytes')
     assert v('submitted_reads')==v('completed_reads') and not v('completion_errors')
     assert v('frequency_updates')==v('reader_requests') and not v('frequency_update_failures')
     assert v('frequency_gate_checks')==v('frequency_gate_accepts')+v('frequency_gate_rejects')
     assert v('peak_ready_bytes')<=16777216 and v('peak_inflight_bytes')<=67108864
    expected=64*4*a.depth*(a.budget//64//4//a.depth) if mode=='cms' else 0
    assert max(int(x['frequency_counter_bytes']) for x in q)==expected
    assert not total('frequency_saturations')
    if mode=='cms':assert not total('frequency_shard_entries')
    hashes=tuple(hashlib.sha256(Path(str(prefix)+f'_{a.L}_{s}.bin').read_bytes()).hexdigest() for s in ('idx_uint32','dists_float'))
    if ref is None:ref=hashes
    assert hashes==ref
    with Path(str(prefix)+f'_L{a.L}_run0_grouping.csv').open() as f:g=next(csv.DictReader(f))
    rows.append(dict(mode=mode,run=r,order=order,sharing=sharing,e2e_qps=g['e2e_qps'],counter_bytes=expected,reads=total('submitted_reads'),admissions=total('ready_admissions'),updates=total('frequency_updates')))
with (a.out/'sketch_metrics.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('PASS',len(rows))
