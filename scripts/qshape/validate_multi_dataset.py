"""Per-dataset validation; no fixed recall or logical request count."""
import statistics
from pathlib import Path
from final_factorial import validate_query, POLICIES, digest, load, atomic, ck, read, write, recall, quantile, effects
def run_files(p,L):
    return [Path(str(p)+s) for s in ('.log',f'_L{L}_run0_queries.csv',f'_L{L}_run0_grouping.csv',f'_{L}_idx_uint32.bin',f'_{L}_dists_float.bin')]
def inspect(p,i,n,ready,L):
    o,s,policy=POLICIES[i];budget=524288 if policy=='cms_512k' else 0
    fs=run_files(p,L);q=read(fs[1]);ck(len(q)==n,'query count')
    for k in ('query_id','execution_id'):ck(sorted(int(x[k]) for x in q)==list(range(n)),k)
    for x in q:
        validate_query(x,policy,budget,ready)
        ck(int(x['group_id'])==int(x['execution_id'])//256,'group mapping')
        if s=='off':ck(x['shared_hits']==x['ready_hits'],'sharing disabled')
        if o=='original':ck(x['query_id']==x['execution_id'],'original order')
    ck(max(int(x['frequency_counter_bytes']) for x in q)==budget,'counter payload')
    g=read(fs[2]);ck(len(g)==1,'grouping rows');g=g[0]
    ck(g['policy']==o and int(g['group_size'])==256 and int(g['candidate_pool'])==512,'grouping config')
    gn,sn,en=(int(g[k]) for k in ('grouping_ns','search_ns','e2e_ns'))
    ck(gn>=0 and sn>0 and en>=sn and en>=gn,'timing')
    qp=n*1e9/en;ck(abs(float(g['e2e_qps'])/qp-1)<.001,'qps')
    lat=[(int(x['search_end_ns'])-int(x['search_start_ns']))/1000 for x in q]
    response=[(int(x['search_end_ns'])-int(x['arrival_ns']))/1000 for x in q]
    row=dict(case=i,recall=recall(fs[0]),e2e_qps=qp,search_qps=n*1e9/sn,grouping_ms=gn/1e6,mean_us=statistics.mean(lat),p99_us=quantile(lat,.99),p999_us=quantile(lat,.999),response_p999_us=quantile(response,.999),response_mean_us=statistics.mean(response),response_p99_us=quantile(response,.99),search_ms=sn/1e6,e2e_ms=en/1e6)
    for k in 'reader_requests reader_bytes submitted_reads submitted_bytes shared_hits ready_hits ready_admissions ready_capacity_evictions bypass lookup_ns wait_copy_ns ready_rejects frequency_tracking_ns frequency_updates'.split():row[k]=sum(int(x[k]) for x in q)
    for k in 'peak_ready_bytes peak_inflight_bytes peak_shared_bytes frequency_counter_bytes frequency_shard_entries'.split():row[k]=max(int(x[k]) for x in q)
    row['inflight_hits']=row['shared_hits']-row['ready_hits']
    logical=sorted(tuple(int(x[k]) for k in ('query_id','reader_requests','reader_bytes','logical_node_reads','static_cache_hits')) for x in q)
    return row,(digest(fs[3]),digest(fs[4]),row['recall'],logical)


def prefix(root,r,i):
    o,s,_=POLICIES[i]
    return root/str(r)/i/f'1_{o}_{s}_stats'
def receipt(p,L):
    return {f.name:digest(f) for f in run_files(p,L)+[p.parent/'telemetry.json',p.parent/'resource.csv']}
def validate(root):
    m=load(root/'manifest.json');c=m['config'];rows=[];ref=None
    from multi_dataset_eval import plan
    ck(m['cases']==[list(x) for x in plan(c)],'matrix')
    for r,i in plan(c):
        p=prefix(root,r,i);ck(load(p.parent/'receipt.json')==receipt(p,c['l']),'receipt')
        x,sig=inspect(p,i,m['audit']['queries'],c['ready_mib']*1048576,c['l'])
        if ref is None:ref=sig
        ck(sig==ref,'result or per-query work mismatch')
        ck(x['recall']>=c['min_recall'],'recall floor')
        t=load(p.parent/'telemetry.json');d=t['device_delta']
        x.update(repeat=r,ids_sha256=sig[0],dists_sha256=sig[1],user_s=t['user_s'],system_s=t['system_s'],peak_rss_kib=t['peak_rss_kib'],device_reads=d['reads'] if d else '',device_read_bytes=d['sectors']*512 if d else '')
        rows.append(x)
    summary=[];paired=[]
    for i in c['policies']:
        g=[x for x in rows if x['case']==i];d=dict(case=i,repeats=len(g))
        d.update({k:statistics.mean(x[k] for x in g) for k in g[0] if k!='repeat' and isinstance(g[0][k],(int,float))})
        d['qps_cv']=statistics.stdev(x['e2e_qps'] for x in g)/d['e2e_qps'] if len(g)>1 else 0;summary.append(d)
    for r in range(1,c['repeats']+1):
        z={x['case']:x for x in rows if x['repeat']==r}
        for i,x in z.items():
            paired.append(dict(repeat=r,case=i,speedup=x['e2e_qps']/z['A0']['e2e_qps'],read_reduction=1-x['submitted_reads']/z['A0']['submitted_reads']))
    for name,data in [('metrics',rows),('summary',summary),('paired',paired)]:write(root/(name+'.csv'),data)
    atomic(root/'validation_summary.json',dict(status='PASS',runs=len(rows),recall=ref[2],files={n+'.csv':digest(root/(n+'.csv')) for n in ('metrics','summary','paired')}))
    print(f'PASS {len(rows)}/{len(m["cases"])}')
