"""Streaming region validation; one run in memory, no trace upload."""
import csv, hashlib, struct
from collections import Counter, defaultdict
from pathlib import Path
from validate_frequency_capacity import ck,read
ACCESS={'OWNER','BYPASS','READY_HIT','INFLIGHT_JOIN'}
KINDS=ACCESS|{'PUBLISH','ADMIT','REJECT','EVICT_CAPACITY','EVICT_TTL'}
def validate_events(events,q,meta,active):
    ids={int(x['query_id']):x for x in q}
    ck(len(ids)==len(q),'duplicate query')
    mm={int(x['query_id']):x for x in meta}
    ck(len(mm)==len(meta) and mm.keys()==ids.keys(),'meta IDs')
    ck(all(int(x['dropped'])==0 for x in meta),'trace dropped')
    per=defaultdict(Counter); access=defaultdict(list);life={};seq=defaultdict(set)
    counts=Counter();same=0
    for e in events:
        i,g,s,o,l,t,off,n=(int(e[k]) for k in ('query_id','group_id','sequence','owner_query','lifecycle','timestamp_ns','offset','length'))
        k=e['event_type'];key=(off,n)
        ck(i in ids and g==int(ids[i]['group_id']) and k in KINDS,'event identity')
        ck(off>=0 and off%4096==0 and n==4096,'expected 4KiB region')
        ck(s not in seq[i],'duplicate sequence');seq[i].add(s)
        per[i][k]+=1;counts[k]+=1
        if k in ACCESS:access[i].append(key)
        if k=='BYPASS':continue
        ck(o in ids and l>0,'owner identity')
        z=life.setdefault((o,l),[key,Counter(),{}])
        ck(z[0]==key,'lifecycle region');z[1][k]+=1
        if k in ('OWNER','PUBLISH','ADMIT','REJECT','EVICT_CAPACITY','EVICT_TTL'):
            ck(k not in z[2],'duplicate lifecycle event');z[2][k]=t
        if k=='OWNER':ck(i==o,'owner query mismatch')
        if k=='INFLIGHT_JOIN' and g==int(ids[o]['group_id']):same+=1
    digest=hashlib.sha256()
    for i,x in sorted(ids.items()):
        c=per[i];n=lambda k:int(x[k])
        ck(sum(c.values())==int(mm[i]['events']),'event count')
        ck(sum(c[k] for k in ACCESS)==n('reader_requests'),'logical count')
        ck(c['OWNER']+c['BYPASS']==n('submitted_reads')==n('completed_reads'),'reads')
        ck(c['READY_HIT']==n('ready_hits') and c['INFLIGHT_JOIN']==n('shared_hits')-n('ready_hits'),'hits')
        for k,f in [('ADMIT','ready_admissions'),('REJECT','ready_rejects'),('EVICT_CAPACITY','ready_capacity_evictions'),('EVICT_TTL','ready_ttl_evictions')]:ck(c[k]==n(f),f)
        ck(sum(z[1] for z in access[i])==n('reader_bytes'),'logical bytes')
        digest.update(struct.pack('<QQ',i,len(access[i])))
        for off,nbytes in sorted(access[i]):digest.update(struct.pack('<QQ',off,nbytes))
    resident=set();unused=0
    for key,c,t in life.values():
        ev=c['EVICT_CAPACITY']+c['EVICT_TTL']
        ck(c['OWNER']==c['PUBLISH']==1 and t['OWNER']<=t['PUBLISH'],'owner publish')
        ck(c['ADMIT']+c['REJECT']==int(active) and ev<=c['ADMIT'],'retention lifecycle')
        ck(not c['READY_HIT'] or c['ADMIT'],'hit without admission')
        if ev:
            ck(t.get('EVICT_CAPACITY',t.get('EVICT_TTL',0))>=t['ADMIT'],'eviction time')
            unused+=not c['READY_HIT']
        if c['ADMIT'] and not ev:
            ck(key not in resident,'duplicate resident');resident.add(key)
    ck(sum(k[1] for k in resident)<=16777216,'resident budget')
    ck(unused==sum(int(x['ready_unused_evictions']) for x in q),'unused eviction count')
    return dict(region_multiset_sha256=digest.hexdigest(),events=sum(counts.values()),dropped=0,unique_regions=len({k for a in access.values() for k in a}),resident_regions=len(resident),same_group_joins=same,**{k.lower():counts[k] for k in sorted(KINDS)})
def inspect_trace(p,q,active):
    stem=str(p)+'_L100_run0'
    with open(stem+'_regions.csv') as f:
        return validate_events(csv.DictReader(f),q,read(stem+'_region_meta.csv'),active)
if __name__=='__main__':
    import argparse
    from run_residual_locality import validate
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);validate(p.parse_args().out.resolve())
