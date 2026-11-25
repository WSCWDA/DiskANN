#!/usr/bin/env python3
import argparse,csv,hashlib,statistics
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--out',type=Path,required=True)
p.add_argument('--repeats',type=int,default=5)
p.add_argument('--queries',type=int,default=10000)
p.add_argument('--L',type=int,default=100)
p.add_argument('--W',type=int,default=64)
p.add_argument('--budget',type=int,default=67108864)
p.add_argument('--modes',nargs='+',default=['stats','trace'])
a=p.parse_args()
def rows(p):
    with open(p) as f:return list(csv.DictReader(f))
def check(x,msg):
    if not x:raise RuntimeError(msg)
out=[]
for r in range(1,a.repeats+1):
 ref=None
 for mode in a.modes:
  for policy in ['original','similarity']:
   for sharing in ['off','inflight']:
    prefix=a.out/f'{r}_{policy}_{sharing}_{mode}'
    stem=str(prefix)+f'_L{a.L}_run0'
    q=rows(stem+'_queries.csv')
    check(sorted(int(x['query_id']) for x in q)==list(range(a.queries)),str(prefix)+' query IDs')
    check(sorted(int(x['execution_id']) for x in q)==list(range(a.queries)),str(prefix)+' execution IDs')
    keys=['reader_requests','reader_bytes','submitted_reads','submitted_bytes','shared_hits','shared_bytes','same_query_hits','bypass','lookup_ns','wait_copy_ns']
    sums={k:sum(int(x[k]) for x in q) for k in keys}
    for x in q:
        n=lambda k:int(x[k])
        check(n('reader_requests')==n('submitted_reads')+n('shared_hits') and n('reader_bytes')==n('submitted_bytes')+n('shared_bytes'),str(prefix)+' conservation')
        check(n('submitted_reads')==n('completed_reads') and n('completion_errors')==0,str(prefix)+' completion')
        check(n('peak_shared_bytes')<=a.budget and n('same_query_hits')<=n('shared_hits'),str(prefix)+' budget')
        if sharing=='off':check(n('shared_hits')==0,str(prefix)+' off')
    ids=tuple(hashlib.sha256(Path(str(prefix)+f'_{a.L}_{s}.bin').read_bytes()).hexdigest() for s in ['idx_uint32','dists_float'])
    logical={int(x['query_id']):tuple(int(x[k]) for k in ['logical_node_reads','static_cache_hits','reader_requests','reader_bytes']) for x in q}
    perf=[]
    for line in Path(str(prefix)+'.log').read_text().splitlines():
        try:v=list(map(float,line.split()))
        except ValueError:continue
        if len(v)==9 and v[:2]==[a.L,a.W]:perf.append(v)
    check(len(perf)==1,str(prefix)+' performance row')
    v=perf[0]
    if ref is None:ref=(ids,logical,v[-1])
    check(ref==(ids,logical,v[-1]),str(prefix)+' result or logical mismatch')
    if mode=='trace':
        pending={};counts={};completed={}
        with open(stem+'_io.csv') as f:
            for x in csv.DictReader(f):
                i=int(x['query_id']);k=(i,int(x['request_id']));region=(int(x['offset']),int(x['length']));t=int(x['timestamp_ns'])
                if x['event_type']=='IO_SUBMIT':
                    check(k not in pending and k[1]==counts.get(i,0),'duplicate submit')
                    pending[k]=(region,t);counts[i]=counts.get(i,0)+1
                else:
                    check(x['event_type']=='IO_COMPLETE' and k in pending,'unmatched completion')
                    rr,tt=pending.pop(k);check(rr==region and t>=tt and int(x['result'])==region[1],'bad completion')
                    completed[i]=completed.get(i,0)+1
        check(not pending,'pending requests')
        for x in q:
            i=int(x['query_id']);check(counts.get(i,0)==completed.get(i,0)==int(x['submitted_reads']),'trace count')
    b=rows(stem+'_grouping.csv')[0]
    out.append(dict(run=r,mode=mode,policy=policy,sharing=sharing,e2e_qps=float(b['e2e_qps']),mean_us=v[3],p999_us=v[4],recall=v[-1],peak_shared_bytes=max(int(x['peak_shared_bytes']) for x in q),**sums))
    print('PASS correctness',prefix,flush=True)
with open(a.out/'sharing_validation_metrics.csv','w') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
def avg(p,s,k):return statistics.mean(x[k] for x in out if x['mode']=='stats' and x['policy']==p and x['sharing']==s)
if 'stats' in a.modes:
    base=avg('original','off','submitted_reads');passive=avg('original','inflight','submitted_reads');active=avg('similarity','inflight','submitted_reads')
    for p in ['original','similarity']:
        for s in ['off','inflight']:
            print(p,s,{k:avg(p,s,k) for k in ['submitted_reads','shared_hits','same_query_hits','e2e_qps','mean_us','p999_us','lookup_ns','wait_copy_ns']})
    for label,value,target in [('passive reduction',1-passive/base,.15),('incremental reduction',1-active/passive,.05),('incremental QPS',avg('similarity','inflight','e2e_qps')/avg('original','inflight','e2e_qps')-1,.05)]:
        print(label,value,'SUPPORTED' if value>=target else 'REVIEW')
