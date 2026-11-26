import argparse,csv,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--out',type=Path,required=True)
p.add_argument('--repeats',type=int,default=5)
p.add_argument('--queries',type=int,default=10000)
p.add_argument('--L',type=int,default=100)
p.add_argument('--ready-stats',action='store_true')
a=p.parse_args()
cmd=[sys.executable,str(Path(__file__).with_name('validate_retention_ablation.py')),'--out',str(a.out),'--repeats',str(a.repeats),'--queries',str(a.queries),'--L',str(a.L),'--policies','none','bounded-local','lru','frequency']
if a.ready_stats:cmd+=['--ready-stats']
subprocess.run(cmd,check=True)
rows=[]
for policy in ('none','bounded-local','lru','frequency'):
 for r in range(1,a.repeats+1):
  for order in ('original','similarity'):
   for sharing in ('off','inflight'):
    path=a.out/policy/str(r)/f'1_{order}_{sharing}_stats_L{a.L}_run0_queries.csv'
    with path.open() as f:q=list(csv.DictReader(f))
    keys=['frequency_updates','frequency_update_failures','frequency_gate_checks','frequency_gate_accepts','frequency_gate_rejects','frequency_tracking_ns']
    d={k:sum(int(x[k]) for x in q) for k in keys}
    assert d['frequency_update_failures']==0,path
    assert d['frequency_updates']==(sum(int(x['reader_requests']) for x in q) if policy=='frequency' else 0),path
    assert d['frequency_gate_checks']==d['frequency_gate_accepts']+d['frequency_gate_rejects'],path
    assert all(int(x['ready_ttl_evictions'])==0 for x in q),path
    rows.append(dict(policy=policy,run=r,order=order,sharing=sharing,**d,max_observed_shard_entries=max(int(x['frequency_shard_entries']) for x in q)))
with (a.out/'frequency_metrics.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(f'PASS frequency {len(rows)} configurations')
