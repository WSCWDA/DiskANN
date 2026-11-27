"""Reuse verified B2.1-A streams; mandatory same-stream C++ baseline cross-check."""
import argparse,json,statistics,time,fcntl,subprocess
from pathlib import Path
import numpy as np
from grouping_characterization import digest,atomic_json
from validate_frequency_capacity import ck,write
from validate_retention_capacity import validate_row
from retention_trace import fingerprint
from dual_timescale import slots
from budgeted_oracle import Oracle,BPS,HORIZON,future_index,validate as check_row

def plan(n):
    return [(r,o,p) for r in range(1,n+1) for o in ('original','similarity') for p in BPS]
def load(p):return json.loads(p.read_text())
def source_check(source,repeats):
    m=load(source/'manifest.json');v=load(source/'validation_summary.json')
    ck(v['status']=='PASS' and v['runs']==48 and m['repeats']==3 and m['limit']==0,'need full B2.1-A source')
    for k,h in v['files'].items():ck(digest(source/k)==h,'source summary hash')
    streams={}
    for r,o,p in plan(repeats):
        if p!='O0':continue
        path=source/f'{r}_{o}.npy';info=load(path.with_suffix('.json'))
        ck(digest(path)==info['sha256'],'source stream hash')
        streams[f'{r}_{o}']=info
    ck(len({x['multiset'] for x in streams.values()})==1,'multiset')
    return streams
