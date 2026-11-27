"""Final factorial evaluation; fixed production mechanisms, no oracle."""
import argparse, hashlib, json, os, random, statistics, subprocess, fcntl, time
from pathlib import Path
from concurrent_integration import POLICIES, digest, files
from validate_frequency_capacity import ck, read, write, recall, quantile

def validate_query(x,policy,budget,ready):
    n=lambda k:int(x[k])
    active=policy!='none';freq=policy=='exact' or policy.startswith('cms_')
    ck(n('reader_requests')==n('submitted_reads')+n('shared_hits'),'request conservation')
    ck(n('reader_bytes')==n('submitted_bytes')+n('shared_bytes'),'byte conservation')
    ck(n('completed_reads')==n('submitted_reads') and n('completion_errors')==0,'completion')
    ck(0<=n('ready_hits')<=n('shared_hits') and 0<=n('ready_hit_bytes')<=n('shared_bytes'),'hits')
    ck(0<=n('peak_ready_bytes')<=(ready if active else 0) and 0<=n('peak_inflight_bytes')<=67108864 and n('peak_shared_bytes')<=67108864+(ready if active else 0),'budget')
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

def inspect(p,i,n,ready):
    o,s,policy=POLICIES[i];budget=524288 if policy=='cms_512k' else 0
    fs=files(p);q=read(fs[1]);ck(len(q)==n,'query count')
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

def plan(stage):
    if stage=='smoke':return [(1,64,16,i) for i in POLICIES]
    cases=[]
    for r in range(1,6):
        block=[(r,t,b,i) for t in (16,64) for b in (4,16,64) for i in POLICIES if (POLICIES[i][2]!='none' or b==16) and ((t==64 and b==16)==(stage=='core'))]
        random.Random(20261127+r).shuffle(block);cases.extend(block)
    return cases

def prefix(root,c):
    r,t,b,i=c;o,s,_=POLICIES[i]
    return root/f'T{t}_B{b}'/str(r)/i/f'1_{o}_{s}_stats'

def atomic(p,x):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,indent=2));tmp.replace(p)
def load(p):return json.loads(p.read_text())
def receipt(p):return {f.name:digest(f) for f in files(p)}
def config(a):
    inputs={k:str(Path(os.environ[k]).resolve()) for k in ('SEARCH_BIN','INDEX_PREFIX','QUERY_FILE','GT_FILE')}
    ix=Path(inputs['INDEX_PREFIX']);index_files=sorted(p for p in ix.parent.glob(ix.name+'*') if p.is_file())
    ck(index_files,'index files missing')
    return dict(stage=a.stage,cases=[list(c) for c in plan(a.stage)],queries=10000,data_type=os.environ.get('DATA_TYPE','float'),dist_fn='l2',inputs=inputs,hashes={k:digest(inputs[k]) for k in ('SEARCH_BIN','QUERY_FILE','GT_FILE')},index_hashes={str(p):digest(p) for p in index_files},commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),policies={k:list(v) for k,v in POLICIES.items()},device=a.device,runner_sha256=digest(__file__))
def device_stat(dev):
    if not dev:return None
    a=list(map(int,(Path('/sys/class/block')/dev/'stat').read_text().split()))
    return dict(reads=a[0],sectors=a[2],writes=a[4],inflight=a[8])
