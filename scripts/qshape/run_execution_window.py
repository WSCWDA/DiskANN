"""B1.1: prepare five fixed permutations, then 10 smoke / 30 formal runs."""
import argparse,csv,fcntl,json,os,random,shutil,statistics,subprocess,time
from pathlib import Path
import numpy as np
import grouping_characterization as a1
import run_residual_locality as a2
from validate_frequency_capacity import ck,read,write
from validate_residual_locality import ACCESS
from execution_window import *
N=a1.N
NAMES=('original','similarity','within_random','within_vector','within_oracle')
CASES={f'B{i}':(name,ret) for i,(ret,name) in enumerate((r,n) for r in ('none','cms') for n in NAMES)}
def plan(n):
    out=[]
    for r in range(1,n+1):
        ids=list(CASES);random.Random(42+r).shuffle(ids);out.extend((r,i) for i in ids)
    return out
def prepare(source,out,query):
    m=json.loads((source/'manifest.json').read_text());v=json.loads((source/'validation_summary.json').read_text())
    ck(v['status']=='PASS' and v['runs']==18 and v['dropped']==0,'A2 validation')
    ck(a1.digest(query)==m['query_sha256'],'query hash')
    base=a1.load_order(source/'similarity_order.txt',N)
    ck(a1.digest(source/'similarity_order.txt')==m['permutation_sha256'],'base hash')
    p=a1.prefix(source,1,'D0')
    ck(json.loads((p.parent/'receipt.json').read_text())==a2.receipt(p),'trace receipt')
    sets=[set() for _ in range(N)];counts=[0]*N
    with a2.files(p)[-2].open() as f:
        for e in csv.DictReader(f):
            if e['event_type'] in ACCESS:
                q=int(e['query_id']);off=int(e['offset']);ck(0<=q<N and off%4096==0 and int(e['length'])==4096,'region')
                sets[q].add(off);counts[q]+=1
    for x in read(a1.files(p)[1]):ck(counts[int(x['query_id'])]==int(x['reader_requests']),'trace count')
    with query.open('rb') as f:
        n,d=np.fromfile(f,dtype='<i4',count=2);ck(n==N and d>0,'fbin header')
        x=np.fromfile(f,dtype='<f4');ck(x.size==n*d and np.isfinite(x).all(),'fbin data');x=x.reshape(n,d)
    out.mkdir(parents=True,exist_ok=False);rows=[];hashes={}
    builders=(lambda:list(range(N)),lambda:base,lambda:random_order(base),lambda:reorder(base,lambda g:vector_score(x,g)),lambda:reorder(base,lambda g:oracle_score(sets,g)))
    for name,build in zip(NAMES,builders):
        t=time.perf_counter_ns();order=build();elapsed=time.perf_counter_ns()-t
        if name!='original':check_membership(base,order)
        f=out/(name+'.txt');f.write_text(a1.order_text(order));hashes[name]=a1.digest(f)
        rows.append(dict(policy=name,ordering_ns=elapsed,window_overlap=window_overlap(order,sets)))
    write(out/'ordering_metrics.csv',rows)
    a1.atomic_json(out/'manifest.json',dict(hashes=hashes,query_sha256=m['query_sha256'],gt_sha256=m['gt_sha256'],index_prefix=m['inputs']['INDEX_PREFIX'],source_manifest_sha256=a1.digest(source/'manifest.json'),source_result=v['a1_result'],base_sha256=m['permutation_sha256'],metrics_sha256=a1.digest(out/'ordering_metrics.csv')))
def command(c,p,i,root):
    name,ret=CASES[i];return a1.command(c,p,'Z3' if ret=='cms' else 'Z7',root/'orders'/(name+'.txt'))
def inspect(p,i,root):
    name,ret=CASES[i];row,sig=a1.inspect(p,'Z3' if ret=='cms' else 'Z7',N,a1.load_order(root/'orders'/(name+'.txt'),N))
    row.update(case=i,policy=name,retention=ret);return row,sig
