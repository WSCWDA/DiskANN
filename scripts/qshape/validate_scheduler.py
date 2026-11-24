#!/usr/bin/env python3
import argparse,csv,hashlib,statistics,collections,heapq,math
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--out',type=Path,required=True)
p.add_argument('--queries',type=int,default=10000)
p.add_argument('--repeats',type=int,default=5)
p.add_argument('--groups',type=int,nargs='+',default=[64,128,256])
p.add_argument('--L',type=int,default=100)
p.add_argument('--W',type=int,default=64)
p.add_argument('--threads',type=int,default=64)
a=p.parse_args()
def rows(path):
    with path.open() as f: return list(csv.DictReader(f))
def one(path):
    x=rows(path); assert len(x)==1,path; return x[0]
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def ratio(x,y): return x/y if y else 0
def pairs(n): return n*(n-1)//2
def locality(q):
    ev=sorted([(int(x[k]),d,int(x['group_id'])) for x in q for k,d in [('search_start_ns',1),('search_end_ns',-1)]])
    counts=collections.Counter(); n=0; same=total=busy=0; last=ev[0][0]; sp=0
    for t,d,g in ev:
        dt=t-last; same+=dt*sp;total+=dt*pairs(n);busy+=dt*n
        sp-=pairs(counts[g]);counts[g]+=d;sp+=pairs(counts[g]);n+=d;last=t
    return ratio(same,total),busy
