"""Merge validated core/sensitivity results without duplicating observations."""
import argparse, csv, json, math, statistics as st, subprocess
from pathlib import Path
from final_factorial import POLICIES, plan, effects, digest, atomic, load, ck, write

ALLOWED={'scripts/qshape/merge_final_factorial.py','scripts/qshape/test_merge_final_factorial.py','docs/qshape/factorial_sensitivity.md'}
PAIRS={'G':[('A1','A0'),('A4','A2'),('A5','A3'),('A7','A6')],'S':[('A2','A0'),('A4','A1'),('A6','A3'),('A7','A5')],'R':[('A3','A0'),('A5','A1'),('A6','A2'),('A7','A4')]}
def compatible(a,b):
    ck(a.keys()==b.keys(),'manifest fields')
    for k in a:
        if k not in ('stage','cases','commit'):ck(a[k]==b[k],'manifest mismatch: '+k)
    if a['commit']!=b['commit']:
        paths=subprocess.check_output(['git','diff','--name-only',a['commit'],b['commit'],'--'],text=True).splitlines()
        ck(set(paths)<=ALLOWED,'execution revision mismatch: '+str(paths))
    return True
def key(c):
    r,t,b,i=c
    return r,t,0 if POLICIES[i][2]=='none' else b,i
def rowkey(x):return int(x['repeat']),int(x['threads']),int(x['ready_mib']),x['case']
def index(rows,expected):
    z={}
    for x in rows:
        k=rowkey(x);ck(k not in z,'duplicate '+str(k));z[k]=x
    ck(set(z)==set(expected),'matrix incomplete or unexpected')
    return z
def read_stage(root,stage):
    m=load(root/'manifest.json');v=load(root/'validation_summary.json')
    ck(m['stage']==stage and m['cases']==[list(c) for c in plan(stage)],'stage matrix')
    ck(m['policies']=={k:list(v) for k,v in POLICIES.items()},'policy mapping')
    ck(v['status']=='PASS' and v['runs']==len(plan(stage)),'source validation')
    ck('metrics.csv' in v['files'],'missing metrics hash')
    for name,h in v['files'].items():ck(name in ('metrics.csv','summary.csv','paired.csv') and digest(root/name)==h,'source hash '+name)
    with (root/'metrics.csv').open() as f:rows=list(csv.DictReader(f))
    for x in rows:
        for k in x:
            if k in ('case','ids_sha256','dists_sha256') or x[k]=='':continue
            try:x[k]=int(x[k])
            except ValueError:x[k]=float(x[k])
            ck(math.isfinite(x[k]),'nonfinite '+k)
        ck(float(x['recall'])==float(v['recall']),'recall')
        x['source_stage']=stage
    index(rows,[key(c) for c in plan(stage)])
    return m,rows
def stats(a):
    m=st.mean(a);h=2.776445*st.stdev(a)/math.sqrt(5)
    ck(len(a)==5,'repeat count')
    return dict(mean=m,ci_low=m-h,ci_high=m+h,positive=sum(x>0 for x in a),minimum=min(a),maximum=max(a))
def attribution(a,b):
    j=a['inflight_hits']-b['inflight_hits'];h=a['ready_hits']-b['ready_hits'];n=b['submitted_reads']-a['submitted_reads']
    ck(j+h==n,'I/O attribution')
    return dict(join_delta=j,ready_delta=h,saved_reads=n,search_saved_ms=b['search_ms']-a['search_ms'],extra_grouping_ms=a['grouping_ms']-b['grouping_ms'],net_saved_ms=b['e2e_ms']-a['e2e_ms'])
def block(z,r,t,b):
    return {i:z[key((r,t,b,i))] for i in POLICIES}
