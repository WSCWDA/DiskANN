"""One-shot offline A2.2 A/B/C. No search binary execution."""
import argparse,json
from pathlib import Path
import numpy as np
import grouping_characterization as a1
from validate_frequency_capacity import ck,write
from extract_query_regions import extract
from residual_locality import analyze,NAMES
from analyze_region_frequency import bands
def calculate(root):
    with np.load(root/'query_regions.npz',allow_pickle=False) as z:
        ptr,ids,keys=(z[k] for k in ('query_indptr','region_ids','region_keys'))
    m=json.loads((root/'extraction_manifest.json').read_text());n=m['queries'];u=m['unique_regions']
    ck(ptr.shape==(n+1,) and ptr[0]==0 and ptr[-1]==len(ids)==m['distinct_query_region_pairs'] and np.all(ptr[1:]>=ptr[:-1]),'CSR pointers')
    ck(keys.shape==(u,2) and np.all(keys[:,1]==4096) and np.all(keys[:,0]%4096==0) and np.all(keys[1:,0]>keys[:-1,0]),'keys')
    ck(ids.ndim==1 and np.all(ids<u),'region IDs')
    for i in range(n):
        a=ids[int(ptr[i]):int(ptr[i+1])];ck(np.all(a[1:]>a[:-1]),'set order')
    orders={name:a1.load_order(root/(name+'_order.txt'),n) for name in NAMES}
    rows,gains,f,ds,gs,rank=analyze(ptr,ids,orders,u,m['group_size'])
    fr=bands(f,ds,rank)
    groups=[dict(order=name,group_id=g,queries=q,pairs=p,unique_regions=k,raw=d) for name in NAMES for g,q,p,k,d in gs[name]]
    regions=[dict(region_id=i,offset=int(keys[i,0]),length=4096,frequency=int(f[i]),original=int(ds['original'][i]),random=int(ds['random'][i]),similarity=int(ds['similarity'][i]),delta_similarity=int(ds['similarity'][i]-ds['original'][i])) for i in rank]
    return {'overlap.csv':rows,'gains.csv':gains,'frequency_bands.csv':fr,'group_overlap.csv':groups,'region_frequency.csv':regions}
def run(source,out):
    out.mkdir(parents=True,exist_ok=False);extract(source,out)
    for name,rows in calculate(out).items():write(out/name,rows)
    from validate_residual_overlap import validate
    validate(out,source)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.source.resolve(),a.out.resolve())
