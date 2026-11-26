import argparse,csv,hashlib
from pathlib import Path
from validate_frequency_capacity import validate_query,recall
def read(p):
 with open(p) as f:return list(csv.DictReader(f))
def check(x,msg):
 if not x:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--repeats',type=int,default=3);p.add_argument('--queries',type=int,default=10000);a=p.parse_args()
 check(int((a.out/'runner_complete').read_text())==a.repeats,'incomplete')
 rows=[];ref=None
 for b in (64,256,512,2048):
  for r in range(1,a.repeats+1):
   for o in ('original','similarity'):
    pre=a.out/f'{b}k'/str(r)/o/f'1_{o}_inflight_stats';stem=str(pre)+'_L100_run0'
    q=read(stem+'_queries.csv');z=read(stem+'_shadow.csv');h=read(stem+'_shadow_histogram.csv')
    check(len(q)==len(z)==a.queries,'query count')
    ids=set(range(a.queries))
    check({int(x['query_id']) for x in q}=={int(x['query_id']) for x in z}==ids,'query IDs')
    zm={int(x['query_id']):x for x in z};hm={}
    for x in h:
     k=(int(x['query_id']),x['kind'],int(x['bucket']))
     check(k not in hm and int(x['count'])>=0,'histogram duplicate/negative');hm[k]=int(x['count'])
    check(len(hm)==a.queries*42,'histogram size')
    for x in q:
     validate_query(x,f'cms_{b}k',b*1024)
     i=int(x['query_id']);v={k:int(n) for k,n in zm[i].items()}
     check(v['updates']==int(x['reader_requests']) and v['failures']==v['invalid']==v['under']==0,'shadow history')
     check(v['checks']==int(x['frequency_gate_checks'])==sum(v[k] for k in ('aa','rr','fa','fr')),'gate conservation')
     check(v['aa']+v['fa']==int(x['frequency_gate_accepts']),'accept conservation')
     for kind,n in [('candidate_error',v['checks']),('victim_error',v['victims'])]+[(f'margin_{j}',v[k]) for j,k in enumerate(('aa','rr','fa','fr'))]:
      check(sum(hm[i,kind,j] for j in range(7))==n,'histogram conservation')
    hashes=tuple(hashlib.sha256(Path(str(pre)+'_100_'+s+'.bin').read_bytes()).hexdigest() for s in ('idx_uint32','dists_float'))
    signature=(hashes,recall(Path(str(pre)+'.log')),sorted((int(x['query_id']),int(x['reader_requests']),int(x['reader_bytes'])) for x in q))
    if ref is None:ref=signature
    check(ref==signature,'cross-config results')
    d=dict(budget_kib=b,run=r,order=o)
    d.update({k:sum(int(x[k]) for x in z) for k in ('updates','checks','aa','rr','fa','fr','victims')})
    d['max_shard_entries']=max(int(x['entries']) for x in z)
    for k in ('reader_requests','submitted_reads','ready_hits','shared_hits'):d[k]=sum(int(x[k]) for x in q)
    for k,n,den in [('agreement',d['aa']+d['rr'],d['checks']),('precision',d['aa'],d['aa']+d['fa']),('recall_accept',d['aa'],d['aa']+d['fr']),('false_accept_rate',d['fa'],d['fa']+d['rr']),('false_reject_rate',d['fr'],d['fr']+d['aa'])]:d[k]=n/den if den else ''
    for kind in ('candidate_error','victim_error','margin_0','margin_1','margin_2','margin_3'):
     for j in range(7):d[f'{kind}_{j}']=sum(hm[i,kind,j] for i in ids)
    rows.append(d);print('PASS',pre,flush=True)
 with (a.out/'shadow_metrics.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print(f'PASS {len(rows)}/{8*a.repeats}')
if __name__=='__main__':main()