def cpp_check(root,key,ids,bench,baseline):
    path=root/(key+'.ids')
    with path.open('w') as f:f.writelines(str(int(k)//4096)+'\n' for k in ids)
    c=dict(policy='cms',n=str(int(max(ids))//4096+1),ops=str(len(ids)),skew='0',seed='42',ready_budget='16777216',meta_budget='524288',mode='perf')
    dest=root/(key+'_cpp.csv')
    try:
        with dest.open('w') as f:subprocess.run([str(bench),*[c[k] for k in ('policy','n','ops','skew','seed','ready_budget','meta_budget','mode')],str(path)],stdout=f,check=True,timeout=1800)
        x=validate_row(dest,c)
        ck(x['fingerprint']==fingerprint(int(k)//4096 for k in ids) and x['observed']==len(set(ids)) and x['saturations']==0,'C++ input')
        for a,b in [('hits','hits'),('reads','misses'),('admissions','main_inserts'),('rejects','rejects'),('evictions','main_evictions'),('resident','main_resident'),('unused_evictions','main_unused')]:
            ck(x[a]==baseline[b],f'C++ baseline mismatch {key} {a}: {x[a]} != {baseline[b]}')
        atomic_json(root/(key+'_cpp.json'),dict(config=c,sha256=digest(dest)))
    finally:path.unlink(missing_ok=True)
def run(a):
    source=a.source.resolve();root=a.out.resolve();bench=a.bench.resolve()
    ck(root!=source and bench.is_file(),'output/benchmark')
    root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        streams=source_check(source,a.repeats)
        cfg=dict(source=str(source),source_manifest=digest(source/'manifest.json'),source_validation=digest(source/'validation_summary.json'),streams=streams,repeats=a.repeats,limit=a.limit,horizon=HORIZON,bench=str(bench),bench_sha256=digest(bench),cases=[list(x) for x in plan(a.repeats)],code={k:digest(Path(__file__).with_name(k)) for k in ('run_budgeted_oracle.py','budgeted_oracle.py','dual_timescale.py')})
        mf=root/'manifest.json'
        if mf.exists():ck(load(mf)==cfg,'resume manifest')
        else:atomic_json(mf,cfg)
        for key,info in streams.items():
            r,o=key.split('_');r=int(r)
            ids=np.load(source/(key+'.npy'),allow_pickle=False)
            ck(ids.ndim==1 and ids.dtype.kind=='u' and ids.dtype.itemsize==8 and len(ids)==info['ops'] and np.all(ids%4096==0),'stream format')
            ids=ids[:a.limit or len(ids)];ck(len(ids)>0,'empty stream')
            positions=future_index(ids)
            for p in BPS:
                dest=root/f'{key}_{p}.json';receipt=dest.with_suffix('.receipt.json')
                if receipt.exists():ck(load(receipt)=={'sha256':digest(dest)},'case receipt');d=load(dest)
                else:
                    slots.cache_clear();model=Oracle(p,len(ids),positions);t=time.perf_counter_ns()
                    for k in ids:model.access(int(k))
                    d=model.result();elapsed=time.perf_counter_ns()-t;check_row(d,p)
                    atomic_json(dest,dict(counters=d,repeat=r,order=o,policy=p,input_sha256=info['sha256'],elapsed_ns=elapsed))
                    atomic_json(receipt,dict(sha256=digest(dest)));d=load(dest)
                if p=='O0':
                    if not a.limit:
                        old=load(source/f'{key}_R1.json')
                        for k in ('ops','hits','misses','main_inserts','main_evictions','main_unused','main_resident','rejects'):
                            ck(old[k]==d['counters'][k],'B2.1-A R1 mismatch '+k)
                    cpp_check(root,key,ids,bench,d['counters'])
                print('PASS',key,p,flush=True)
        validate(root)
def validate(root):
    cfg=load(root/'manifest.json');rows=[]
    ck(cfg['cases']==[list(x) for x in plan(cfg['repeats'])] and cfg['horizon']==HORIZON,'matrix')
    source=Path(cfg['source'])
    ck(digest(source/'manifest.json')==cfg['source_manifest'] and digest(source/'validation_summary.json')==cfg['source_validation'],'source changed')
    ck(source_check(source,cfg['repeats'])==cfg['streams'],'stream provenance')
    for r,o,p in plan(cfg['repeats']):
        key=f'{r}_{o}';path=root/f'{key}_{p}.json';info=cfg['streams'][key]
        ck(load(path.with_suffix('.receipt.json'))=={'sha256':digest(path)},'receipt')
        d=load(path);c=d['counters'];check_row(c,p)
        ck((d['repeat'],d['order'],d['policy'])==(r,o,p) and d['input_sha256']==info['sha256'] and c['ops']==min(cfg['limit'] or info['ops'],info['ops']) and d['elapsed_ns']>0,'case identity')
        if p=='O0':
            rec=load(root/(key+'_cpp.json'));cpp=root/(key+'_cpp.csv')
            ck(digest(cpp)==rec['sha256'],'cpp receipt')
            x=validate_row(cpp,rec['config'])
            ck(int(x['ops'])==c['ops'] and x['policy']=='cms' and x['counter_bytes']==524288 and x['saturations']==0,'cpp configuration')
            for a,b in [('hits','hits'),('reads','misses'),('admissions','main_inserts'),('rejects','rejects'),('evictions','main_evictions'),('resident','main_resident'),('unused_evictions','main_unused')]:ck(x[a]==c[b],'cpp mismatch '+a)
        rows.append(dict(repeat=r,order=o,policy=p,elapsed_ns=d['elapsed_ns'],**c))
    base={(d['repeat'],d['order']):d for d in rows if d['policy']=='O0'}
    for d in rows:
        b=base[d['repeat'],d['order']]
        d['hit_ratio']=d['hits']/d['ops']
        d['miss_reduction']=(b['misses']-d['misses'])/max(1,b['misses'])
        d['insert_ratio']=d['main_inserts']/max(1,b['main_inserts'])
        d['net_saved_misses']=b['misses']-d['misses']
        d['budget_utilization']=d['exceptions']/max(1,d['budget'])
    summary=[]
    for o in ('original','similarity'):
        for p in BPS:
            g=[d for d in rows if d['order']==o and d['policy']==p]
            summary.append(dict(order=o,policy=p,**{k:statistics.mean(d[k] for d in g) for k in g[0] if isinstance(g[0][k],(int,float)) and k!='repeat'},all_positive=all(d['miss_reduction']>0 for d in g),max_insert_ratio=max(d['insert_ratio'] for d in g)))
    gates=[]
    for p in list(BPS)[1:]:
        s=next(d for d in summary if d['order']=='similarity' and d['policy']==p);o=next(d for d in summary if d['order']=='original' and d['policy']==p)
        gates.append(dict(policy=p,similarity_gain=s['miss_reduction'],original_gain=o['miss_reduction'],all_positive=s['all_positive'],max_insert_ratio=max(s['max_insert_ratio'],o['max_insert_ratio']),passed=s['miss_reduction']>=.03 and s['all_positive'] and o['miss_reduction']>=-.01 and max(s['max_insert_ratio'],o['max_insert_ratio'])<=3))
    write(root/'metrics.csv',rows);write(root/'summary.csv',summary);write(root/'decision.csv',gates)
    atomic_json(root/'validation_summary.json',dict(status='PASS',runs=len(rows),cpp_checks=len(base),files={k:digest(root/k) for k in ('metrics.csv','summary.csv','decision.csv')}))
    print(f'PASS {len(rows)}/{len(cfg["cases"])}; C++ baseline checks {len(base)}')
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','validate']);p.add_argument('--source',type=Path);p.add_argument('--bench',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--repeats',type=int,choices=[1,3],default=3);p.add_argument('--limit',type=int,default=0);a=p.parse_args()
    ck(a.limit>=0,'limit')
    if a.action=='run':ck(a.source is not None and a.bench is not None,'source/bench');run(a)
    else:validate(a.out.resolve())
if __name__=='__main__':main()
