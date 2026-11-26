"""Static overlap: distinct query-region incidences, not runtime hits."""
import numpy as np
BUDGETS=(0,1,4,8,16,32,64)
NAMES=('original','random','similarity')
def contributions(ptr,ids,order,u,g=256):
    freq=np.bincount(ids,minlength=u).astype(np.int64)
    d=np.zeros(u,dtype=np.int64)
    groups=[]
    for start in range(0,len(order),g):
        qs=order[start:start+g]
        a=np.concatenate([ids[int(ptr[q]):int(ptr[q+1])] for q in qs])
        k,c=np.unique(a,return_counts=True)
        d[k]+=c-1
        groups.append((start//g,len(qs),len(a),len(k),len(a)-len(k)))
    return freq,d,groups
def rank_regions(freq):
    return np.lexsort((np.arange(len(freq)),-freq))
def analyze(ptr,ids,orders,u,g=256):
    ds={};gs={}
    for name in NAMES:
        f,d,groups=contributions(ptr,ids,orders[name],u,g);ds[name]=d;gs[name]=groups
    rank=rank_regions(f);rows=[]
    for name in NAMES:
        d=ds[name];raw=int(d.sum())
        for mb in BUDGETS:
            k=min(u,mb*256);covered=int(d[rank[:k]].sum())
            rows.append(dict(order=name,budget_mib=mb,cache_regions=k,raw=raw,covered=covered,residual=raw-covered,query_region_pairs=int(f.sum()),covered_pairs=int(f[rank[:k]].sum())))
    gains=[]
    for mb in BUDGETS:
        z={x['order']:x for x in rows if x['budget_mib']==mb}
        for name in ('random','similarity'):
            a,b=z['original'],z[name];raw=b['raw']-a['raw'];res=b['residual']-a['residual']
            gains.append(dict(order=name,budget_mib=mb,delta_raw=raw,delta_covered=b['covered']-a['covered'],delta_residual=res,residual_preservation=res/raw if raw>0 else ''))
    return rows,gains,f,ds,gs,rank
