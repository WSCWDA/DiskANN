#!/usr/bin/env python3
import argparse,csv,statistics,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--out',type=Path,required=True)
p.add_argument('--repeats',type=int,default=5)
p.add_argument('--queries',type=int,default=10000)
p.add_argument('--L',type=int,default=100)
p.add_argument('--W',type=int,default=64)
p.add_argument('--budget',type=int,default=67108864)
a=p.parse_args()
def rows(path):
    with path.open() as f:return list(csv.DictReader(f))
def check(ok,msg):
    if not ok:raise RuntimeError(msg)
result=[]
for h in ['legacy','mixed']:
 for profile in [0,1]:
    root=a.out/f'{h}_{profile}'
    subprocess.run([sys.executable,str(Path(__file__).with_name('validate_sharing.py')),'--out',str(root),'--repeats',str(a.repeats),'--queries',str(a.queries),'--L',str(a.L),'--W',str(a.W),'--budget',str(a.budget),'--modes','stats'],check=True)
    for m in rows(root/'sharing_validation_metrics.csv'):
        if m['sharing']!='inflight':continue
        d=dict(hash=h,profile=profile,**m)
        d.update(active_shards='',max_shard_pct='',lock_wait_us='',lock_hold_us='')
        if profile:
            s=rows(root/f"{m['run']}_{m['policy']}_inflight_stats_L{a.L}_run0_shards.csv")
            check(sorted(int(x['shard_id']) for x in s)==list(range(64)),'shard IDs')
            n=sum(int(x['lookups']) for x in s);o=sum(int(x['owners']) for x in s);j=sum(int(x['joins']) for x in s);pub=sum(int(x['publishes']) for x in s)
            check(n==int(m['reader_requests']) and j==int(m['shared_hits']) and o+int(m['bypass'])+j==n and o==pub,'shard conservation')
            active=sum(int(x['lookups'])>0 for x in s)
            d.update(active_shards=active,max_shard_pct=100*max(int(x['lookups']) for x in s)/n,lock_wait_us=sum(int(x['lock_wait_ns']) for x in s)/(n+pub)/1000,lock_hold_us=sum(int(x['lock_hold_ns']) for x in s)/(n+pub)/1000)
            check(h!='mixed' or active==64,'mixed shard coverage')
        result.append(d)
with (a.out/'hash_validation_metrics.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
for policy in ['original','similarity']:
 for profile in [0,1]:
    def avg(h,k):return statistics.mean(float(x[k]) for x in result if x['hash']==h and x['profile']==profile and x['policy']==policy)
    print(policy,profile,'QPS change',avg('mixed','e2e_qps')/avg('legacy','e2e_qps')-1,'lookup us legacy/mixed',*[avg(h,'lookup_ns')/avg(h,'reader_requests')/1000 for h in ['legacy','mixed']])
    if profile:print('active shards, max shard %, lock wait/hold us',*[(h,*[avg(h,k) for k in ['active_shards','max_shard_pct','lock_wait_us','lock_hold_us']]) for h in ['legacy','mixed']])
