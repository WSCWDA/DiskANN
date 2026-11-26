"""D1/D2: stream 18 validated traces, compare paired runs, no search execution."""
import argparse,csv,json
from pathlib import Path
import numpy as np
import grouping_characterization as a1
from run_residual_locality import receipt,MAP
from validate_frequency_capacity import ck,read,write
from runtime_attribution import aggregate,compare,summarize,FIELDS
from residual_locality import rank_regions
def inputs(source,static):
    v=json.loads((source/'validation_summary.json').read_text());m=json.loads((source/'manifest.json').read_text())
    s=json.loads((static/'validation_summary.json').read_text())
    ck(v['status']==s['status']=='PASS' and v['runs']==18 and s['configs']==21 and v['region_multiset_sha256']==s['region_multiset_sha256'] and m['mapping']==MAP,'source provenance')
    for name,h in s['files'].items():ck(a1.digest(static/name)==h,'static hash '+name)
    em=json.loads((static/'extraction_manifest.json').read_text())
    ck(em['source_manifest_sha256']==a1.digest(source/'manifest.json') and em['source_validation_sha256']==a1.digest(source/'validation_summary.json'),'source linkage')
    rows=sorted(read(static/'region_frequency.csv'),key=lambda x:int(x['region_id']))
    ck(len(rows)==165446 and [int(x['region_id']) for x in rows]==list(range(len(rows))),'region IDs')
    off=np.array([int(x['offset']) for x in rows]);f=np.array([int(x['frequency']) for x in rows])
    ds={k:np.array([int(x[k]) for x in rows]) for k in ('original','random','similarity')}
    ck(np.all(off[1:]>off[:-1]) and np.all(f>0),'region keys')
    metrics={(int(x['repeat']),x['case']):x for x in read(source/'trace_metrics.csv')}
    ck(set(metrics)=={(r,'D'+str(i)) for r in range(1,4) for i in range(6)},'matrix')
    ck(all(x['region_multiset_sha256']==v['region_multiset_sha256'] and int(x['dropped'])==0 for x in metrics.values()),'trace validation')
    return off,f,ds,metrics
def compute(source,static,out):
    off,f,ds,metrics=inputs(source,static);u=len(off);rank=rank_regions(f)
    rankpos=np.empty(u,dtype=np.int64);rankpos[rank]=np.arange(u)
    edges=[0,int(u*.001),int(u*.01),4096,int(u*.1),u]
    runs=[];bands=[];pairs=[];quads=[];regionpairs=[];arrays={}
    for r in range(1,4):
        for i in range(6):
            case='D'+str(i);p=a1.prefix(source,r,case)
            ck(json.loads((p.parent/'receipt.json').read_text())==receipt(p),'receipt')
            q=read(a1.files(p)[1]);groups={int(x['query_id']):int(x['group_id']) for x in q}
            order=a1.permutation(q,10000);name=('original','random','similarity')[i%3]
            ck(order==a1.load_order(static/(name+'_order.txt'),10000),'order')
            with Path(str(p)+'_L100_run0_regions.csv').open() as stream:a,c=aggregate(csv.DictReader(stream),off,groups)
            z=metrics[r,case]
            ck(sum(c.values())==int(z['events']),'event total')
            for k,n in c.items():ck(n==int(z[k.lower()]),'event count '+k)
            ck(int(a[:,0].sum())==3265956 and np.all(a[:,0]>=f),'logical total')
            ck(int(a[:,4:6].sum()+a[:,6].sum())==int(z['inflight_join']),'join total')
            ck(int(a[:,4].sum()+a[:,6].sum())==int(z['same_group_joins']),'same group total')
            if i<3:ck(not a[:,2].any() and not a[:,7:].any(),'retention off')
            arrays[r,case]=a
            def totals(mask):return {k:int(v) for k,v in zip(FIELDS,a[mask].sum(axis=0))}
            runs.append(dict(repeat=r,case=case,**totals(np.ones(u,dtype=bool))))
            for lo,hi in zip(edges,edges[1:]):
                mask=(rankpos>=lo)&(rankpos<hi)
                bands.append(dict(repeat=r,case=case,rank_start=lo,rank_end=hi,**totals(mask)))
            print('PASS',r,case,flush=True)
        for start in (0,3):
            for j in (1,2):
                base='D'+str(start);other='D'+str(start+j);name=('random','similarity')[j-1]
                raw=ds[name]-ds['original'];res=raw.copy()
                if start:res[rank[:4096]]=0
                gain,ready,joins,quad=compare(arrays[r,base],arrays[r,other],res)
                tag=dict(repeat=r,base=base,other=other,budget_mib=16 if start else 0)
                pairs.append(dict(**tag,raw_gain=int(raw.sum()),**summarize(np.ones(u,dtype=bool),res,gain,ready,joins)))
                for lo,hi in zip(edges,edges[1:]):
                    for k in range(1,5):
                        mask=(rankpos>=lo)&(rankpos<hi)&(quad==k)
                        quads.append(dict(**tag,rank_start=lo,rank_end=hi,quadrant=k,**summarize(mask,res,gain,ready,joins)))
                for k in range(1,5):
                    mask=quad==k
                    regionpairs.append(dict(**tag,quadrant=k,**summarize(mask,res,gain,ready,joins)))
                np.savez_compressed(out/f'{r}_{base}_{other}.npz',offset=off,frequency=f,raw_gain=raw,residual_gain=res,read_gain=gain,ready_delta=ready,join_delta=joins,quadrant=quad)
    np.savez_compressed(out/'runtime_regions.npz',offset=off,frequency=f,**{f'{r}_{c}':a for (r,c),a in arrays.items()})
    for name,rows in [('runs',runs),('runtime_bands',bands),('paired',pairs),('quadrant_bands',quads),('quadrants',regionpairs)]:write(out/(name+'.csv'),rows)
    a1.atomic_json(out/'manifest.json',dict(source=str(source),static=str(static),source_manifest_sha256=a1.digest(source/'manifest.json'),source_validation_sha256=a1.digest(source/'validation_summary.json'),static_validation_sha256=a1.digest(static/'validation_summary.json'),fields=list(FIELDS)))
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--static',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);compute(a.source.resolve(),a.static.resolve(),a.out.resolve())
    from validate_runtime_attribution import validate
    validate(a.out)
if __name__=='__main__':main()
