import argparse,csv,hashlib,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--repeats',type=int,default=5);p.add_argument('--queries',type=int,default=10000);p.add_argument('--L',type=int,default=100);p.add_argument('--budget',type=int,default=67108864);p.add_argument('--ready-budget',type=int,default=16777216);p.add_argument('--policies',nargs='+',default=['none','bounded','bounded-local','lru']);p.add_argument('--ready-stats',action='store_true');p.add_argument('--group-sizes',nargs='+',type=int,default=[64,128,256,512]);p.add_argument('--pool-sizes',nargs='+',type=int,default=[512]);a=p.parse_args()
def read(p):
 with open(p) as f:return list(csv.DictReader(f))
def ck(ok,msg):
 if not ok:raise RuntimeError(msg)
def write(path,rows):
 with open(path,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
out=[];groups=[];ref=None
keys='reader_requests submitted_reads submitted_bytes shared_hits ready_hits ready_admissions ready_rejects ready_ttl_evictions ready_capacity_evictions ready_unused_evictions ready_cross_query_hits ready_same_group_hits ready_cross_group_hits ready_hit_age_ns ready_eviction_age_ns ready_retention_ns'.split()
cases=[(g,512,'similarity',p) for g in a.group_sizes for p in ('none','bounded-local','lru')]+[(256,pool,'similarity',p) for pool in a.pool_sizes if pool!=512 for p in ('none','bounded-local','lru')]+[(256,512,'original',p) for p in ('none','bounded-local','lru')]
ck(len(cases)==len(set(cases)), 'duplicate cases')
for r in range(1,a.repeats+1):
 for gsize,pool,order,policy in cases:
   for sharing in ('inflight',):
    prefix=a.out/f'g{gsize}_p{pool}'/policy/str(r)/f'1_{order}_{sharing}_stats';stem=str(prefix)+f'_L{a.L}_run0';q=read(stem+'_queries.csv')
    ck(sorted(int(x['query_id']) for x in q)==list(range(a.queries)),str(prefix)+' IDs')
    ck(sorted(int(x['execution_id']) for x in q)==list(range(a.queries)),str(prefix)+' order')
    ck(all(int(x['group_id'])==int(x['execution_id'])//gsize for x in q),str(prefix)+' group mapping')
    meta=read(stem+'_grouping.csv')[0]
    ck(int(meta['group_size'])==gsize and int(meta['candidate_pool'])==pool and meta['policy']==order,str(prefix)+' grouping config')
    active=policy!='none'
    for x in q:
     n=lambda k:int(x[k])
     ck(n('reader_requests')==n('submitted_reads')+n('shared_hits') and n('reader_bytes')==n('submitted_bytes')+n('shared_bytes'),str(prefix)+' conservation')
     ck(n('completed_reads')==n('submitted_reads') and not n('completion_errors'),str(prefix)+' completion')
     ck(n('ready_hits')<=n('shared_hits') and n('ready_hit_bytes')<=n('shared_bytes'),str(prefix)+' hits')
     ck(n('peak_shared_bytes')<=a.budget+(a.ready_budget if active else 0) and n('peak_ready_bytes')<=(a.ready_budget if active else 0) and n('peak_inflight_bytes')<=a.budget,str(prefix)+' budget')
     ck(n('ready_cross_query_hits')==n('ready_same_group_hits')+n('ready_cross_group_hits')<=n('ready_hits'),str(prefix)+' group hits')
     if not active:ck(not n('ready_hits') and not n('ready_admissions'),str(prefix)+' disabled')
     if active:ck(n('ready_admissions')+n('ready_rejects')+n('bypass')==n('submitted_reads'),str(prefix)+' admission conservation')
     if sharing=='off':ck(n('shared_hits')==n('ready_hits'),str(prefix)+' no inflight joins')
     if policy in ('none','bounded','bounded-local','lru'):ck(not n('ready_ttl_evictions'),str(prefix)+' TTL')
     if policy in ('none','bounded','bounded-local','ttl'):ck(not n('ready_capacity_evictions'),str(prefix)+' LRU')
    if active:ck(sum(int(x['ready_hits']) for x in q)>0,str(prefix)+' READY hits')
    ids=tuple(hashlib.sha256(Path(str(prefix)+f'_{a.L}_{s}.bin').read_bytes()).hexdigest() for s in ('idx_uint32','dists_float'))
    logical=sorted(tuple(int(x[k]) for k in ('query_id','reader_requests','reader_bytes','logical_node_reads','static_cache_hits')) for x in q)
    if ref is None:ref=(ids,logical)
    ck(ref==(ids,logical),str(prefix)+' results')
    def agg(z):
     d={k:sum(int(x[k]) for x in z) for k in keys};d['inflight_hits']=d['shared_hits']-d['ready_hits'];return d
    base=dict(run=r,group_size=gsize,candidate_pool=pool,retention=policy,order=order,sharing=sharing)
    latency=sorted((int(x['search_end_ns'])-int(x['search_start_ns']))/1000 for x in q)
    out.append(dict(**base,mean_us=statistics.mean(latency),p99_us=latency[(99*len(latency)+99)//100-1],p999_us=latency[(999*len(latency)+999)//1000-1],e2e_qps=float(meta['e2e_qps']),grouping_ns=int(meta['grouping_ns']),comparisons=int(meta['comparisons']),search_ns=int(meta['search_ns']),e2e_ns=int(meta['e2e_ns']),**agg(q),**{k:max(int(x[k]) for x in q) for k in ('peak_shared_bytes','peak_ready_bytes','peak_inflight_bytes')}))
    g={}
    for x in q:g.setdefault(int(x['group_id']),[]).append(x)
    for i,z in sorted(g.items()):groups.append(dict(**base,group_id=i,query_count=len(z),**agg(z)))
    print('PASS',prefix)
write(a.out/'grouping_sensitivity_metrics.csv',out);write(a.out/'grouping_sensitivity_groups.csv',groups)
print('PASS',len(out),'runs; cross-configuration result SHA256 and logical counts')
