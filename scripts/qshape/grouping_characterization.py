"""P3.3-A1: fixed-order cost isolation; no future access trace."""
import argparse, hashlib, json, os, random, statistics, subprocess, fcntl, shutil
from pathlib import Path
from validate_frequency_capacity import ck, read, write, recall, quantile, validate_query
from concurrent_integration import digest, files
POLICIES={f'Z{i}':(o,'inflight','cms_512k' if i<4 else 'none')
          for i,o in enumerate(('original','random','similarity','oracle')*2)}
N=10000
def plan(repeats):
    result=[]
    for r in range(1,repeats+1):
        ids=list(POLICIES);random.Random(42+r).shuffle(ids)
        result.extend((r,i) for i in ids)
    return result
def permutation(rows,n):
    ck(len(rows)==n,'query count')
    rows=sorted(rows,key=lambda x:int(x['execution_id']))
    ck([int(x['execution_id']) for x in rows]==list(range(n)),'execution permutation')
    order=[int(x['query_id']) for x in rows]
    ck(sorted(order)==list(range(n)),'query permutation')
    ck(all(int(x['group_id'])==j//256 for j,x in enumerate(rows)),'group mapping')
    return order
def order_text(order):
    return ''.join(str(i)+'\n' for i in order)
def load_order(path,n):
    order=list(map(int,path.read_text().split()))
    ck(len(order)==n and sorted(order)==list(range(n)),'invalid permutation')
    return order
def atomic_json(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)
def prepare(source,out):
    source=source.resolve();out=out.resolve()
    m=json.loads((source/'manifest.json').read_text())
    ck(m['repeats']==3 and m['queries']==N,'source formal matrix')
    ck(m['policies']['A7']==['similarity','inflight','cms_512k'],'source A7 mapping')
    orders=[];times=[];hashes={}
    for r in range(1,4):
        p=source/str(r)/'A7'/'1_similarity_inflight_stats'
        fs=files(p);receipt=json.loads((p.parent/'receipt.json').read_text())
        ck(receipt=={f.name:digest(f) for f in fs},'source receipt')
        orders.append(permutation(read(fs[1]),N))
        g=read(fs[2]);ck(len(g)==1 and g[0]['policy']=='similarity' and int(g[0]['group_size'])==256 and int(g[0]['candidate_pool'])==512 and int(g[0]['seed'])==42,'source grouping config')
        times.append(int(g[0]['grouping_ns']))
        hashes[str(fs[1])]=digest(fs[1])
    ck(all(o==orders[0] for o in orders),'source orders differ')
    out.mkdir(parents=True,exist_ok=False)
    p=out/'similarity_order.txt';p.write_text(order_text(orders[0]))
    atomic_json(out/'permutation.json',dict(queries=N,sha256=digest(p),source_query_sha256=m['query_sha256'],source_manifest_sha256=digest(source/'manifest.json'),source_query_csv=hashes,historical_grouping_ns=times))
    print('PASS: fixed permutation',digest(p))
def prefix(root,r,i):
    return root/str(r)/i/'search'
def inspect(p,i,n,expected):
    o,s,policy=POLICIES[i];budget=524288 if policy=='cms_512k' else 0
    fs=files(p);q=read(fs[1]);ck(len(q)==n,'query count')
    for k in ('query_id','execution_id'):ck(sorted(int(x[k]) for x in q)==list(range(n)),k)
    order=permutation(q,n)
    if o in ('similarity','oracle'):ck(order==expected,'fixed permutation mismatch')
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
    row.update(grouping_ns=gn,search_ns=sn,e2e_ns=en,comparisons=int(g['comparisons']),order_sha256=hashlib.sha256(order_text(order).encode()).hexdigest())
    ck(row['comparisons']>0 if o=='similarity' else row['comparisons']==0,'comparison count')
    return row,(digest(fs[3]),digest(fs[4]),row['recall'],logical)

def config(a):
    e={k:str(Path(os.environ[k]).resolve()) for k in ('SEARCH_BIN','INDEX_PREFIX','QUERY_FILE','GT_FILE')}
    dtype=os.environ.get('DATA_TYPE','float');ck(dtype=='float','A1 requires DATA_TYPE=float')
    p=a.permutation.resolve();meta=json.loads((p.parent/'permutation.json').read_text())
    load_order(p,N)
    ck(digest(p)==meta['sha256'] and digest(e['QUERY_FILE'])==meta['source_query_sha256'],'permutation provenance')
    ck(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked changes')
    return dict(repeats=a.repeats,queries=N,inputs=e,data_type=dtype,binary_sha256=digest(e['SEARCH_BIN']),query_sha256=digest(e['QUERY_FILE']),gt_sha256=digest(e['GT_FILE']),commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),permutation_sha256=digest(p),provenance=meta,policies={k:list(v) for k,v in POLICIES.items()},cases=[list(x) for x in plan(a.repeats)])
def command(c,p,i,order):
    o,_,policy=POLICIES[i];e=c['inputs']
    args=[e['SEARCH_BIN'],'--data_type',c['data_type'],'--dist_fn','l2','--index_path_prefix',e['INDEX_PREFIX'],'--query_file',e['QUERY_FILE'],'--gt_file',e['GT_FILE'],'--result_path',str(p),'-K','10','-L','100','-T','64','-W','64','--num_nodes_to_cache','0']
    opts={'enable':1,'trace':0,'grouping':o,'group-size':256,'candidate-pool':512,'seed':42,'scheduler':'reorder','hash':'mixed','shard-stats':0,'breakdown':0,'reuse-stats':0,'retention':'frequency' if policy=='cms_512k' else 'none','frequency-shadow':0,'frequency-mode':'cms' if policy=='cms_512k' else 'exact','frequency-budget':524288,'frequency-depth':4,'ready-budget':16777216,'ready-ttl-us':5000,'ready-stats':0,'region-trace':0,'region-event-limit':4096,'sharing':'inflight','inflight-budget':67108864,'output-prefix':str(p)}
    if o=='oracle':opts['oracle-file']=str(order)
    for k,v in opts.items():args.extend(['--qshape-'+k,str(v)])
    return args
def receipt(p):
    return {f.name:digest(f) for f in files(p)}
def run(a):
    root=a.out.resolve();root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        c=config(a);m=root/'manifest.json';order=root/'similarity_order.txt'
        if m.exists():
            ck(json.loads(m.read_text())==c,'resume configuration mismatch')
            ck(digest(order)==c['permutation_sha256'],'saved permutation changed')
        else:
            shutil.copyfile(a.permutation,order);atomic_json(m,c)
        expected=load_order(order,N)
        for r,i in plan(a.repeats):
            p=prefix(root,r,i);p.parent.mkdir(parents=True,exist_ok=True);rec=p.parent/'receipt.json'
            if rec.exists():
                ck(json.loads(rec.read_text())==receipt(p),'resume receipt mismatch')
                inspect(p,i,N,expected);continue
            for f in files(p):
                if f.exists():f.unlink()
            args=command(c,p,i,order);atomic_json(p.parent/'command.json',args)
            with files(p)[0].open('w') as log:
                subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=900,check=True)
            inspect(p,i,N,expected);atomic_json(rec,receipt(p))
            print('PASS',r,i,flush=True)
        validate(root)
def paired(rows,repeats):
    result=[]
    for r in range(1,repeats+1):
        z={x['case']:x for x in rows if x['repeat']==r}
        for offset in (0,4):
            a,b,c,d=[z[f'Z{i+offset}'] for i in range(4)]
            result.append(dict(repeat=r,retention='cms' if offset==0 else 'none',load_gain=d['e2e_qps']/c['e2e_qps']-1,precomputed_gain=d['e2e_qps']/a['e2e_qps']-1,similarity_vs_random=d['e2e_qps']/b['e2e_qps']-1,search_gain=d['search_qps']/a['search_qps']-1,read_reduction=1-d['submitted_reads']/a['submitted_reads'],compute_saved_ms=c['grouping_ms']-d['grouping_ms'],search_saved_ms=(a['search_ns']-d['search_ns'])/1e6,full_precomputed_ms=(c['grouping_ns']+d['e2e_ns'])/1e6))
    return result
def validate(root):
    c=json.loads((root/'manifest.json').read_text());cases=plan(c['repeats'])
    ck(c['repeats'] in (1,3) and c['cases']==[list(x) for x in cases] and c['policies']=={k:list(v) for k,v in POLICIES.items()} and c['data_type']=='float' and c['queries']==N,'manifest matrix')
    order=root/'similarity_order.txt';ck(digest(order)==c['permutation_sha256']==c['provenance']['sha256'],'permutation hash')
    expected=load_order(order,N);rows=[];ref=None;random_hash=None
    for r,i in cases:
        p=prefix(root,r,i)
        ck(json.loads((p.parent/'receipt.json').read_text())==receipt(p),'receipt')
        ck(json.loads((p.parent/'command.json').read_text())==command(c,p,i,order),'command mismatch')
        row,sig=inspect(p,i,N,expected)
        if ref is None:ref=sig
        ck(sig==ref,'cross-config result or logical requests')
        if i in ('Z1','Z5'):
            if random_hash is None:random_hash=row['order_sha256']
            ck(random_hash==row['order_sha256'],'random order changed')
        row['repeat']=r;rows.append(row)
    write(root/'grouping_metrics.csv',rows)
    summary=[]
    for i in POLICIES:
        z=[x for x in rows if x['case']==i]
        d=dict(case=i,**{k:statistics.mean(x[k] for x in z) for k,v in z[0].items() if k!='repeat' and isinstance(v,(int,float))})
        d['qps_cv']=statistics.stdev(x['e2e_qps'] for x in z)/d['e2e_qps'] if len(z)>1 else 0
        summary.append(d)
    write(root/'grouping_summary.csv',summary);write(root/'grouping_paired.csv',paired(rows,c['repeats']))
    print(f'PASS {len(rows)}/{len(cases)}')
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','validate']);p.add_argument('--out',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--permutation',type=Path);p.add_argument('--repeats',type=int,choices=[1,3],default=3);a=p.parse_args()
    if a.action=='prepare':
        ck(a.source is not None,'--source required');prepare(a.source,a.out)
    elif a.action=='run':
        ck(a.permutation is not None,'--permutation required');run(a)
    else:validate(a.out.resolve())
if __name__=='__main__':main()
