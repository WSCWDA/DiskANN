import argparse,csv,math
from pathlib import Path
def read(p):
 with p.open() as f:return list(csv.DictReader(f))
def check(ok,msg):
 if not ok:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();m=read(a.out/'manifest.csv')
 check(bool(m) and int((a.out/'complete').read_text())==len(m) and len({x['file'] for x in m})==len(m),'manifest')
 rows=[];inputs={};results={}
 for c in m:
  rr=read(a.out/c['file']);check(len(rr)==1,'row count');x=rr[0]
  for k in ('policy','mode','n','ops','skew','seed','ready_budget','meta_budget'):
   check(x[k]==c[k] if k in ('policy','mode') else float(x[k])==float(c[k]),k)
  v=lambda k:int(x[k]);n=v('ops');h=v('hits');r=v('reads');ad=v('admissions');ev=v('evictions')
  check(all(v(k)>=0 for k in x if k not in ('policy','mode','skew')),'negative')
  check(n==h+r and n>0 and 0<v('observed')<=min(n,v('n')),'requests')
  check(ad==ev+v('resident') and v('unused_evictions')<=ev,'residency')
  check(v('ready_peak')<=v('ready_budget') and v('inflight_peak')<=67108864 and v('live_peak')<=v('ready_budget')+67108864,'budget')
  check(v('resident')*4096<=v('ready_peak'),'resident bytes')
  check(ad+v('rejects')==(0 if x['policy']=='none' else r),'publication')
  if x['policy']=='none':check(h==ad==ev==0,'none')
  check(v('frequency_updates')==(n if x['policy'] in ('exact','cms') else 0) and v('frequency_failures')==0,'frequency')
  check(v('counter_bytes')==(v('meta_budget') if x['policy']=='cms' else 0),'counter bytes')
  check(v('gate_checks')==v('gate_accepts')+v('gate_rejects'),'gate')
  check(v('elapsed_ns')>0,'time')
  key=tuple(c[k] for k in ('n','ops','skew','seed'))
  inp=tuple(x[k] for k in ('fingerprint','checksum','observed'))
  check(inputs.setdefault(key,inp)==inp,'input/data checksum')
  key+=tuple(c[k] for k in ('policy','ready_budget','meta_budget'))
  outcome=tuple(x[k] for k in ('hits','reads','admissions','rejects','evictions','resident','gate_checks','gate_accepts','gate_rejects'))
  check(results.setdefault(key,outcome)==outcome,'mode equivalence')
  x['hit_ratio']=h/n;x['ops_per_second']=n*1e9/v('elapsed_ns');x['admission_productivity']=h/ad if ad else ''
  x['unused_eviction_ratio']=v('unused_evictions')/ev if ev and x['mode']!='perf' else ''
  rows.append(x);print('PASS',c['file'])
 with (a.out/'retention_metrics.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print(f'PASS {len(m)}/{len(m)}')
if __name__=='__main__':main()
