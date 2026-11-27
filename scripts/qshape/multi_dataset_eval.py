"""One dataset/config per output directory; reuse frozen run_sharing.sh."""
import argparse, os, random, subprocess, fcntl, json
from pathlib import Path
from audit_dataset import audit
from final_factorial import POLICIES, ck, digest, atomic, load, device_stat
from validate_multi_dataset import prefix, receipt, inspect, validate
def plan(c):
    ck(c['repeats'] in (1,3,5),'repeats')
    ids=c['policies'];ck('A0' in ids and len(set(ids))==len(ids) and set(ids)<=set(POLICIES),'policies')
    out=[]
    for r in range(1,c['repeats']+1):
        a=list(ids);random.Random(20261127+r).shuffle(a);out.extend((r,i) for i in a)
    return out
def config(p):
    c=load(p)
    for k in ('binary','query','gt','index_prefix','base'):
        if c.get(k):c[k]=str(Path(c[k]).resolve())
    for k in ('threads','beam','l','k','ready_mib'):ck(type(c[k]) is int and c[k]>0,k)
    ck(c['l']>=c['k'] and 0<=c['min_recall']<=100,'search/recall')
    plan(c);return c
def run(c,root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ck(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked changes')
        m=dict(config=c,audit=audit(c),cases=[list(x) for x in plan(c)],commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),policy_map={k:list(v) for k,v in POLICIES.items()},runner_sha256=digest('scripts/qshape/run_sharing.sh'))
        mf=root/'manifest.json'
        if mf.exists():ck(load(mf)==m,'resume configuration mismatch')
        else:atomic(mf,m)
        for r,i in plan(c):
            p=prefix(root,r,i);p.parent.mkdir(parents=True,exist_ok=True);rec=p.parent/'receipt.json'
            if rec.exists():ck(load(rec)==receipt(p,c['l']),'resume receipt');continue
            o,s,policy=POLICIES[i]
            env=dict(os.environ,SEARCH_BIN=c['binary'],INDEX_PREFIX=c['index_prefix'],QUERY_FILE=c['query'],GT_FILE=c['gt'],OUT=str(p.parent),REPEATS='1',MODES='stats',ORDERS=o,SHARING_MODES=s,CACHE_ONLY='1',RETENTION='frequency' if policy in ('exact','cms_512k') else policy,FREQUENCY_MODE='cms' if policy=='cms_512k' else 'exact',FREQUENCY_BUDGET='524288',FREQUENCY_DEPTH='4',READY_BUDGET=str(c['ready_mib']*1048576),BUDGET='67108864',GROUP_SIZE='256',CANDIDATE_POOL='512',T=str(c['threads']),W=str(c['beam']),L=str(c['l']),K=str(c['k']),CACHES='0',DATA_TYPE=c['data_type'],DIST_FN='l2',HASH_POLICY='mixed',READY_STATS='0',BREAKDOWN='0',SHARD_STATS='0',REUSE_STATS='0',REGION_TRACE='0',FREQUENCY_SHADOW='0',TIMEOUT=str(c.get('timeout',3600)))
            dev=c.get('device','');before=device_stat(dev)
            subprocess.run(['/usr/bin/time','-f','%U,%S,%M,%e','-o',str(p.parent/'resource.csv'),'bash','scripts/qshape/run_sharing.sh'],env=env,check=True)
            after=device_stat(dev);delta={k:after[k]-before[k] for k in ('reads','sectors','writes')} if before else None
            ck(delta is None or min(delta.values())>=0,'device reset')
            u,s,rss,wall=map(float,(p.parent/'resource.csv').read_text().strip().split(','))
            atomic(p.parent/'telemetry.json',dict(device_delta=delta,device_before=before,device_after=after,user_s=u,system_s=s,peak_rss_kib=rss,wall_s=wall))
            row,_=inspect(p,i,m['audit']['queries'],c['ready_mib']*1048576,c['l']);ck(row['recall']>=c['min_recall'],'recall floor')
            atomic(rec,receipt(p,c['l']));print('PASS',r,i,flush=True)
        validate(root)
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['audit','run','validate']);p.add_argument('--config',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    if a.action=='validate':validate(a.out.resolve())
    elif a.action=='audit':print(json.dumps(audit(config(a.config)),indent=2))
    else:run(config(a.config),a.out.resolve())
if __name__=='__main__':main()