def run(a):
    root=a.out.resolve();root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ck(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked changes')
        m=config(a);mf=root/'manifest.json'
        if mf.exists():ck(load(mf)==m,'resume configuration mismatch')
        else:atomic(mf,m)
        for c in plan(a.stage):
            r,t,b,i=c;p=prefix(root,c);p.parent.mkdir(parents=True,exist_ok=True);rec=p.parent/'receipt.json';tele=p.parent/'telemetry.json'
            if rec.exists():
                ck(load(rec)==dict(files=receipt(p),telemetry=digest(tele)),'receipt mismatch')
                inspect(p,i,m['queries'],b*1048576);continue
            o,s,policy=POLICIES[i]
            env=dict(os.environ,**m['inputs']);env.update(OUT=str(p.parent),REPEATS='1',MODES='stats',ORDERS=o,SHARING_MODES=s,CACHE_ONLY='1',RETENTION='frequency' if policy in ('exact','cms_512k') else policy,FREQUENCY_MODE='cms' if policy=='cms_512k' else 'exact',FREQUENCY_BUDGET='524288',FREQUENCY_DEPTH='4',READY_BUDGET=str(b*1048576),BUDGET='67108864',GROUP_SIZE='256',CANDIDATE_POOL='512',T=str(t),W='64',L='100',K='10',CACHES='0',DATA_TYPE=m['data_type'],DIST_FN='l2',HASH_POLICY='mixed',READY_STATS='0',BREAKDOWN='0',SHARD_STATS='0',REUSE_STATS='0',REGION_TRACE='0',FREQUENCY_SHADOW='0',TIMEOUT='900')
            before=device_stat(a.device);start=time.monotonic_ns()
            subprocess.run(['/usr/bin/time','-f','%U,%S,%M,%e','-o',str(p.parent/'resource.csv'),'bash','scripts/qshape/run_sharing.sh'],env=env,check=True)
            elapsed=time.monotonic_ns()-start;after=device_stat(a.device)
            user,sys,rss,wall=map(float,(p.parent/'resource.csv').read_text().strip().split(','))
            delta={k:after[k]-before[k] for k in ('reads','sectors','writes')} if before else None
            ck(delta is None or min(delta.values())>=0,'device counter reset')
            atomic(tele,dict(device_delta=delta,device_before=before,device_after=after,user_s=user,system_s=sys,peak_rss_kib=rss,process_wall_s=wall,runner_wall_ns=elapsed))
            inspect(p,i,m['queries'],b*1048576)
            atomic(rec,dict(files=receipt(p),telemetry=digest(tele)));print('PASS',c,flush=True)
        validate(root)
def effects(z):
    # log QPS factorial contrasts, averaged over other factors.
    import math
    out={}
    for mask in range(1,8):
        out['effect_'+''.join(k for bit,k in ((1,'G'),(2,'S'),(4,'R')) if mask&bit)]=sum((1 if ((j&mask).bit_count()%2)==mask.bit_count()%2 else -1)*math.log(z['A'+str(j)]['e2e_qps']) for j in range(8))/4
    return out
def validate(root):
    m=load(root/'manifest.json');cases=plan(m['stage']);ck(m['cases']==[list(c) for c in cases],'matrix')
    ck(m['policies']=={k:list(v) for k,v in POLICIES.items()},'policies')
    rows=[];ref=None
    for c in cases:
        r,t,b,i=c;p=prefix(root,c);tele=p.parent/'telemetry.json'
        ck(load(p.parent/'receipt.json')==dict(files=receipt(p),telemetry=digest(tele)),'receipt')
        row,sig=inspect(p,i,m['queries'],b*1048576)
        if ref is None:ref=sig
        ck(sig==ref,'cross-config results or logical work')
        x=load(tele);delta=x['device_delta']
        row.update(repeat=r,threads=t,ready_mib=b if POLICIES[i][2]!='none' else 0,ids_sha256=sig[0],dists_sha256=sig[1],user_s=x['user_s'],system_s=x['system_s'],peak_rss_kib=x['peak_rss_kib'],process_wall_s=x['process_wall_s'],device_reads=delta['reads'] if delta else '',device_read_bytes=delta['sectors']*512 if delta else '',device_writes=delta['writes'] if delta else '')
        rows.append(row)
    write(root/'metrics.csv',rows)
    summary=[]
    for key in sorted({(x['threads'],x['ready_mib'],x['case']) for x in rows}):
        g=[x for x in rows if (x['threads'],x['ready_mib'],x['case'])==key]
        d=dict(threads=key[0],ready_mib=key[1],case=key[2],repeats=len(g))
        for k,v in g[0].items():
            if k not in d and k!='repeat' and isinstance(v,(int,float)):d[k]=statistics.mean(x[k] for x in g)
        d['qps_cv']=statistics.stdev(x['e2e_qps'] for x in g)/d['e2e_qps'] if len(g)>1 else 0
        summary.append(d)
    write(root/'summary.csv',summary)
    paired=[]
    for r,t,b in sorted({(x['repeat'],x['threads'],x['ready_mib']) for x in rows if x['ready_mib']}):
        z={x['case']:x for x in rows if x['repeat']==r and x['threads']==t and x['ready_mib'] in (0,b)}
        if len(z)!=10:continue
        q=lambda i:z[i]['e2e_qps']
        paired.append(dict(repeat=r,threads=t,ready_mib=b,speedup=q('A7')/q('A0'),grouping_gain=q('A7')/q('A6')-1,sharing_gain=q('A7')/q('A5')-1,retention_gain=q('A7')/q('A4')-1,cms_exact=q('A7')/q('R2'),cms_lru=q('A7')/q('R1'),read_reduction=1-z['A7']['submitted_reads']/z['A0']['submitted_reads'],**effects(z)))
    if paired:write(root/'paired.csv',paired)
    outputs=['metrics.csv','summary.csv']+(['paired.csv'] if paired else [])
    atomic(root/'validation_summary.json',dict(status='PASS',runs=len(rows),recall=ref[2],paired_blocks=len(paired),files={k:digest(root/k) for k in outputs}))
    print(f'PASS {len(rows)}/{len(cases)}')
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','validate']);p.add_argument('--stage',choices=['smoke','core','sensitivity'],default='smoke');p.add_argument('--out',type=Path,required=True);p.add_argument('--device',default='');a=p.parse_args()
    if a.action=='run':run(a)
    else:validate(a.out.resolve())
if __name__=='__main__':main()
