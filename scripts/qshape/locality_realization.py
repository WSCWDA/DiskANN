"""Offline timestamp analysis. Equal timestamps are ambiguous, never causal."""
import numpy as np
from collections import defaultdict
KINDS=('OWNER','BYPASS','READY_HIT','INFLIGHT_JOIN','PUBLISH','ADMIT','REJECT','EVICT_CAPACITY','EVICT_TTL')
ACCESS=set(KINDS[:4])
LIMITS=(10000,50000,100000,500000,1000000,5000000,10000000,100000000,1000000000)
METRICS=('cross_gap','same_group_gap','rank_distance','owner_publish','join_age','join_remaining','post_publish_gap','residence_evicted','residence_censored','reject_next','evict_next','hits_per_admission','unused_eviction','readmission','resident_access','timestamp_tie')
def require(x,msg):
    if not x:raise ValueError(msg)
def region(events,groups,ranks,end,active):
    """Events: (timestamp, query, sequence, owner, lifecycle, kind).
    All time metrics in ns, rank/count metrics in units. Strict next access.
    """
    out=defaultdict(list);life=defaultdict(dict);joins=defaultdict(list);hits=defaultdict(list)
    accesses=sorted(e for e in events if e[5] in ACCESS)
    times=np.array([e[0] for e in accesses],dtype=np.int64)
    last={};lastgroup={};last_other=None;prev=None
    # Latest strictly earlier access by a different query, global and same group.
    # Keep two distinct query IDs per scope, update only after timestamp batch.
    scopes=defaultdict(list)
    def nextgap(t):
        i=np.searchsorted(times,t,side='right')
        return int(times[i])-t if i<len(times) else None
    i=0
    while i<len(accesses):
        j=i+1;t=accesses[i][0]
        while j<len(accesses) and accesses[j][0]==t:j+=1
        if j-i>1:out['timestamp_tie'].append(j-i)
        for _,q,_,_,_,_ in accesses[i:j]:
            for scope,name in ((-1,'cross_gap'),(groups[q],'same_group_gap')):
                for pt,pq in scopes[scope]:
                    if pq!=q:
                        out[name].append(t-pt)
                        if scope==-1:out['rank_distance'].append(abs(ranks[q]-ranks[pq]))
                        break
        for _,q,_,_,_,_ in accesses[i:j]:
            for scope in (-1,groups[q]):
                scopes[scope]=([(t,q)]+[x for x in scopes[scope] if x[1]!=q])[:2]
        i=j
    for t,q,s,o,l,k in events:
        if k=='BYPASS':continue
        key=(o,l)
        if k=='INFLIGHT_JOIN':joins[key].append(t)
        elif k=='READY_HIT':hits[key].append(t)
        else:
            require(k not in life[key],'duplicate lifecycle event')
            life[key][k]=t
    require(set(joins)<=set(life) and set(hits)<=set(life),'orphan lifecycle')
    admissions=[]
    for key,z in life.items():
        require('OWNER' in z and 'PUBLISH' in z,'missing owner/publish')
        a,p=z['OWNER'],z['PUBLISH'];require(a<=p,'publish order')
        out['owner_publish'].append(p-a)
        for t in joins[key]:
            require(a<=t<=p,'join order');out['join_age'].append(t-a);out['join_remaining'].append(p-t)
        gap=nextgap(p)
        if gap is not None:out['post_publish_gap'].append(gap)
        require(int('ADMIT' in z)+int('REJECT' in z)==int(active),'retention decision')
        if 'REJECT' in z:
            gap=nextgap(z['REJECT'])
            if gap is not None:out['reject_next'].append(gap)
        ev=[z[k] for k in ('EVICT_CAPACITY','EVICT_TTL') if k in z]
        require(len(ev)<=1 and (not ev or 'ADMIT' in z),'eviction')
        if 'ADMIT' in z:
            t=z['ADMIT'];stop=ev[0] if ev else end;require(t<=stop,'residence order')
            admissions.append(t);out['residence_evicted' if ev else 'residence_censored'].append(stop-t)
            out['hits_per_admission'].append(len(hits[key]))
            require(all(t<=x<=stop for x in hits[key]),'hit outside residency')
            # Strict interior only; endpoint ties excluded.
            out['resident_access'].append(max(0,int(np.searchsorted(times,stop,'left')-np.searchsorted(times,t,'right'))))
            if ev:
                out['unused_eviction'].append(int(not hits[key]))
                gap=nextgap(stop)
                if gap is not None:out['evict_next'].append(gap)
        else:require(not hits[key],'hit without admission')
    if admissions:out['readmission'].append(len(admissions)-1)
    return out
def stats(values):
    a=np.asarray(values,dtype=np.int64)
    return [len(a),int(a.sum()),*[int(np.count_nonzero(a<=x)) for x in LIMITS]]
def combine(a,mask):
    z=a[mask].sum(axis=0);n=int(z[0])
    return dict(samples=n,total=int(z[1]),mean=float(z[1]/n) if n else '',**{'le_'+str(x):int(v) for x,v in zip(LIMITS,z[2:])})
