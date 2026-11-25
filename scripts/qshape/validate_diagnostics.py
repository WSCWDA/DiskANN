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
def rows(p):
    with open(p) as f:return list(csv.DictReader(f))
def check(x,msg):
    if not x:raise RuntimeError(msg)
out=[]
for mode in ['control','breakdown','reuse']:
 root=a.out/mode
 subprocess.run([sys.executable,str(Path(__file__).with_name('validate_sharing.py')),'--out',str(root),'--repeats',str(a.repeats),'--queries',str(a.queries),'--L',str(a.L),'--W',str(a.W),'--budget',str(a.budget),'--modes','stats'],check=True)
 for m in rows(root/'sharing_validation_metrics.csv'):
    if m['sharing']!='inflight':continue
    stem=root/f"{m['run']}_{m['policy']}_inflight_stats_L{a.L}_run0"
    d=dict(diagnostic_mode=mode,**m)
    if mode!='control':
        q=rows(str(stem)+'_queries.csv'); z=rows(str(stem)+'_diagnostics.csv')
        check(len(q)==len(z)==a.queries,'diagnostic rows')
        for x,y in zip(q,z):
            check(x['query_id']==y['query_id'],'query mapping')
            n=lambda k:int(y[k])
            if mode=='breakdown':
                check(n('consumer_consumes')==int(x['shared_hits']),'consumer count')
                check(n('owner_consumes')+n('consumer_consumes')+int(x['bypass'])==int(x['reader_requests']),'consume count')
                check(n('ready_before_wait_count')+n('blocking_wait_count')==n('consumer_consumes'),'wait count')
                check(n('copy_bytes')==int(x['reader_bytes']) if int(x['bypass'])==0 else n('copy_bytes')<=int(x['reader_bytes']),'copy bytes')
                check(sum(n(k) for k in ['owner_wait_ns','consumer_wait_ns','owner_copy_ns','consumer_copy_ns'])<=int(x['wait_copy_ns']),'timing conservation')
            else:
                check(n('reuse_same_group')<=n('reuse_cross_query')<=n('reuse_hits')<=n('reuse_lookups'),'reuse counts')
        d.update({k:sum(int(x[k]) for x in z) for k in z[0] if k!='query_id'})
        if mode=='reuse':
            gaps=[];cross=[];counts={}
            with open(str(stem)+'_reuse.csv') as f:
                for x in csv.DictReader(f):
                    g=int(x['gap_ns']);check(g>=0,'gap')
                    i=int(x['query_id']);counts[i]=counts.get(i,0)+1;gaps.append(g)
                    if x['query_id']!=x['previous_query']:cross.append(g)
            check(all(counts.get(int(x['query_id']),0)==min(4096,int(x['reuse_hits'])) for x in z),'sample counts')
            d['reuse_samples']=len(gaps);d['cross_samples']=len(cross)
            for us in [100,500,1000,2000,5000,10000]:
                d[f'cross_gap_le_{us}us']=sum(g<=us*1000 for g in cross)
            if cross:
                cross.sort()
                for pct in [50,95,99]:d[f'cross_gap_p{pct}_us']=cross[int((len(cross)-1)*pct/100)]/1000
    out.append(d)
keys=list(dict.fromkeys(k for x in out for k in x))
with open(a.out/'diagnostic_metrics.csv','w') as f:
    w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(out)
for x in out:
    print(x['diagnostic_mode'],x['run'],x['policy'],'QPS',x['e2e_qps'], 'consumer_wait_ms/query',x.get('consumer_wait_ns',0)/a.queries/1e6,'reuse_cross_query',x.get('reuse_cross_query',0))
print('PASS diagnostics; reuse counts are bounded-history observations, not cache hit predictions')
