import argparse,csv,collections,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--repeats',type=int,default=3);p.add_argument('--L',type=int,default=100);p.add_argument('--queries',type=int,default=10000);a=p.parse_args()
def ck(ok,msg):
 if not ok:raise RuntimeError(msg)
def rows(path):
 with open(path) as f:yield from csv.DictReader(f)
cases=['original_bounded-local_256_512','similarity_bounded-local_256_512','original_lru_256_512','similarity_lru_256_512','similarity_lru_64_512','similarity_lru_256_2048']
ref=None; summaries=[]
for case in cases:
 order,policy,g,pool=case.split('_')
 for run in range(1,a.repeats+1):
  prefix=a.out/case/str(run)/f'1_{order}_inflight_stats'
  stem=str(prefix)+f'_L{a.L}_run0'
  q=list(rows(stem+'_queries.csv'));meta=list(rows(stem+'_region_meta.csv'))
  ck(len(q)==len(meta)==a.queries,'query count')
  ck(sorted(int(x['query_id']) for x in q)==list(range(a.queries)),'query IDs')
  ck(sorted(int(x['query_id']) for x in meta)==list(range(a.queries)),'meta IDs')
  ck(not any(int(x['dropped']) for x in meta),'trace truncated; increase REGION_EVENT_LIMIT')
  ids=tuple(hashlib.sha256(Path(str(prefix)+f'_{a.L}_{s}.bin').read_bytes()).hexdigest() for s in ('idx_uint32','dists_float'))
  logical=sorted(tuple(int(x[k]) for k in ('query_id','reader_requests','reader_bytes','logical_node_reads','static_cache_hits')) for x in q)
  if ref is None:ref=(ids,logical)
  ck(ref==(ids,logical),'search results')
  counts=collections.Counter();perq=collections.Counter();regions={};life={}
  for e in rows(stem+'_regions.csv'):
   k=(int(e['offset']),int(e['length']));kind=e['event_type'];qid=int(e['query_id']);gid=int(e['group_id']);t=int(e['timestamp_ns']);lid=(int(e['owner_query']),int(e['lifecycle']))
   counts[kind]+=1;perq[qid]+=1
   z=regions.setdefault(k,dict(accesses=0,queries=set(),groups=set(),ready_hits=0,inflight_hits=0,admissions=0,evictions=0))
   if kind in ('OWNER','BYPASS','READY_HIT','INFLIGHT_JOIN'):
    z['accesses']+=1;z['queries'].add(qid);z['groups'].add(gid)
   if kind=='READY_HIT':z['ready_hits']+=1
   if kind=='INFLIGHT_JOIN':z['inflight_hits']+=1
   if kind=='ADMIT':z['admissions']+=1
   if kind.startswith('EVICT_'):z['evictions']+=1
   if kind!='BYPASS':
    v=life.setdefault(lid,dict(key=k,owner=0,publish=0,admit=0,reject=0,evict=0,hits=0,joins=0,admit_ns=0,evict_ns=0))
    ck(v['key']==k,'lifecycle key')
    field={'OWNER':'owner','PUBLISH':'publish','ADMIT':'admit','REJECT':'reject','READY_HIT':'hits','INFLIGHT_JOIN':'joins','EVICT_TTL':'evict','EVICT_CAPACITY':'evict'}.get(kind)
    ck(field is not None,'unexpected event '+kind);v[field]+=1
    if kind=='ADMIT':v['admit_ns']=t
    if kind.startswith('EVICT_'):v['evict_ns']=t
  for x in meta:ck(perq[int(x['query_id'])]==int(x['events']),'event count')
  total=lambda k:sum(int(x[k]) for x in q)
  ck(counts['OWNER']+counts['BYPASS']==total('submitted_reads')==total('completed_reads') and not total('completion_errors'),'read conservation')
  ck(counts['READY_HIT']==total('ready_hits') and counts['INFLIGHT_JOIN']==total('shared_hits')-total('ready_hits'),'hit conservation')
  ck(counts['ADMIT']==total('ready_admissions') and counts['REJECT']==total('ready_rejects'),'admission conservation')
  ck(counts['EVICT_CAPACITY']==total('ready_capacity_evictions') and counts['EVICT_TTL']==total('ready_ttl_evictions'),'eviction conservation')
  ck(counts['OWNER']+counts['BYPASS']+counts['READY_HIT']+counts['INFLIGHT_JOIN']==total('reader_requests'),'access conservation')
  resident=set();unused=0
  for v in life.values():
   ck(v['owner']==v['publish']==1 and v['admit']+v['reject']==1 and v['evict']<=v['admit'],'lifecycle conservation')
   ck(not v['hits'] or v['admit'],'hit without admission')
   if v['evict']:ck(v['evict_ns']>=v['admit_ns'],'eviction time');unused+=v['hits']==0
   if v['admit'] and not v['evict']:ck(v['key'] not in resident,'duplicate resident');resident.add(v['key'])
  ck(sum(k[1] for k in resident)<=16777216,'resident budget')
  ck(unused==total('ready_unused_evictions'),'unused evictions')
  path=Path(stem+'_region_summary.csv')
  with path.open('w') as f:
   w=csv.writer(f);w.writerow(['offset','length','accesses','distinct_queries','distinct_groups','ready_hits','inflight_hits','admissions','evictions','final_resident'])
   for k,z in regions.items():w.writerow([*k,z['accesses'],len(z['queries']),len(z['groups']),z['ready_hits'],z['inflight_hits'],z['admissions'],z['evictions'],int(k in resident)])
  summaries.append(dict(case=case,run=run,unique_regions=len(regions),resident_regions=len(resident),unused_evictions=unused,**counts))
  print('PASS',case,run,flush=True)
with (a.out/'region_validation_summary.json').open('w') as f:json.dump(summaries,f,indent=2)
