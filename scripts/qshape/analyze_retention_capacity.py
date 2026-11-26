import argparse,csv,statistics
from pathlib import Path
from validate_retention_capacity import validate

def ratio(a,b):return a/b if b>0 else None
def derive(rows):
    refs={(x['n'],x['ops'],x['skew'],x['seed'],x['policy'],x['meta_budget']):x for x in rows}
    result=[]
    for x in rows:
        k=tuple(x[a] for a in ('n','ops','skew','seed'))
        exact=refs[k+('exact','0')];lru=refs[k+('lru','0')]
        n=int(x['ops']);h=x['hits'];m=x['counter_bytes'];speed=n*1e9/x['elapsed_ns']
        result.append(dict(x,hit_ratio=h/n,ops_per_second=speed,
            utility_preservation=ratio(h,exact['hits']),
            incremental_preservation=ratio(h-lru['hits'],exact['hits']-lru['hits']),
            absolute_utility_loss=(exact['hits']-h)/n,
            admission_reduction=None if not lru['admissions'] else 1-x['admissions']/lru['admissions'],
            admission_productivity=ratio(h,x['admissions']),
            processing_efficiency=speed/(n*1e9/exact['elapsed_ns']),
            metadata_pressure=ratio(x['observed']*16,m),update_pressure=ratio(n*16,m)))
    return result
def write(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    rows=derive(validate(a.out));write(a.out/'capacity_metrics.csv',rows)
    groups={}
    keys=('n','ops','skew','policy','meta_budget')
    for x in rows:groups.setdefault(tuple(x[k] for k in keys),[]).append(x)
    summary=[]
    metrics=('observed','hits','reads','admissions','evictions','saturations','hit_ratio','ops_per_second','utility_preservation','incremental_preservation','absolute_utility_loss','admission_reduction','admission_productivity','processing_efficiency','metadata_pressure','update_pressure')
    for k,g in groups.items():
        s=dict(zip(keys,k),repeats=len(g))
        for m in metrics:
            v=[x[m] for x in g if x[m] is not None]
            mean=statistics.mean(v) if v else None
            sd=statistics.stdev(v) if len(v)>1 else None
            s.update({m+'_mean':mean,m+'_sd':sd,m+'_valid':len(v)})
            if m=='ops_per_second':s['throughput_cv']=sd/mean if sd is not None and mean else None
        summary.append(s)
    write(a.out/'capacity_summary.csv',summary)
if __name__=='__main__':main()
