"""Region-level attribution, with signed differences (not causal matching)."""
import csv
from collections import Counter
import numpy as np
from validate_frequency_capacity import ck
from validate_residual_locality import ACCESS,KINDS
FIELDS=('logical','reads','ready','joins','same_group','cross_group','same_query','admit','reject','evict_capacity','evict_ttl')
def aggregate(events, offsets, groups):
    lookup={int(x):i for i,x in enumerate(offsets)}
    a=np.zeros((len(offsets),len(FIELDS)),dtype=np.int64)
    ix={k:i for i,k in enumerate(FIELDS)}
    counts=Counter()
    for e in events:
        k=e['event_type'];off=int(e['offset']);q=int(e['query_id']);g=int(e['group_id'])
        ck(k in KINDS and off in lookup and int(e['length'])==4096 and q in groups and groups[q]==g,'event identity')
        row=a[lookup[off]];counts[k]+=1
        if k in ACCESS:row[ix['logical']]+=1
        if k in ('OWNER','BYPASS'):row[ix['reads']]+=1
        elif k=='READY_HIT':row[ix['ready']]+=1
        elif k=='INFLIGHT_JOIN':
            o=int(e['owner_query']);ck(o in groups,'owner')
            row[ix['joins']]+=1
            row[ix['same_query' if o==q else 'same_group' if groups[o]==g else 'cross_group']]+=1
        elif k in ('ADMIT','REJECT','EVICT_CAPACITY','EVICT_TTL'):
            row[ix[k.lower()]]+=1
    ck(np.all(a[:,0]==a[:,1:4].sum(axis=1)),'region access conservation')
    ck(np.all(a[:,3]==a[:,4:7].sum(axis=1)),'join conservation')
    return a,counts
def compare(base,other,static):
    ck(np.array_equal(base[:,0],other[:,0]),'region logical count')
    d=other-base
    gain=-d[:,1]
    ck(np.array_equal(gain,d[:,2]+d[:,3]),'gain conservation')
    quadrant=np.where(static>0,np.where(gain>0,1,4),np.where(gain>0,2,3))
    return gain,d[:,2],d[:,3],quadrant
def summarize(mask,static,gain,ready,joins):
    return dict(regions=int(mask.sum()),static_gain=int(static[mask].sum()),read_gain=int(gain[mask].sum()),ready_delta=int(ready[mask].sum()),join_delta=int(joins[mask].sum()),positive_read_gain=int(gain[mask & (gain>0)].sum()),negative_read_gain=int(gain[mask & (gain<0)].sum()))
