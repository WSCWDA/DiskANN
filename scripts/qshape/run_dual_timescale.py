"""48 independent trace/policy analyses; 16-case smoke uses a prefix."""
import argparse,csv,json,hashlib,time,statistics,random,fcntl
from pathlib import Path
import numpy as np
import grouping_characterization as a1
import run_residual_locality as a2
from dual_timescale import Replay,POLICIES,validate as check_row,slots
from validate_frequency_capacity import ck,read,write
from validate_residual_locality import ACCESS
def plan(n):
    return [(r,o,p) for r in range(1,n+1) for o in ('original','similarity') for p in POLICIES]
def extract(source,r,o,out,limit):
    p=a1.prefix(source,r,'D0' if o=='original' else 'D2')
    ck(json.loads((p.parent/'receipt.json').read_text())==a2.receipt(p),'source receipt')
    q=read(a1.files(p)[1]);meta=read(a2.files(p)[-1])
    expected={int(x['query_id']):int(x['reader_requests']) for x in q}
    mm={int(x['query_id']):x for x in meta}
    ck(len(expected)==len(q)==len(mm)==len(meta)==a1.N and expected.keys()==mm.keys(),'query IDs')
    ck(all(int(x['dropped'])==0 for x in meta),'dropped')
    n=sum(expected.values());a=np.empty(n,dtype=[('t','<u8'),('q','<u4'),('s','<u4'),('off','<u8')])
    counts={k:0 for k in expected};events=counts.copy();i=0
    with a2.files(p)[-2].open() as f:
        for e in csv.DictReader(f):
            k=int(e['query_id']);events[k]+=1
            if e['event_type'] not in ACCESS:continue
            off=int(e['offset']);ck(off>=0 and off%4096==0 and int(e['length'])==4096,'region')
            a[i]=(int(e['timestamp_ns']),k,int(e['sequence']),off);i+=1;counts[k]+=1
    ck(i==n and counts==expected and all(events[k]==int(mm[k]['events']) for k in events),'trace counts')
    a.sort(order=['q','off','s']);h=hashlib.sha256()
    import struct
    start=0
    for k in sorted(expected):
        count=expected[k];h.update(struct.pack('<QQ',k,count))
        for off in a['off'][start:start+count]:h.update(struct.pack('<QQ',int(off),4096))
        start+=count
    a.sort(order=['t','q','s']);path=out/f'{r}_{o}.npy'
    np.save(path,a['off'][:limit or n].copy(),allow_pickle=False)
    return dict(sha256=a1.digest(path),ops=min(limit,n) if limit else n,multiset=h.hexdigest(),source_receipt=a1.digest(p.parent/'receipt.json'))
def run(a):
    root=a.out.resolve();root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        source=a.source.resolve();v=json.loads((source/'validation_summary.json').read_text())
        ck(v['status']=='PASS' and v['runs']==18 and v['dropped']==0,'A2 validation')
        cfg=dict(source=str(source),source_manifest=a1.digest(source/'manifest.json'),source_validation=a1.digest(source/'validation_summary.json'),repeats=a.repeats,limit=a.limit,cases=[list(x) for x in plan(a.repeats)],code={p.name:a1.digest(p) for p in (Path(__file__),Path(__file__).with_name('dual_timescale.py'))})
        mf=root/'manifest.json'
        if mf.exists():ck(json.loads(mf.read_text())==cfg,'resume manifest')
        else:a1.atomic_json(mf,cfg)
        for r in range(1,a.repeats+1):
            for o in ('original','similarity'):
                path=root/f'{r}_{o}.npy';rec=path.with_suffix('.json')
                if rec.exists():info=json.loads(rec.read_text());ck(a1.digest(path)==info['sha256'],'stream hash')
                else:info=extract(source,r,o,root,a.limit);a1.atomic_json(rec,info)
                ck(info['multiset']==v['region_multiset_sha256'],'multiset')
                ids=np.load(path,allow_pickle=False);ck(len(ids)==info['ops'],'stream length')
                for p in POLICIES:
                    dest=root/f'{r}_{o}_{p}.json'
                    if dest.exists():continue
                    slots.cache_clear();model=Replay(p);t=time.perf_counter_ns()
                    for k in ids:model.access(int(k))
                    elapsed=time.perf_counter_ns()-t
                    d=model.result();check_row(d,p);d.update(repeat=r,order=o,policy=p,elapsed_ns=elapsed,input_sha256=info['sha256'])
                    a1.atomic_json(dest,d);print('PASS',r,o,p,flush=True)
        validate(root)
def validate(root):
    cfg=json.loads((root/'manifest.json').read_text());rows=[]
    ck(cfg['cases']==[list(x) for x in plan(cfg['repeats'])],'matrix')
    for r,o,p in plan(cfg['repeats']):
        path=root/f'{r}_{o}.npy';info=json.loads(path.with_suffix('.json').read_text())
        ck(a1.digest(path)==info['sha256'],'input hash')
        d=json.loads((root/f'{r}_{o}_{p}.json').read_text())
        ck((d['repeat'],d['order'],d['policy'])==(r,o,p) and d['input_sha256']==info['sha256'] and d['ops']==info['ops'] and d['elapsed_ns']>0,'result identity')
        check_row(d,p);d['hit_ratio']=d['hits']/d['ops'];d['ops_per_second']=d['ops']*1e9/d['elapsed_ns'];rows.append(d)
    base={(d['repeat'],d['order']):d for d in rows if d['policy']=='R1'}
    for d in rows:
        b=base[d['repeat'],d['order']];d['miss_reduction']=1-d['misses']/b['misses'] if b['misses'] else 0
    summary=[]
    for o in ('original','similarity'):
        for p in POLICIES:
            g=[d for d in rows if d['order']==o and d['policy']==p]
            summary.append(dict(order=o,policy=p,**{k:statistics.mean(d[k] for d in g) for k in g[0] if isinstance(g[0][k],(int,float)) and k!='repeat'},all_positive=all(d['miss_reduction']>0 for d in g)))
    write(root/'metrics.csv',rows);write(root/'summary.csv',summary)
    a1.atomic_json(root/'validation_summary.json',dict(status='PASS',runs=len(rows),files={k:a1.digest(root/k) for k in ('metrics.csv','summary.csv')}))
    print(f'PASS {len(rows)}/{len(cfg["cases"])}')
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','validate']);p.add_argument('--source',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--repeats',type=int,choices=[1,3],default=3);p.add_argument('--limit',type=int,default=0);a=p.parse_args()
    ck(a.limit>=0,'limit')
    if a.action=='run':ck(a.source is not None,'source');run(a)
    else:validate(a.out.resolve())
if __name__=='__main__':main()
