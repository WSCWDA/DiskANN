import argparse,csv,hashlib,json,math,statistics,re
from pathlib import Path
from frequency_capacity_runner import plan,BUDGETS
def ck(ok,msg):
    if not ok:raise ValueError(msg)
def read(path):
    with open(path) as f:return list(csv.DictReader(f))
def write(path,rows):
    with open(path,'w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def quantile(xs,p):
    return sorted(xs)[math.ceil(len(xs)*p)-1]
def validate_query(x,policy,budget):
    n=lambda k:int(x[k])
    active=policy!='none';freq=policy=='exact' or policy.startswith('cms_')
    ck(n('reader_requests')==n('submitted_reads')+n('shared_hits'),'request conservation')
    ck(n('reader_bytes')==n('submitted_bytes')+n('shared_bytes'),'byte conservation')
    ck(n('completed_reads')==n('submitted_reads') and n('completion_errors')==0,'completion')
    ck(0<=n('ready_hits')<=n('shared_hits') and 0<=n('ready_hit_bytes')<=n('shared_bytes'),'hits')
    ck(0<=n('peak_ready_bytes')<=(16777216 if active else 0) and 0<=n('peak_inflight_bytes')<=67108864 and n('peak_shared_bytes')<=67108864+(16777216 if active else 0),'budget')
    ck(n('frequency_updates')==(n('reader_requests') if freq else 0) and n('frequency_update_failures')==0,'frequency updates')
    ck(n('frequency_gate_checks')==n('frequency_gate_accepts')+n('frequency_gate_rejects'),'gate')
    ck(n('frequency_saturations')==0,'saturation')
    ck(n('frequency_counter_bytes') in (0,budget),'counter bytes')
    if policy!='exact':ck(n('frequency_shard_entries')==0,'unexpected exact entries')
    if active:ck(n('ready_admissions')+n('ready_rejects')+n('bypass')==n('submitted_reads'),'admission conservation')
    else:ck(n('ready_hits')==n('ready_admissions')==0,'disabled retention')
    ck(n('ready_ttl_evictions')==0,'unexpected TTL')
    if policy in ('none','bounded-local'):ck(n('ready_capacity_evictions')==0,'unexpected capacity eviction')
    ck(n('arrival_ns')<=n('search_start_ns')<=n('search_end_ns'),'timestamps')
def recall(path):
    # DiskANN table: L W QPS mean p99.9 IOs IO-us CPU Recall.
    matches=[]
    for line in path.read_text(errors='replace').splitlines():
        parts=line.split()
        if len(parts)!=9:continue
        try:v=list(map(float,parts))
        except ValueError:continue
        if v[0]==100 and v[1]==64 and all(math.isfinite(x) for x in v) and 0<=v[-1]<=100:matches.append(v[-1])
    ck(len(matches)==1,'missing/ambiguous recall row '+str(path))
    return matches[0]
def compare(c,e,l):
    q=c['e2e_qps']/e['e2e_qps'];io=c['submitted_reads']/e['submitted_reads']-1;tail=c['p999_us']/e['p999_us']-1;adm=1-c['ready_admissions']/l['ready_admissions']
    return dict(qps_retention=q,read_increase=io,p999_increase=tail,admission_reduction=adm,meets_targets=q>=.98 and io<=.02 and tail<=.05 and adm>=.95)
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();root=a.out
    m=json.loads((root/'manifest.json').read_text());cases=plan(m['repeats'],m['seed']);ck(cases==m['cases'],'manifest mismatch')
    ck(int((root/'runner_complete').read_text())==len(cases),'incomplete runner')
    N=m['queries'];rows=[];ref=None
    for case in cases:
        policy,o,r=case['policy'],case['order'],case['run']
        prefix=root/policy/str(r)/o/f'1_{o}_inflight_stats';stem=str(prefix)+'_L100_run0'
        q=read(stem+'_queries.csv');ck(len(q)==N,'query count')
        for k in ('query_id','execution_id'):ck(sorted(int(x[k]) for x in q)==list(range(N)),k+' permutation')
        budget=int(policy[4:-1])*1024 if policy.startswith('cms_') else 0
        for x in q:
            try:
                validate_query(x,policy,budget)
                ck(int(x['group_id'])==int(x['execution_id'])//256,'group mapping')
            except ValueError as ex:raise ValueError(str(prefix)+' query '+x['query_id']+': '+str(ex)) from ex
        ck(max(int(x['frequency_counter_bytes']) for x in q)==budget,'actual counter payload')
        hashes=tuple(hashlib.sha256(Path(str(prefix)+'_100_'+s+'.bin').read_bytes()).hexdigest() for s in ('idx_uint32','dists_float'))
        logical=sorted(tuple(int(x[k]) for k in ('query_id','reader_requests','reader_bytes','logical_node_reads','static_cache_hits')) for x in q)
        rec=recall(Path(str(prefix)+'.log'))
        if ref is None:ref=(hashes,logical,rec)
        ck(ref==(hashes,logical,rec),'cross-config results '+str(prefix))
        g=read(stem+'_grouping.csv');ck(len(g)==1,'grouping rows');g=g[0]
        ck(g['policy']==o and int(g['group_size'])==256 and int(g['candidate_pool'])==512,'grouping config')
        gn,sn,en=(int(g[k]) for k in ('grouping_ns','search_ns','e2e_ns'))
        ck(gn>=0 and sn>0 and en>=sn and en>=gn,'grouping times')
        qps=float(g['e2e_qps']);ck(math.isfinite(qps) and abs(qps-N*1e9/en)/(N*1e9/en)<.001,'QPS consistency')
        lat=[(int(x['search_end_ns'])-int(x['search_start_ns']))/1000 for x in q]
        response=[(int(x['search_end_ns'])-int(x['arrival_ns']))/1000 for x in q]
        keys='reader_requests reader_bytes submitted_reads submitted_bytes shared_hits ready_hits ready_admissions ready_rejects ready_capacity_evictions frequency_updates frequency_tracking_ns frequency_gate_checks frequency_gate_accepts frequency_gate_rejects frequency_saturations bypass'.split()
        row=dict(**case,counter_bytes=budget,recall=rec,ids_sha256=hashes[0],dists_sha256=hashes[1],e2e_qps=qps,search_qps=N*1e9/sn,grouping_ms=gn/1e6,search_ms=sn/1e6,e2e_ms=en/1e6,mean_us=statistics.mean(lat),p50_us=quantile(lat,.5),p95_us=quantile(lat,.95),p99_us=quantile(lat,.99),p999_us=quantile(lat,.999),response_p999_us=quantile(response,.999))
        row.update({k:sum(int(x[k]) for x in q) for k in keys})
        row.update({k:max(int(x[k]) for x in q) for k in ('peak_ready_bytes','peak_inflight_bytes','peak_shared_bytes','frequency_shard_entries')})
        row['inflight_hits']=row['shared_hits']-row['ready_hits'];rows.append(row)
        print('PASS',prefix,flush=True)
    write(root/'capacity_metrics.csv',rows)
    summary=[]
    for policy in dict.fromkeys(x['policy'] for x in rows):
        for o in ('original','similarity'):
            z=[x for x in rows if x['policy']==policy and x['order']==o]
            d=dict(policy=policy,order=o,repeats=len(z))
            for k,v in z[0].items():
                if k not in ('run','position','policy','order') and isinstance(v,(int,float)):d[k]=statistics.mean(x[k] for x in z)
            qs=[x['e2e_qps'] for x in z];d.update(qps_std=statistics.stdev(qs) if len(qs)>1 else 0,qps_min=min(qs),qps_max=max(qs));d['qps_cv']=d['qps_std']/d['e2e_qps']
            summary.append(d)
    write(root/'capacity_summary.csv',summary)
    lookup={(x['policy'],x['order']):x for x in summary};comparisons=[]
    for b in BUDGETS:
        for o in ('original','similarity'):
            c=lookup[(f'cms_{b}k',o)];e=lookup[('exact',o)];l=lookup[('lru',o)]
            comparisons.append(dict(budget_kib=b,order=o,**compare(c,e,l),grouping_gain=lookup[(f'cms_{b}k','similarity')]['e2e_qps']/lookup[(f'cms_{b}k','original')]['e2e_qps']-1))
    write(root/'capacity_comparison.csv',comparisons)
    eligible=[b for b in BUDGETS if all(x['meets_targets'] for x in comparisons if x['budget_kib']==b)]
    result=dict(correctness='PASS',runs=len(rows),recall=ref[2],eligible_kib=eligible,minimum_observed_kib=min(eligible) if eligible else None,provisional=m['repeats']<5,max_qps_cv=max(x['qps_cv'] for x in summary))
    (root/'validation_summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
