"""Offline bounded exception heuristic; future information is never deployable."""
from bisect import bisect_right
from collections import defaultdict
from array import array
from dual_timescale import Replay, slots, validate as validate_base

BPS={'O0':0,'O1':10,'O2':50,'O3':100,'O4':200,'O5':500}
HORIZON=65536

def future_index(ids):
    positions=defaultdict(lambda:array('I'))
    for t,k in enumerate(ids):positions[int(k)].append(t)
    return positions

def utility(positions,k,t,w):
    a=positions.get(k,())
    return bisect_right(a,t+w)-bisect_right(a,t)

class Oracle(Replay):
    def __init__(self,policy,n,positions,horizon=HORIZON):
        super().__init__('R1')
        if n<=0 or horizon<=0:raise ValueError('invalid length/horizon')
        self.budget=n*BPS[policy]//10000
        self.positions=positions
        self.horizon=horizon
    def admit(self,d,k,used=False):
        if len(d)==self.mcap:
            v=next(iter(d))
            if self.estimate(k)<=self.estimate(v):
                c=self.c;c['cms_denials']+=1
                if c['exceptions']>=self.budget:
                    c['budget_denials']+=1
                else:
                    c['oracle_checks']+=1
                    t=c['ops']-1
                    gain=utility(self.positions,k,t,self.horizon)-utility(self.positions,v,t,self.horizon)
                    if gain>0:
                        c['exceptions']+=1;c['predicted_gain']+=gain
                        self.evict(d,'main');d[k]=used;c['main_inserts']+=1
                        return True
                    c['utility_denials']+=1
                c['rejects']+=1;return False
        return super().admit(d,k,used)
    def result(self):
        d=super().result()
        d.update({k:self.c[k] for k in ('cms_denials','exceptions','budget_denials','oracle_checks','utility_denials','predicted_gain')})
        d.update(budget=self.budget,horizon=self.horizon)
        return d

def validate(d,p):
    validate_base(d,'R1')
    def ck(ok):
        if not ok:raise ValueError('oracle conservation '+p)
    ck(all(isinstance(v,int) and v>=0 for v in d.values()))
    ck(d['budget']==d['ops']*BPS[p]//10000)
    ck(d['exceptions']<=min(d['budget'],d['main_inserts']))
    ck(d['cms_denials']==d['exceptions']+d['rejects'])
    ck(d['cms_denials']==d['budget_denials']+d['oracle_checks'])
    ck(d['oracle_checks']==d['exceptions']+d['utility_denials'])
    ck(d['predicted_gain']>=d['exceptions'] and d['horizon']==HORIZON)