def trace(path,q):
    # Compact per-region lists of observed submit/harvest intervals.
    regions=collections.defaultdict(list); pending={}; seen=collections.Counter(); done=collections.Counter()
    byid={int(x['query_id']):x for x in q}
    with path.open() as f:
        for x in csv.DictReader(f):
            i=int(x['query_id']); k=(i,int(x['request_id'])); r=(int(x['offset']),int(x['length']));t=int(x['timestamp_ns'])
            assert i in byid and r[1]>0 and int(byid[i]['search_start_ns'])<=t<=int(byid[i]['search_end_ns'])
            if x['event_type']=='IO_SUBMIT':
                assert k not in pending and k[1]==seen[i];pending[k]=(r,t);seen[i]+=1
            else:
                assert x['event_type']=='IO_COMPLETE';rr,s=pending.pop(k)
                assert rr==r and t>=s and int(x['result'])==r[1]
                regions[r].append((s,t,i));done[i]+=1
    assert not pending
    for i,x in byid.items(): assert seen[i]==done[i]==int(x['submitted_reads'])
    total=sum(seen.values());assert total>0
    joins=dup=0; gaps=[]
    for v in regions.values():
        v.sort(); active=[]; counts=collections.Counter(); gc=collections.defaultdict(collections.Counter); prev=None; other=None
        for s,t,i in v:
            while active and active[0][0]<=s:
                _,j=heapq.heappop(active);counts[j]-=1
            if len(active)>counts[i]: joins+=1
            heapq.heappush(active,(t,i));counts[i]+=1
            gc[int(byid[i]['group_id'])][i]+=1
            if prev is not None:
                prior=prev if prev[1]!=i else other
                if prior is not None:gaps.append(s-prior[0])
                if prev[1]!=i:other=prev
            prev=(s,i)
        dup+=sum(sum(c.values())-max(c.values()) for c in gc.values())
    gaps.sort()
    return dict(inflight_pct=100*joins/total,region_dup_pct=100*dup/total,gap_p50_us=gaps[len(gaps)//2]/1000 if gaps else 0)
out=[]
for g in a.groups:
 for r in range(1,a.repeats+1):
    reference=None; refcounts=None; refrecall=None
    for mode in ['stats','trace']:
     for policy in ['original','similarity']:
      for scheduler in ['reorder','group-aware']:
        prefix=a.out/f'g{g}_{r}_{policy}_{scheduler}_{mode}'
        stem=str(prefix)+f'_L{a.L}_run0'
        q=rows(Path(stem+'_queries.csv'));assert len(q)==a.queries
        assert sorted(int(x['query_id']) for x in q)==list(range(a.queries))
        assert sorted(int(x['execution_id']) for x in q)==list(range(a.queries))
        for x in q:
            assert int(x['group_id'])==int(x['execution_id'])//g
            assert int(x['arrival_ns'])<=int(x['dispatch_ns'])<=int(x['search_start_ns'])<=int(x['search_end_ns'])
            assert int(x['submitted_reads'])==int(x['completed_reads']) and int(x['completion_errors'])==0
        counts={int(x['query_id']):tuple(int(x[k]) for k in ['logical_node_reads','static_cache_hits','submitted_reads','submitted_bytes']) for x in q}
        ids=tuple(digest(Path(str(prefix)+f'_{a.L}_{s}.bin')) for s in ['idx_uint32','dists_float'])
        perf=[]
        for line in Path(str(prefix)+'.log').read_text().splitlines():
            try: v=list(map(float,line.split()))
            except ValueError: continue
            if len(v)==9 and v[:2]==[a.L,a.W]:perf.append(v)
        assert len(perf)==1,prefix
        v=perf[0]
        if reference is None:reference,refcounts,refrecall=ids,counts,v[-1]
        assert ids==reference and counts==refcounts and v[-1]==refrecall
        b=one(Path(stem+'_grouping.csv'));s=one(Path(stem+'_scheduler.csv'));summary=one(Path(stem+'_summary.csv'))
        assert s['scheduler']==scheduler and b['policy']==policy
        for k in ['logical_node_reads','static_cache_hits','submitted_reads','submitted_bytes','completion_errors']:
            assert int(summary[k])==sum(int(x[k]) for x in q)
        same,busy=locality(q);search=int(b['search_ns']);assert search>0
        m=dict(group=g,run=r,mode=mode,policy=policy,scheduler=scheduler,qps=v[2],mean_us=v[3],p999_us=v[4],recall=v[-1],e2e_qps=float(b['e2e_qps']),same_group_pct=100*same,worker_busy_pct=100*ratio(busy,search*a.threads),scheduler_worker_pct=100*ratio(int(s['worker_scheduler_ns']),search*a.threads),grouping_pct=100*ratio(int(b['grouping_ns']),search),distance_ms=int(s['distance_ns'])/1e6,ranking_ms=int(s['ranking_ns'])/1e6,maintenance_ms=int(s['maintenance_ns'])/1e6)
        if mode=='trace':m.update(trace(Path(stem+'_io.csv'),q))
        out.append(m);print('PASS correctness',prefix,flush=True)
fields=list(dict.fromkeys(k for x in out for k in x))
with (a.out/'scheduler_validation_metrics.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
for g in a.groups:
 for policy in ['original','similarity']:
    def avg(mode,s,k):return statistics.mean(x[k] for x in out if x['group']==g and x['policy']==policy and x['mode']==mode and x['scheduler']==s)
    print('GROUP',g,policy)
    for mode,k in [('stats','e2e_qps'),('stats','mean_us'),('stats','p999_us'),('stats','worker_busy_pct'),('stats','scheduler_worker_pct'),('stats','grouping_pct'),('trace','same_group_pct'),('trace','inflight_pct'),('trace','region_dup_pct'),('trace','gap_p50_us')]:
        x=avg(mode,'reorder',k);y=avg(mode,'group-aware',k);print(k,x,y,'delta',y-x)
    q=ratio(avg('stats','group-aware','e2e_qps'),avg('stats','reorder','e2e_qps'))
    gain=avg('trace','group-aware','inflight_pct')-avg('trace','reorder','inflight_pct')
    print('STAGE GATE (descriptive)', 'SUPPORTED' if q>=.97 and gain>0 and avg('stats','group-aware','scheduler_worker_pct')<=1 else 'REVIEW')
