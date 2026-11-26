import argparse,csv,math
from pathlib import Path
def read(p):
 with p.open() as f:return list(csv.DictReader(f))
def check(v,msg):
 if not v:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();m=read(a.out/'manifest.csv')
 check(int((a.out/'complete').read_text())==len(m) and len({x['file'] for x in m})==len(m),'manifest')
 fingerprints={};rows=[]
 for c in m:
  rr=read(a.out/c['file']);diag=c['mode']=='diagnostic';check(len(rr)==(3 if diag else 1),c['file'])
  for x in rr:
   for k in ('mode','backend','n','ops','budget','skew','threads','seed','cover'):
    check(x[k]==c[k] if k in ('mode','backend') else float(x[k])==float(c[k]),k)
   key=tuple(c[k] for k in ('n','ops','skew','seed','cover'));check(fingerprints.setdefault(key,x['fingerprint'])==x['fingerprint'],'input mismatch')
   if x['backend']=='cms':check(int(x['payload_bytes'])==int(x['budget']) and int(x['exact_entries'])==0,'CMS payload')
   else:check(int(x['payload_bytes'])==24*int(x['exact_entries']),'exact field bytes')
   check(int(x['saturations'])>=0,'saturation')
   if diag:
    check(0<int(x['observed'])<=min(int(x['n']),int(x['ops'])),'observed')
    check(int(x['saturations']) or int(x['under'])==0,'underestimate')
    check(0<=int(x['zero'])<=int(x['observed']) and float(x['mae'])>=0,'error')
    check(all(math.isfinite(float(x[k])) and 0<=float(x[k])<=1 for k in ('hot_recall','utility_coverage')),'utility')
    if x['backend']=='exact':check(int(x['zero'])==int(x['observed']) and float(x['utility_coverage'])==1 and float(x['hot_recall'])==1,'exact reference')
   else:check(int(x['elapsed_ns'])>0,'time')
   x['operations_per_second']=int(x['ops'])*1e9/int(x['elapsed_ns']) if int(x['elapsed_ns']) else ''
   rows.append(x)
  print('PASS',c['file'])
 with (a.out/'estimator_metrics.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print(f'PASS {len(m)}/{len(m)}')
if __name__=='__main__':main()
