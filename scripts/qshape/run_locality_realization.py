"""One CSV scan per run; packed event arrays sorted by region."""
import argparse,csv,json
from pathlib import Path
import numpy as np
import grouping_characterization as a1
from run_residual_locality import receipt
from run_runtime_attribution import inputs
from residual_locality import rank_regions
from validate_frequency_capacity import read,write
from locality_realization import *
DT=np.dtype([('rid','i4'),('t','i8'),('q','i4'),('s','i8'),('o','i4'),('l','i8'),('k','u1')])
TIME=set(METRICS)-{'rank_distance','hits_per_admission','unused_eviction','readmission','resident_access','timestamp_tie'}
def rows_for(a,mask,tag,metrics):
    for k in metrics:
        d=combine(a[:,METRICS.index(k),:],mask)
        if k not in TIME:
            for x in LIMITS:d['le_'+str(x)]=''
        yield dict(**tag,metric=k,**d)
def scan(p,off,groups,ranks,expected,active):
    lookup={int(x):i for i,x in enumerate(off)};events=np.empty(expected,dtype=DT);n=0
    with Path(str(p)+'_L100_run0_regions.csv').open() as f:
        for e in csv.DictReader(f):
            require(n<expected,'extra events')
            q=int(e['query_id']);require(groups[q]==int(e['group_id']) and int(e['length'])==4096,'identity')
            events[n]=(lookup[int(e['offset'])],int(e['timestamp_ns']),q,int(e['sequence']),int(e['owner_query']),int(e['lifecycle']),KINDS.index(e['event_type']));n+=1
    require(n==expected,'event count')
    end=int(events['t'].max());events.sort(order='rid')
    bounds=np.searchsorted(events['rid'],np.arange(len(off)+1))
    a=np.zeros((len(off),len(METRICS),2+len(LIMITS)),dtype=np.int64)
    for i in range(len(off)):
        es=[(int(t),int(q),int(s),int(o),int(l),KINDS[k]) for _,t,q,s,o,l,k in events[bounds[i]:bounds[i+1]]]
        for k,v in region(es,groups,ranks,end,active).items():a[i,METRICS.index(k)]=stats(v)
    return a
