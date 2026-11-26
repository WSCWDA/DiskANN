"""Recompute outputs from compact sets and verify source provenance."""
import argparse,json
import numpy as np
from pathlib import Path
import grouping_characterization as a1
from validate_frequency_capacity import ck,read
from run_residual_overlap import calculate
from residual_locality import NAMES,BUDGETS
def validate(root,source):
    m=json.loads((root/'extraction_manifest.json').read_text());v=json.loads((source/'validation_summary.json').read_text())
    ck(m['source_manifest_sha256']==a1.digest(source/'manifest.json') and m['source_validation_sha256']==a1.digest(source/'validation_summary.json') and m['region_multiset_sha256']==v['region_multiset_sha256'],'source provenance')
    ck((m['queries'],m['unique_regions'],m['logical_requests'],m['group_size'])==(10000,165446,3265956,256),'dataset')
    expected=calculate(root)
    for name,rows in expected.items():
        actual=read(root/name)
        ck(actual==[{k:str(v) for k,v in x.items()} for x in rows],'recompute '+name)
    rows=expected['overlap.csv'];ck(len(rows)==21,'matrix')
    for name in NAMES:
        z=[x for x in rows if x['order']==name]
        ck([x['budget_mib'] for x in z]==list(BUDGETS),'budgets')
        ck(z[0]['covered']==0 and all(x['raw']==x['covered']+x['residual'] for x in z),'conservation')
        ck(all(a['residual']>=b['residual'] for a,b in zip(z,z[1:])),'monotonic residual')
        ck(sum(x['raw'] for x in expected['group_overlap.csv'] if x['order']==name)==z[0]['raw'],'group conservation')
        ck(sum(x[name] for x in expected['frequency_bands.csv'])==z[0]['raw'],'band conservation')
    for x in expected['gains.csv']:ck(x['delta_raw']==x['delta_covered']+x['delta_residual'],'gain conservation')
    names=list(expected)+['query_regions.npz','extraction_manifest.json']+[n+'_order.txt' for n in NAMES]
    a1.atomic_json(root/'validation_summary.json',dict(status='PASS',configs=21,region_multiset_sha256=m['region_multiset_sha256'],files={n:a1.digest(root/n) for n in names}))
    print('PASS 21/21')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();validate(a.out.resolve(),a.source.resolve())
