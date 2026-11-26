import argparse, hashlib, json, os, random, statistics, subprocess
from pathlib import Path
from validate_frequency_capacity import ck, read, write, recall, quantile, validate_query
POLICIES={**{f'A{i}':('similarity' if i&1 else 'original','inflight' if i&2 else 'off','cms_512k' if i&4 else 'none') for i in range(8)},'R1':('similarity','inflight','lru'),'R2':('similarity','inflight','exact')}
def plan(repeats):
    result=[]
    for r in range(1,repeats+1):
        ids=list(POLICIES);random.Random(42+r).shuffle(ids)
        result.extend((r,i) for i in ids)
    return result
def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def prefix(root,r,i):
    o,s,p=POLICIES[i]
    return root/str(r)/i/f'1_{o}_{s}_stats'
def files(p):
    return [Path(str(p)+s) for s in ('.log','_L100_run0_queries.csv','_L100_run0_grouping.csv','_100_idx_uint32.bin','_100_dists_float.bin')]
def inspect(p,i,n):
    o,s,policy=POLICIES[i];budget=524288 if policy=='cms_512k' else 0
    fs=files(p);q=read(fs[1]);ck(len(q)==n,'query count')
    for k in ('query_id','execution_id'):ck(sorted(int(x[k]) for x in q)==list(range(n)),k)
    for x in q:
        validate_query(x,policy,budget)
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
    row=dict(case=i,recall=recall(fs[0]),e2e_qps=qp,search_qps=n*1e9/sn,grouping_ms=gn/1e6,mean_us=statistics.mean(lat),p99_us=quantile(lat,.99),p999_us=quantile(lat,.999),response_p999_us=quantile(response,.999))
    for k in 'reader_requests reader_bytes submitted_reads submitted_bytes shared_hits ready_hits ready_admissions ready_capacity_evictions bypass lookup_ns wait_copy_ns'.split():row[k]=sum(int(x[k]) for x in q)
    for k in 'peak_ready_bytes peak_inflight_bytes peak_shared_bytes frequency_counter_bytes frequency_shard_entries'.split():row[k]=max(int(x[k]) for x in q)
    row['inflight_hits']=row['shared_hits']-row['ready_hits']
    logical=sorted(tuple(int(x[k]) for k in ('query_id','reader_requests','reader_bytes','logical_node_reads','static_cache_hits')) for x in q)
    return row,(digest(fs[3]),digest(fs[4]),row['recall'],logical)
def config(a):
    e={k:os.environ[k] for k in ('SEARCH_BIN','INDEX_PREFIX','QUERY_FILE','GT_FILE')}
    for k in e:e[k]=str(Path(e[k]).resolve())
    return dict(repeats=a.repeats,queries=10000,inputs=e,binary_sha256=digest(e['SEARCH_BIN']),query_sha256=digest(e['QUERY_FILE']),gt_sha256=digest(e['GT_FILE']),commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),cases=[list(x) for x in plan(a.repeats)])
def run(a):
    root=a.out.resolve();root.mkdir(parents=True,exist_ok=True);c=config(a);m=root/'manifest.json'
    ck(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked changes')
    if m.exists():ck(json.loads(m.read_text())==c,'resume configuration mismatch')
    else:m.write_text(json.dumps(c,indent=2))
    for r,i in plan(a.repeats):
        p=prefix(root,r,i);receipt=p.parent/'receipt.json'
        if receipt.exists():
            ck(json.loads(receipt.read_text())=={f.name:digest(f) for f in files(p)},'resume receipt mismatch');inspect(p,i,c['queries']);continue
        o,s,policy=POLICIES[i]
        env=dict(os.environ,**c['inputs']);env.update(OUT=str(p.parent),REPEATS='1',MODES='stats',ORDERS=o,SHARING_MODES=s,CACHE_ONLY='1',RETENTION='frequency' if policy in ('exact','cms_512k') else policy,FREQUENCY_MODE='cms' if policy=='cms_512k' else 'exact',FREQUENCY_BUDGET='524288',FREQUENCY_DEPTH='4',READY_BUDGET='16777216',BUDGET='67108864',GROUP_SIZE='256',CANDIDATE_POOL='512',T='64',W='64',L='100',K='10',CACHES='0',DATA_TYPE='uint8',DIST_FN='l2',HASH_POLICY='mixed',READY_STATS='0',BREAKDOWN='0',SHARD_STATS='0',REUSE_STATS='0',REGION_TRACE='0',FREQUENCY_SHADOW='0',TIMEOUT='900')
        subprocess.run(['bash','scripts/qshape/run_sharing.sh'],env=env,check=True)
        inspect(p,i,c['queries'])
        tmp=receipt.with_suffix('.tmp');tmp.write_text(json.dumps({f.name:digest(f) for f in files(p)}));tmp.replace(receipt)
    validate(root)
def validate(root):
    c=json.loads((root/'manifest.json').read_text());cases=plan(c['repeats']);ck(c['repeats'] in (1,3) and c['cases']==[list(x) for x in cases],'matrix')
    rows=[];ref=None
    for r,i in cases:
        p=prefix(root,r,i);ck(json.loads((p.parent/'receipt.json').read_text())=={f.name:digest(f) for f in files(p)},'receipt')
        row,signature=inspect(p,i,c['queries'])
        if ref is None:ref=signature
        ck(signature==ref,'cross-config result or logical requests')
        row['repeat']=r;rows.append(row)
    write(root/'integration_metrics.csv',rows)
    summary=[]
    for i in POLICIES:
        z=[x for x in rows if x['case']==i];d=dict(case=i,**{k:statistics.mean(x[k] for x in z) for k in z[0] if k not in ('case','repeat')})
        d['qps_cv']=statistics.stdev(x['e2e_qps'] for x in z)/d['e2e_qps'] if len(z)>1 else 0;summary.append(d)
    write(root/'integration_summary.csv',summary)
    paired=[]
    for r in range(1,c['repeats']+1):
        z={x['case']:x for x in rows if x['repeat']==r}
        q=lambda i:z[i]['e2e_qps']
        paired.append(dict(repeat=r,speedup=q('A7')/q('A0'),grouping_gain=q('A7')/q('A6')-1,sharing_gain=q('A7')/q('A5')-1,retention_gain=q('A7')/q('A4')-1,best_pair_gain=q('A7')/max(q(i) for i in ('A4','A5','A6'))-1,cms_exact=q('A7')/q('R2'),cms_lru=q('A7')/q('R1'),read_reduction=1-z['A7']['submitted_reads']/z['A0']['submitted_reads']))
    write(root/'integration_paired.csv',paired)
    print(f'PASS {len(rows)}/{len(cases)}')
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','validate']);p.add_argument('--out',type=Path,required=True);p.add_argument('--repeats',type=int,choices=[1,3],default=3);a=p.parse_args()
    if a.action=='run':run(a)
    else:validate(a.out)
if __name__=='__main__':main()