def compute(source,static,runtime,out):
    off,f,ds,metrics=inputs(source,static);u=len(off)
    v=json.loads((runtime/'validation_summary.json').read_text());m=json.loads((runtime/'manifest.json').read_text())
    require(v['status']=='PASS' and v['runs']==18 and v['pairs']==12,'runtime validation')
    require(m['source_manifest_sha256']==a1.digest(source/'manifest.json') and m['static_validation_sha256']==a1.digest(static/'validation_summary.json'),'provenance')
    for name,h in v['files'].items():require(a1.digest(runtime/name)==h,'runtime hash '+name)
    rank=rank_regions(f);pos=np.empty(u,dtype=int);pos[rank]=np.arange(u)
    edges=[0,int(u*.001),int(u*.01),4096,int(u*.1),u]
    aa=[];bb=[];cc=[];matrix=[]
    with np.load(runtime/'runtime_regions.npz',allow_pickle=False) as rr:
        require(np.array_equal(rr['offset'],off),'region keys')
        for r in range(1,4):
            arrays={}
            for i in range(6):
                c='D'+str(i);p=a1.prefix(source,r,c)
                require(json.loads((p.parent/'receipt.json').read_text())==receipt(p),'receipt')
                q=read(a1.files(p)[1]);groups={int(x['query_id']):int(x['group_id']) for x in q};ranks={int(x['query_id']):int(x['execution_id']) for x in q}
                z=metrics[r,c];a=scan(p,off,groups,ranks,int(z['events']),i>=3);arrays[c]=a
                old=rr[f'{r}_{c}'];idx=lambda k:METRICS.index(k)
                for k,col in [('join_age',3),('join_remaining',3),('hits_per_admission',7)]:
                    require(np.array_equal(a[:,idx(k),0],old[:,col]),'count '+k)
                require(np.array_equal(a[:,idx('residence_evicted'),0],old[:,9]+old[:,10]),'evictions')
                require(np.array_equal(a[:,idx('hits_per_admission'),1],old[:,2]),'ready hits')
                require(int(a[:,idx('unused_eviction'),1].sum())==sum(int(x['ready_unused_evictions']) for x in q),'unused evictions')
                tag=dict(repeat=r,case=c,outlier=int((r,c) in ((2,'D0'),(3,'D3'))))
                for lo,hi in zip(edges,edges[1:]):
                    mask=(pos>=lo)&(pos<hi);t=dict(**tag,rank_start=lo,rank_end=hi)
                    aa.extend(rows_for(a,mask,t,METRICS[:6]+('post_publish_gap','timestamp_tie')))
                    if i>=3:bb.extend(rows_for(a,mask,t,METRICS[7:15]))
                matrix.append(dict(stage='A',repeat=r,case=c,base='',status='PASS'))
                if i>=3:matrix.append(dict(stage='B',repeat=r,case=c,base='',status='PASS'))
                print('PASS scan',r,c,flush=True)
            for start in (0,3):
                for j in (1,2):
                    b='D'+str(start);c='D'+str(start+j)
                    with np.load(runtime/f'{r}_{b}_{c}.npz',allow_pickle=False) as p:
                        require(np.array_equal(p['offset'],off),'pair keys');quad=p['quadrant']
                        for lo,hi in zip(edges,edges[1:]):
                            for k in range(1,5):
                                mask=(pos>=lo)&(pos<hi)&(quad==k)
                                for side in (b,c):
                                    tag=dict(repeat=r,base=b,case=c,side=side,quadrant=k,rank_start=lo,rank_end=hi,regions=int(mask.sum()),static_gain=int(p['residual_gain'][mask].sum()),read_gain=int(p['read_gain'][mask].sum()),outlier=int((r,b) in ((2,'D0'),(3,'D3')) or (r,c) in ((2,'D0'),(3,'D3'))))
                                    cc.extend(rows_for(arrays[side],mask,tag,METRICS if start else METRICS[:7]+('timestamp_tie',)))
                    matrix.append(dict(stage='C',repeat=r,case=c,base=b,status='PASS'))
    for name,data in [('temporal',aa),('retention',bb),('joint',cc),('matrix',matrix)]:write(out/(name+'.csv'),data)
    # Pooled event-weighted means/CDF counts, never mean of per-run ratios.
    for name,data in [('temporal',aa),('retention',bb),('joint',cc)]:
        result=[]
        for clean in (0,1):
            bins={}
            for x in data:
                if clean and x['outlier']:continue
                key=tuple((k,v) for k,v in x.items() if k not in ('repeat','outlier','samples','total','mean','regions','static_gain','read_gain') and not k.startswith('le_'))
                z=bins.setdefault(key,[0,0]+[0]*len(LIMITS));z[0]+=x['samples'];z[1]+=x['total']
                for i,t in enumerate(LIMITS):z[i+2]+=int(x['le_'+str(t)] or 0)
            for key,z in bins.items():
                d=dict(key);result.append(dict(**d,exclude_outliers=clean,samples=z[0],total=z[1],mean=z[1]/z[0] if z[0] else '',**{'le_'+str(t):z[i+2] if d['metric'] in TIME else '' for i,t in enumerate(LIMITS)}))
        write(out/(name+'_sensitivity.csv'),result)
    a1.atomic_json(out/'manifest.json',dict(source=str(source),static=str(static),runtime=str(runtime),runtime_validation_sha256=a1.digest(runtime/'validation_summary.json'),metrics=list(METRICS),thresholds_ns=list(LIMITS)))
def main():
    p=argparse.ArgumentParser()
    for k in ('source','static','runtime','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);compute(a.source.resolve(),a.static.resolve(),a.runtime.resolve(),a.out.resolve())
    from validate_locality_realization import validate
    validate(a.out)
if __name__=='__main__':main()
