"""Check saved arrays, pair differences, and aggregate conservation."""
import argparse,json
from pathlib import Path
import numpy as np
import grouping_characterization as a1
from validate_frequency_capacity import ck,read
from runtime_attribution import compare,summarize,FIELDS
def validate(out):
    runs=read(out/'runs.csv');pairs=read(out/'paired.csv');quads=read(out/'quadrants.csv');bands=read(out/'quadrant_bands.csv');rb=read(out/'runtime_bands.csv')
    ck((len(runs),len(pairs),len(quads),len(bands),len(rb))==(18,12,48,240,90),'matrix')
    def check(row,expected):
        ck(all(int(row[k])==v for k,v in expected.items()),'aggregate mismatch')
    with np.load(out/'runtime_regions.npz',allow_pickle=False) as z:
        for x in runs:
            a=z[x['repeat']+'_'+x['case']]
            ck(a.shape==(165446,len(FIELDS)) and np.all(a>=0),'array shape')
            ck(np.all(a[:,0]==a[:,1:4].sum(axis=1)) and np.all(a[:,3]==a[:,4:7].sum(axis=1)),'conservation')
            check(x,dict(zip(FIELDS,map(int,a.sum(axis=0)))))
            sub=[y for y in rb if all(y[k]==x[k] for k in ('repeat','case'))]
            ck(len(sub)==5,'bands');check(x,{k:sum(int(y[k]) for y in sub) for k in FIELDS})
        for x in pairs:
            r,b,o=(x[k] for k in ('repeat','base','other'))
            with np.load(out/f'{r}_{b}_{o}.npz',allow_pickle=False) as p:
                st=p['residual_gain'];g,h,j,q=compare(z[r+'_'+b],z[r+'_'+o],st)
                for k,a in [('read_gain',g),('ready_delta',h),('join_delta',j),('quadrant',q)]:ck(np.array_equal(p[k],a),k)
                check(x,summarize(np.ones(len(st),dtype=bool),st,g,h,j))
                sub=[y for y in quads if all(y[k]==x[k] for k in ('repeat','base','other'))]
                ck(len(sub)==4,'quadrants')
                for y in sub:
                    check(y,summarize(q==int(y['quadrant']),st,g,h,j))
                    ss=[v for v in bands if all(v[k]==y[k] for k in ('repeat','base','other','quadrant'))]
                    ck(len(ss)==5,'quadrant bands')
                    check(y,{k:sum(int(v[k]) for v in ss) for k in summarize(q==int(y['quadrant']),st,g,h,j)})
    files={p.name:a1.digest(p) for p in out.iterdir() if p.suffix in ('.csv','.npz') or p.name=='manifest.json'}
    a1.atomic_json(out/'validation_summary.json',dict(status='PASS',runs=18,pairs=12,files=files))
    print('PASS 18/18 runs; 12/12 paired comparisons')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);validate(p.parse_args().out)
