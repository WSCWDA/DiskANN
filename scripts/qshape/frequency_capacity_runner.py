import csv,json,os,random,subprocess
from pathlib import Path
BUDGETS=(64,128,256,512,1024,2048)
POLICIES=('none','bounded-local','lru','exact')+tuple('cms_'+str(b)+'k' for b in BUDGETS)
def plan(repeats,seed):
    rng=random.Random(seed)
    rows=[]
    for r in range(1,repeats+1):
        cases=[(p,o) for p in POLICIES for o in ('original','similarity')]
        rng.shuffle(cases)
        rows.extend(dict(run=r,position=i+1,policy=p,order=o) for i,(p,o) in enumerate(cases))
    return rows
def main():
    root=Path(os.environ['OUT']).resolve()
    repeats=int(os.getenv('REPEATS','5'));seed=int(os.getenv('CAPACITY_SEED','42'))
    if repeats<1:raise ValueError('repeats must be positive')
    env=dict(os.environ,T='64',W='64',L='100',K='10',CACHES='0',GROUP_SIZE='256',CANDIDATE_POOL='512',BUDGET='67108864',READY_BUDGET='16777216',FREQUENCY_DEPTH='4',HASH_POLICY='mixed',BREAKDOWN='0',REUSE_STATS='0',SHARD_STATS='0',REGION_TRACE='0',READY_STATS='0',CACHE_ONLY='0',REPEATS='1',MODES='stats',SHARING_MODES='inflight')
    for k in ('SEARCH_BIN','INDEX_PREFIX','QUERY_FILE','GT_FILE'): 
        if not env.get(k):raise ValueError('missing '+k)
    rows=plan(repeats,seed)
    root.mkdir(parents=True,exist_ok=False)
    manifest=dict(repeats=repeats,seed=seed,queries=int(os.getenv('QUERIES','10000')),settings={k:env[k] for k in ('T','W','L','K','CACHES','GROUP_SIZE','CANDIDATE_POOL','BUDGET','READY_BUDGET','FREQUENCY_DEPTH','HASH_POLICY','SEARCH_BIN','INDEX_PREFIX','QUERY_FILE','GT_FILE')},commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),cases=rows)
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
    with (root/'execution_order.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for row in rows:
        p,o,r=row['policy'],row['order'],row['run']
        cms=p.startswith('cms_')
        case=dict(env,OUT=str(root/p/str(r)/o),ORDERS=o,RETENTION='frequency' if cms or p=='exact' else p,FREQUENCY_MODE='cms' if cms else 'exact',FREQUENCY_BUDGET=str(int(p[4:-1])*1024 if cms else 1048576))
        print('RUN',row,flush=True)
        subprocess.run(['bash',str(Path(__file__).with_name('run_sharing.sh'))],env=case,check=True)
    (root/'runner_complete').write_text(str(len(rows))+'\n')
if __name__=='__main__':main()
