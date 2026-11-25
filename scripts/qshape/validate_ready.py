#!/usr/bin/env python3
import argparse,csv,hashlib,statistics
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--out',type=Path,required=True)
p.add_argument('--repeats',type=int,default=5)
p.add_argument('--queries',type=int,default=10000)
p.add_argument('--L',type=int,default=100)
p.add_argument('--budget',type=int,default=67108864)
p.add_argument('--ready-budget',type=int,default=16777216)
a=p.parse_args()
def rows(path):
    with open(path) as f:return list(csv.DictReader(f))
def check(ok,msg):
    if not ok:raise RuntimeError(msg)
out=[];ref=None
for r in range(1,a.repeats+1):
 for retention in ('none','bounded'):
  for policy in ('original','similarity'):
   for sharing in ('off','inflight'):
    prefix=a.out/retention/f'{r}_{policy}_{sharing}_stats'
    stem=str(prefix)+f'_L{a.L}_run0'
    q=rows(stem+'_queries.csv')
    check(sorted(int(x['query_id']) for x in q)==list(range(a.queries)),str(prefix)+' IDs')
    check(sorted(int(x['execution_id']) for x in q)==list(range(a.queries)),str(prefix)+' order')
    active=retention=='bounded' and sharing=='inflight'
    for x in q:
     n=lambda k:int(x[k])
     check(n('reader_requests')==n('submitted_reads')+n('shared_hits') and n('reader_bytes')==n('submitted_bytes')+n('shared_bytes'),str(prefix)+' conservation')
     check(n('submitted_reads')==n('completed_reads') and not n('completion_errors'),str(prefix)+' completion')
     check(n('ready_hits')<=n('shared_hits') and n('ready_hit_bytes')<=n('shared_bytes'),str(prefix)+' hit accounting')
     check(n('peak_shared_bytes')<=a.budget+(a.ready_budget if active else 0) and n('peak_inflight_bytes')<=a.budget and n('peak_ready_bytes')<=(a.ready_budget if active else 0),str(prefix)+' budget')
     if not active:check(not n('ready_hits') and not n('ready_admissions') and not n('ready_rejects'),str(prefix)+' disabled retention')
     if sharing=='off':check(not n('shared_hits'),str(prefix)+' disabled sharing')
    ids=tuple(hashlib.sha256(Path(str(prefix)+f'_{a.L}_{s}.bin').read_bytes()).hexdigest() for s in ('idx_uint32','dists_float'))
    logical=sorted((int(x['query_id']),int(x['reader_requests']),int(x['reader_bytes']),int(x['logical_node_reads']),int(x['static_cache_hits'])) for x in q)
    if ref is None:ref=(ids,logical)
    check(ref==(ids,logical),str(prefix)+' results')
    b=rows(stem+'_grouping.csv')[0]
    out.append(dict(run=r,retention=retention,policy=policy,sharing=sharing,e2e_qps=float(b['e2e_qps']),**{k:sum(int(x[k]) for x in q) for k in ('submitted_reads','submitted_bytes','shared_hits','ready_hits','ready_hit_bytes','ready_admissions','ready_rejects')},**{k:max(int(x[k]) for x in q) for k in ('peak_shared_bytes','peak_ready_bytes','peak_inflight_bytes')}))
    print('PASS',prefix)
with open(a.out/'ready_validation_metrics.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
for policy in ('original','similarity'):
 for retention in ('none','bounded'):
    z=[x for x in out if x['policy']==policy and x['retention']==retention and x['sharing']=='inflight']
    print(policy,retention,{k:statistics.mean(x[k] for x in z) for k in ('e2e_qps','submitted_reads','ready_hits','ready_admissions','ready_rejects')})
