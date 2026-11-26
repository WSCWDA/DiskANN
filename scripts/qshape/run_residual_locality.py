"""A2.1: six trace configurations, reuse A1 command and checks."""
import argparse,json,os,random,shutil,subprocess,fcntl
from pathlib import Path
import grouping_characterization as a1
from validate_residual_locality import inspect_trace
from validate_frequency_capacity import ck,read,write
MAP=dict(zip(('D0','D1','D2','D3','D4','D5'),('Z4','Z5','Z7','Z0','Z1','Z3')))
def plan(n):
    out=[]
    for r in range(1,n+1):
        ids=list(MAP);random.Random(42+r).shuffle(ids);out.extend((r,i) for i in ids)
    return out
def command(c,p,i,order):
    args=a1.command(c,p,MAP[i],order)
    for k in ('region-trace','ready-stats','breakdown'):args[args.index('--qshape-'+k)+1]='1'
    return args
def files(p):
    return list(a1.files(p))+[Path(str(p)+'_L100_run0'+s) for s in ('_regions.csv','_region_meta.csv')]
def receipt(p):return {f.name:a1.digest(f) for f in files(p)}
def inspect(p,i,order):
    row,sig=a1.inspect(p,MAP[i],a1.N,order)
    trace=inspect_trace(p,read(a1.files(p)[1]),int(i[1])>=3)
    row.update(trace);row['case']=i
    return row,sig
def validate(root):
    c=json.loads((root/'manifest.json').read_text());order=root/'similarity_order.txt'
    ck(c['repeats'] in (1,3) and c['cases']==[list(x) for x in plan(c['repeats'])] and c['mapping']==MAP,'matrix')
    ck(a1.digest(order)==c['permutation_sha256'],'permutation hash')
    expected=a1.load_order(order,a1.N);ref=None;rows=[];random_hash=None
    for r,i in plan(c['repeats']):
        p=a1.prefix(root,r,i)
        ck(json.loads((p.parent/'receipt.json').read_text())==receipt(p),'receipt')
        ck(json.loads((p.parent/'command.json').read_text())==command(c,p,i,order),'command')
        row,sig=inspect(p,i,expected)
        key=(sig,row['region_multiset_sha256'])
        if ref is None:ref=key
        ck(key==ref,'cross-run query region multiset or search result mismatch')
        ck(list(sig[:3])==c['a1_result'],'A1 result mismatch')
        if i in ('D1','D4'):
            if random_hash is None:random_hash=row['order_sha256']
            ck(random_hash==row['order_sha256'],'random permutation')
        row['repeat']=r;rows.append(row);print('PASS',r,i,flush=True)
    write(root/'trace_metrics.csv',rows)
    a1.atomic_json(root/'validation_summary.json',dict(status='PASS',runs=len(rows),region_multiset_sha256=ref[1],a1_result=c['a1_result'],dropped=0))
    print(f'PASS {len(rows)}/{len(plan(c["repeats"]))}')
def run(a):
    root=a.out.resolve();root.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        c=a1.config(a);source=a.source.resolve();m=json.loads((source/'manifest.json').read_text())
        for k in ('query_sha256','gt_sha256','permutation_sha256','data_type'):ck(c[k]==m[k],'A1 provenance '+k)
        ck(c['inputs']['INDEX_PREFIX']==m['inputs']['INDEX_PREFIX'],'index prefix')
        p0=a1.prefix(source,1,'Z0')
        ck(json.loads((p0.parent/'receipt.json').read_text())==a1.receipt(p0),'A1 receipt')
        _,sig=a1.inspect(p0,'Z0',a1.N,a1.load_order(a.permutation,a1.N))
        c.update(mapping=MAP,cases=[list(x) for x in plan(a.repeats)],a1_result=list(sig[:3]),a1_manifest_sha256=a1.digest(source/'manifest.json'))
        manifest=root/'manifest.json';order=root/'similarity_order.txt'
        if manifest.exists():ck(json.loads(manifest.read_text())==c,'resume manifest')
        else:shutil.copyfile(a.permutation,order);a1.atomic_json(manifest,c)
        ck(a1.digest(order)==c['permutation_sha256'],'saved order')
        expected=a1.load_order(order,a1.N)
        for r,i in plan(a.repeats):
            p=a1.prefix(root,r,i);p.parent.mkdir(parents=True,exist_ok=True);rec=p.parent/'receipt.json'
            if rec.exists():
                ck(json.loads(rec.read_text())==receipt(p),'resume receipt');continue
            for f in files(p):
                if f.exists():f.unlink()
            args=command(c,p,i,order);a1.atomic_json(p.parent/'command.json',args)
            with files(p)[0].open('w') as log:subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=1800,check=True)
            row,sig=inspect(p,i,expected);ck(list(sig[:3])==c['a1_result'],'A1 results')
            a1.atomic_json(rec,receipt(p));print('COLLECTED',r,i,flush=True)
        validate(root)
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','validate']);p.add_argument('--out',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--permutation',type=Path);p.add_argument('--repeats',type=int,choices=[1,3],default=3);a=p.parse_args()
    if a.action=='run':
        ck(a.source is not None and a.permutation is not None,'source and permutation required');run(a)
    else:validate(a.out.resolve())
if __name__=='__main__':main()