def analyze(rows):
    z=index(rows,[key(c) for c in plan('core')+plan('sensitivity')])
    ref=None
    for x in rows:
        sig=tuple(x[k] for k in ('ids_sha256','dists_sha256','recall','reader_requests','reader_bytes'))
        if ref is None:ref=sig
        ck(sig==ref,'cross-stage logical/result mismatch')
        ck(x['reader_requests']==x['submitted_reads']+x['inflight_hits']+x['ready_hits'],'request conservation')
        ck(x['reader_bytes']>=x['submitted_bytes']>=0,'byte range')
        ck(x['e2e_qps']>0 and x['search_qps']>0 and x['submitted_reads']>0,'invalid metrics')
    summary=[];paired=[];conditional=[];factorial=[];app=[]
    for t,b,i in sorted({k[1:] for k in z}):
        g=[z[r,t,b,i] for r in range(1,6)]
        d=dict(threads=t,ready_mib=b,case=i,repeats=5)
        for k,v in g[0].items():
            if k not in d and k!='repeat' and isinstance(v,(int,float)):d[k]=st.mean(x[k] for x in g)
        d['qps_cv']=st.stdev(x['e2e_qps'] for x in g)/d['e2e_qps'];summary.append(d)
    for t in (16,64):
        for b in (4,16,64):
            blocks=[block(z,r,t,b) for r in range(1,6)]
            base=dict(threads=t,ready_mib=b)
            local=[]
            for r,g in enumerate(blocks,1):
                a,c=g['A7'],g['A6']
                d=dict(**base,repeat=r,baseline_source=g['A0']['source_stage'],speedup=a['e2e_qps']/g['A0']['e2e_qps'],grouping_gain=a['e2e_qps']/c['e2e_qps']-1,search_gain=a['search_qps']/c['search_qps']-1,read_reduction=1-a['submitted_reads']/c['submitted_reads'],overall_read_reduction=1-a['submitted_reads']/g['A0']['submitted_reads'],sharing_gain=a['e2e_qps']/g['A5']['e2e_qps']-1,retention_gain=a['e2e_qps']/g['A4']['e2e_qps']-1,cms_exact=a['e2e_qps']/g['R2']['e2e_qps'],cms_lru=a['e2e_qps']/g['R1']['e2e_qps'],**attribution(a,c),**effects(g))
                paired.append(d);local.append(d)
            for mechanism,pairs in PAIRS.items():
                for a,c in pairs:
                    gains=[g[a]['e2e_qps']/g[c]['e2e_qps']-1 for g in blocks]
                    conditional.append(dict(**base,mechanism=mechanism,numerator=a,denominator=c,**stats(gains),search_gain=st.mean(g[a]['search_qps']/g[c]['search_qps']-1 for g in blocks),read_reduction=st.mean(1-g[a]['submitted_reads']/g[c]['submitted_reads'] for g in blocks)))
            for k in local[0]:
                if k.startswith('effect_'):
                    d=stats([x[k] for x in local]);factorial.append(dict(**base,effect=k,**d,exp_effect=math.exp(d['mean'])))
            d=dict(**base,**stats([x['grouping_gain'] for x in local]))
            for k in ('search_gain','read_reduction','join_delta','ready_delta','saved_reads','search_saved_ms','extra_grouping_ms','net_saved_ms'):d[k]=st.mean(x[k] for x in local)
            d['classification']='positive' if d['ci_low']>0 else 'negative' if d['ci_high']<0 else 'inconclusive'
            app.append(d)
    return dict(merged_metrics=rows,merged_summary=summary,merged_paired=paired,conditional_effects=conditional,factorial_effects=factorial,grouping_applicability=app)
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','merge']);p.add_argument('--core',type=Path,required=True);p.add_argument('--sensitivity',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    m,rows=read_stage(a.core,'core')
    if a.action=='preflight':
        from final_factorial import config
        from argparse import Namespace
        compatible(m,config(Namespace(stage='sensitivity',device=m['device'])))
        print('PASS core 50/50 and current execution compatibility');return
    ck(a.sensitivity is not None and a.out is not None,'sensitivity/out required')
    n,other=read_stage(a.sensitivity,'sensitivity');compatible(m,n)
    result=analyze(rows+other)
    ck([len(x) for x in result.values()]==[220,44,30,72,42,6],'output counts')
    a.out.mkdir(parents=True,exist_ok=True)
    ck(not any(a.out.iterdir()),'output must be empty')
    for k,v in result.items():write(a.out/(k+'.csv'),v)
    atomic(a.out/'validation_summary.json',dict(status='PASS',runs=220,paired_blocks=30,source_manifests=[digest(a.core/'manifest.json'),digest(a.sensitivity/'manifest.json')],source_metrics=[digest(a.core/'metrics.csv'),digest(a.sensitivity/'metrics.csv')],files={k+'.csv':digest(a.out/(k+'.csv')) for k in result}))
    print('PASS 220/220, 30 paired blocks')
if __name__=='__main__':main()
