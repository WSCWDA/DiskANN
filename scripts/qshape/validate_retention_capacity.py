"""Strict B1 matrix and per-run validation."""
import argparse,csv,json,hashlib,random
from pathlib import Path

FIELDS="policy n ops skew seed ready_budget meta_budget mode".split()
COUNTS="observed fingerprint checksum elapsed_ns hits reads admissions rejects evictions unused_evictions resident ready_peak inflight_peak live_peak frequency_updates frequency_failures counter_bytes saturations gate_checks gate_accepts gate_rejects acquire_ns fill_ns publish_ns consume_ns tracking_ns".split()
def check(ok,msg):
    if not ok: raise ValueError(msg)
def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()
def matrix(profile,repeats):
    check(profile in ('smoke','pilot','formal','skew-smoke','skew') and repeats>0,'profile/repeats')
    ns,ops={'smoke':([10000],20000),'pilot':([100000,1000000,10000000],1000000),'formal':([100000,1000000,10000000],10000000),'skew-smoke':([10000],20000),'skew':([1000000],10000000)}[profile]
    cases=[]
    for seed in range(42,42+repeats):
        batch=[]
        for n in ns:
            for skew in ((0.8,1.2) if profile.startswith('skew') else (0,1)):
                for p,m in [(p,0) for p in (('lru','exact') if profile.startswith('skew') else ('none','bounded-local','lru','exact'))]+[('cms',k*1024) for k in (64,256,512,1024,2048)]:
                    batch.append(dict(zip(FIELDS,map(str,(p,n,ops,skew,seed,16777216,m,'perf')))))
        random.Random(seed).shuffle(batch)
        cases.extend(batch)
    return [dict(file=f'{i:04d}.csv',**c) for i,c in enumerate(cases)]
def read_csv(p):
    with open(p,newline='') as f:
        reader=csv.DictReader(f)
        check(reader.fieldnames is not None and len(set(reader.fieldnames))==len(reader.fieldnames),'CSV header')
        return list(reader)
def validate_row(path,c):
    rows=read_csv(path);check(len(rows)==1,'row count')
    x=rows[0];check(set(x)==set(FIELDS+COUNTS) and all(v is not None for v in x.values()),'schema')
    for k in FIELDS:
        check((float(x[k])==float(c[k]) if k=='skew' else x[k]==c[k]),'parameter '+k)
    v={k:int(x[k]) for k in COUNTS}
    check(all(a>=0 for a in v.values()),'negative counter')
    n=int(c['ops']);p=c['policy'];h=v['hits'];r=v['reads'];a=v['admissions'];ev=v['evictions']
    check(n==h+r and 0<v['observed']<=min(n,int(c['n'])),'requests/cardinality')
    check(a==ev+v['resident'] and v['unused_evictions']<=ev,'residency')
    check(v['resident']*4096<=v['ready_peak']<=int(c['ready_budget']),'READY budget')
    check(v['inflight_peak']<=4096 and v['live_peak']<=int(c['ready_budget'])+4096,'single-thread payload')
    check(v['live_peak']>=max(v['ready_peak'],v['inflight_peak']),'live peak')
    check(a+v['rejects']==(0 if p=='none' else r),'publication')
    if p=='none':check(h==a==ev==v['resident']==0,'none')
    if p=='lru':check(a==r and v['rejects']==0,'LRU')
    if p=='bounded-local':check(ev==0,'first-fill')
    check(v['frequency_updates']==(n if p in ('exact','cms') else 0) and v['frequency_failures']==0,'frequency')
    check(v['counter_bytes']==(int(c['meta_budget']) if p=='cms' else 0),'counter budget')
    check(v['gate_checks']==v['gate_accepts']+v['gate_rejects'],'gate')
    check(v['elapsed_ns']>0,'elapsed')
    return dict(c,**v)
def validate_saved(out,c):
    p=out/c['file']; receipt=json.loads(p.with_suffix('.json').read_text())
    check(receipt=={'case':c,'sha256':digest(p)},'receipt mismatch')
    return validate_row(p,c)
def validate(out):
    config=json.loads((out/'config.json').read_text())
    cases=matrix(config['profile'],config['repeats'])
    check(read_csv(out/'manifest.csv')==cases,'matrix mismatch')
    check((out/'complete').read_text().strip()==str(len(cases)),'incomplete')
    rows=[];inputs={}
    for c in cases:
        x=validate_saved(out,c)
        key=tuple(c[k] for k in ('n','ops','skew','seed'))
        sig=tuple(x[k] for k in ('observed','fingerprint','checksum'))
        check(inputs.setdefault(key,sig)==sig,'input/data mismatch '+str(key))
        rows.append(x)
    return rows
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rows=validate(a.out)
    print(f'PASS {len(rows)}/{len(rows)}; saturated runs={sum(x["saturations"]>0 for x in rows)}')
