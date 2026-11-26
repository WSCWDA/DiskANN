"""Replay complete logical region streams through production retention."""
import argparse,csv,json,random,subprocess,collections,statistics
from pathlib import Path
from validate_retention_capacity import check,digest,read_csv,validate_row
ACCESS={'OWNER','BYPASS','READY_HIT','INFLIGHT_JOIN'}
def extract(stem):
    q=read_csv(Path(str(stem)+'_queries.csv'))
    meta=read_csv(Path(str(stem)+'_region_meta.csv'))
    expected={int(x['query_id']):int(x['reader_requests']) for x in q}
    m={int(x['query_id']):x for x in meta}
    check(len(expected)==len(q)==len(m)==len(meta) and expected.keys()==m.keys(),'query IDs')
    check(all(int(x['dropped'])==0 for x in meta),'truncated trace')
    events=collections.Counter(); counts=collections.Counter(); hist=collections.Counter(); stream=[]
    with open(str(stem)+'_regions.csv') as f:
        for e in csv.DictReader(f):
            qid=int(e['query_id']);events[qid]+=1
            if e['event_type'] not in ACCESS:continue
            off=int(e['offset']);length=int(e['length'])
            check(off>=0 and off%4096==0 and length==4096,'only aligned 4KiB regions supported')
            counts[qid]+=1;hist[qid,off//4096]+=1
            stream.append((int(e['timestamp_ns']),qid,int(e['sequence']),off//4096))
    check(set(events)<=set(expected),'unknown query')
    for k in expected:
        check(events[k]==int(m[k]['events']) and counts[k]==expected[k],'per-query completeness')
    check(bool(stream),'empty trace')
    stream.sort()
    check(len({(x[1],x[2]) for x in stream})==len(stream),'duplicate access sequence')
    return [x[3] for x in stream],hist
def fingerprint(ids):
    h=1469598103934665603
    for x in ids:h=((h^x)*1099511628211)&((1<<64)-1)
    return h
def prepare(a):
    a.out.mkdir(parents=True,exist_ok=False)
    hist=None;manifest={}
    for order,stem in [('original',a.original),('similarity',a.similarity)]:
        ids,h=extract(stem)
        if hist is None:hist=h
        check(hist==h,'per-query region multiset mismatch')
        if a.limit:ids=ids[:a.limit]
        p=a.out/(order+'.ids')
        with p.open('w') as f:f.writelines(str(x)+'\n' for x in ids)
        manifest[order]=dict(ops=len(ids),n=max(ids)+1,observed=len(set(ids)),fingerprint=fingerprint(ids),sha256=digest(p),sources={suffix:digest(Path(str(stem)+suffix)) for suffix in ('_queries.csv','_region_meta.csv','_regions.csv')})
    (a.out/'inputs.json').write_text(json.dumps(manifest,indent=2))
def cases(repeats,mode):
    for r in range(1,repeats+1):
        batch=[(o,p) for o in ('original','similarity') for p in ('lru','exact','cms')]
        random.Random(42+r).shuffle(batch)
        for o,p in batch:yield r,o,p,mode
def case_params(info,p,mode):
    return dict(policy=p,n=str(info['n']),ops=str(info['ops']),skew='0',seed='42',ready_budget='16777216',meta_budget=str(524288 if p=='cms' else 0),mode=mode)
def run(a):
    info=json.loads((a.out/'inputs.json').read_text())
    cfg=dict(repeats=a.repeats,mode=a.mode,binary_sha256=digest(a.bench),commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    config=a.out/'run.json'
    check(not config.exists(),'run already exists; use new directory')
    config.write_text(json.dumps(cfg))
    for r,o,p,mode in cases(a.repeats,a.mode):
        path=a.out/(o+'.ids');check(digest(path)==info[o]['sha256'],'input hash')
        c=case_params(info[o],p,mode)
        dest=a.out/f'{r}_{o}_{p}.csv'
        tmp=dest.with_suffix('.partial')
        with tmp.open('w') as f:subprocess.run([str(a.bench.resolve()),*[c[k] for k in ('policy','n','ops','skew','seed','ready_budget','meta_budget','mode')],str(path)],stdout=f,check=True,timeout=900)
        validate_row(tmp,c);tmp.replace(dest)
        dest.with_suffix('.sha256').write_text(digest(dest))
    validate(a.out)
def validate(out):
    info=json.loads((out/'inputs.json').read_text());cfg=json.loads((out/'run.json').read_text())
    rows=[];sig={};stable={}
    for o in info:check(digest(out/(o+'.ids'))==info[o]['sha256'],'input hash')
    for r,o,p,mode in cases(cfg['repeats'],cfg['mode']):
        dest=out/f'{r}_{o}_{p}.csv'
        check(digest(dest)==dest.with_suffix('.sha256').read_text(),'result hash')
        x=validate_row(dest,case_params(info[o],p,mode))
        check(x['fingerprint']==info[o]['fingerprint'] and x['observed']==info[o]['observed'] and x['saturations']==0,'trace identity/saturation')
        check(sig.setdefault(o,x['checksum'])==x['checksum'],'data checksum')
        v=tuple(x[k] for k in ('hits','reads','admissions','evictions'))
        check(stable.setdefault((o,p),v)==v,'non-deterministic replay')
        x.update(order=o,repeat=r,hit_ratio=x['hits']/int(x['ops']),ops_per_second=int(x['ops'])*1e9/x['elapsed_ns']);rows.append(x)
    def write(name,data):
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    write('trace_metrics.csv',rows)
    summary=[]
    for o in ('original','similarity'):
        for p in ('lru','exact','cms'):
            g=[x for x in rows if x['order']==o and x['policy']==p]
            summary.append(dict(order=o,policy=p,**{k:statistics.mean(x[k] for x in g) for k in ('hit_ratio','reads','admissions','ops_per_second')}))
    write('trace_summary.csv',summary)
    h={(x['order'],x['policy']):x['hit_ratio'] for x in summary}
    interaction=(h['similarity','cms']-h['original','cms'])-(h['similarity','lru']-h['original','lru'])
    (out/'interaction.json').write_text(json.dumps(dict(interaction_pp=100*interaction,grouping_cms_pp=100*(h['similarity','cms']-h['original','cms']),grouping_lru_pp=100*(h['similarity','lru']-h['original','lru'])),indent=2))
    print(f'PASS {len(rows)}/{len(rows)}')
def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
    x=s.add_parser('prepare');x.add_argument('--original',type=Path,required=True);x.add_argument('--similarity',type=Path,required=True);x.add_argument('--limit',type=int,default=0)
    x=s.add_parser('run');x.add_argument('--bench',type=Path,required=True);x.add_argument('--repeats',type=int,choices=[1,3],default=3);x.add_argument('--mode',choices=['perf','correctness'],default='perf')
    s.add_parser('validate')
    for x in s.choices.values():x.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.cmd=='prepare':prepare(a)
    elif a.cmd=='run':run(a)
    else:validate(a.out)
if __name__=='__main__':main()