def validate(root):
    c=json.loads((root/'manifest.json').read_text());o=root/'orders';m=c['orders'];cases=plan(c['repeats'])
    ck(c['cases']==[list(x) for x in cases] and c['policies']=={k:list(v) for k,v in CASES.items()},'matrix')
    ck(a1.digest(o/'ordering_metrics.csv')==m['metrics_sha256'],'ordering metrics')
    base=a1.load_order(o/'similarity.txt',N)
    for name in NAMES:
        f=o/(name+'.txt');ck(a1.digest(f)==m['hashes'][name],'order hash')
        order=a1.load_order(f,N)
        if name!='original':check_membership(base,order)
        else:ck(order==list(range(N)),'original')
    rows=[];ref=None
    for r,i in cases:
        p=a1.prefix(root,r,i);ck(json.loads((p.parent/'receipt.json').read_text())==a1.receipt(p),'receipt')
        ck(json.loads((p.parent/'command.json').read_text())==command(c,p,i,root),'command')
        row,sig=inspect(p,i,root);ck(list(sig[:3])==m['source_result'],'A2 result')
        if ref is None:ref=sig
        ck(sig==ref,'logical signature');row['repeat']=r;rows.append(row)
    write(root/'metrics.csv',rows);summary=[];paired=[]
    for i in CASES:
        z=[x for x in rows if x['case']==i];d=dict(case=i,policy=z[0]['policy'],retention=z[0]['retention'])
        d.update({k:statistics.mean(x[k] for x in z) for k,v in z[0].items() if k!='repeat' and isinstance(v,(int,float))})
        d['qps_cv']=statistics.stdev(x['search_qps'] for x in z)/d['search_qps'] if len(z)>1 else 0;summary.append(d)
    for r in range(1,c['repeats']+1):
        for ret in ('none','cms'):
            z={x['policy']:x for x in rows if x['repeat']==r and x['retention']==ret};b=z['similarity']
            for name,x in z.items():
                paired.append(dict(repeat=r,retention=ret,policy=name,search_gain=x['search_qps']/b['search_qps']-1,e2e_gain=x['e2e_qps']/b['e2e_qps']-1,read_reduction=1-x['submitted_reads']/b['submitted_reads'],p99_change=x['p99_us']/b['p99_us']-1))
    write(root/'summary.csv',summary);write(root/'paired.csv',paired)
    a1.atomic_json(root/'validation_summary.json',dict(status='PASS',runs=len(rows),files={n:a1.digest(root/n) for n in ('metrics.csv','summary.csv','paired.csv')}));print(f'PASS {len(rows)}/{len(cases)}')
def run(a):
    root=a.out.resolve();root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        o=a.orders.resolve();m=json.loads((o/'manifest.json').read_text())
        e={k:str(Path(os.environ[k]).resolve()) for k in ('SEARCH_BIN','INDEX_PREFIX','QUERY_FILE','GT_FILE')}
        ck(os.environ.get('DATA_TYPE','float')=='float','dtype')
        ck(a1.digest(e['QUERY_FILE'])==m['query_sha256'] and a1.digest(e['GT_FILE'])==m['gt_sha256'] and e['INDEX_PREFIX']==m['index_prefix'],'inputs')
        ck(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip(),'tracked changes')
        c=dict(inputs=e,data_type='float',binary_sha256=a1.digest(e['SEARCH_BIN']),commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),orders=m,repeats=a.repeats,cases=[list(x) for x in plan(a.repeats)],policies={k:list(v) for k,v in CASES.items()})
        mf=root/'manifest.json'
        if mf.exists():ck(json.loads(mf.read_text())==c,'resume manifest')
        else:shutil.copytree(o,root/'orders');a1.atomic_json(mf,c)
        for name in NAMES:ck(a1.digest(root/'orders'/(name+'.txt'))==m['hashes'][name],'order hash')
        for r,i in plan(a.repeats):
            p=a1.prefix(root,r,i);p.parent.mkdir(parents=True,exist_ok=True);rec=p.parent/'receipt.json'
            if rec.exists():ck(json.loads(rec.read_text())==a1.receipt(p),'resume receipt');continue
            for f in a1.files(p):
                if f.exists():f.unlink()
            args=command(c,p,i,root);a1.atomic_json(p.parent/'command.json',args)
            with a1.files(p)[0].open('w') as log:subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=900,check=True)
            _,sig=inspect(p,i,root);ck(list(sig[:3])==m['source_result'],'A2 result');a1.atomic_json(rec,a1.receipt(p));print('PASS',r,i,flush=True)
        validate(root)
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','validate']);p.add_argument('--out',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--query',type=Path);p.add_argument('--orders',type=Path);p.add_argument('--repeats',type=int,choices=[1,3],default=3);a=p.parse_args()
    if a.action=='prepare':prepare(a.source.resolve(),a.out.resolve(),a.query.resolve())
    elif a.action=='run':run(a)
    else:validate(a.out.resolve())
if __name__=='__main__':main()
