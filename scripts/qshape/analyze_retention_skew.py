"""Combine validated B1 and B2 raw runs; no production changes."""
import argparse,json,subprocess
from pathlib import Path
from validate_retention_capacity import validate,check,digest,FIELDS
from analyze_retention_capacity import derive,summarize,write

BASE='8a65adca2e03cc64444195d8c106f2c8d5d5360e'
def compatible(old,new,repo):
    check(old['profile']=='formal' and new['profile']=='skew','profiles')
    check(old['repeats']==new['repeats']==3,'seeds')
    check(not old['tracked_dirty'] and not new['tracked_dirty'],'dirty checkout')
    check(old['bench_sha256']==new['bench_sha256'],'binary mismatch')
    check(old['commit']==BASE,'unexpected B1 commit')
    def git(*args):
        return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
    git('merge-base','--is-ancestor',old['commit'],new['commit'])
    changed=git('diff','--name-only',old['commit'],new['commit']).splitlines()
    check(all(p.startswith('scripts/qshape/') or p.startswith('docs/qshape/') for p in changed),'non-tool source changes')
def select(old,new):
    historical=[x for x in old if x['n']=='1000000' and x['policy'] in ('lru','exact','cms')]
    rows=[dict(x,source='B1') for x in historical]+[dict(x,source='B2') for x in new]
    expected={(str(s),str(seed),p,str(m)) for s in (0,0.8,1,1.2) for seed in (42,43,44)
              for p,m in [('lru',0),('exact',0)]+[('cms',k*1024) for k in (64,256,512,1024,2048)]}
    actual={(x['skew'],x['seed'],x['policy'],x['meta_budget']) for x in rows}
    check(len(rows)==84 and actual==expected,'combined matrix')
    check(all(x['n']=='1000000' and x['ops']=='10000000' and x['ready_budget']=='16777216' and x['mode']=='perf' for x in rows),'combined parameters')
    check(all(x['saturations']==0 for x in rows),'counter saturation')
    return rows
def candidates(rows):
    result=[]
    for skew in ('0','0.8','1','1.2'):
        for budget in (64,256,512,1024,2048):
            g=[x for x in rows if x['skew']==skew and x['policy']=='cms' and int(x['meta_budget'])==budget*1024]
            check(len(g)==3,'candidate seeds')
            meaningful=all(x['incremental_preservation'] is not None for x in g)
            passed=meaningful and all(x['utility_preservation'] is not None and x['utility_preservation']>=.95 and x['incremental_preservation']>=.90 and x['admission_reduction'] is not None and x['admission_reduction']>=.90 and x['processing_efficiency']>=.95 for x in g)
            result.append(dict(skew=skew,budget_kib=budget,status='pass' if passed else ('fail' if meaningful else 'low_reference_gain'),min_reference_gain=min(x['reference_gain'] for x in g),min_incremental=min(x['incremental_preservation'] for x in g) if meaningful else None))
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--b1',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    old=json.loads((a.b1/'config.json').read_text());new=json.loads((a.out/'config.json').read_text())
    compatible(old,new,Path(__file__).resolve().parents[2])
    rows=select(validate(a.b1),validate(a.out))
    metrics=derive(rows,min_reference_gain=.001)
    write(a.out/'skew_metrics.csv',metrics);write(a.out/'skew_summary.csv',summarize(metrics));write(a.out/'skew_candidates.csv',candidates(metrics))
    provenance=[dict(source=x['source'],file=x['file'],sha256=digest((a.b1 if x['source']=='B1' else a.out)/x['file'])) for x in rows]
    write(a.out/'skew_provenance.csv',provenance)
    print('PASS 84/84 (42 historical + 42 new)')
if __name__=='__main__':main()
