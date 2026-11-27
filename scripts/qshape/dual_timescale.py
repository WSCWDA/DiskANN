"""Instantaneous, sharded 4KiB retention model; no asynchronous sharing."""
from collections import OrderedDict, Counter
from array import array
from functools import lru_cache
MASK=(1<<64)-1
def mix(x):
    x &= MASK
    x=((x^(x>>30))*0xbf58476d1ce4e5b9)&MASK
    x=((x^(x>>27))*0x94d049bb133111eb)&MASK
    return x^(x>>31)
@lru_cache(maxsize=262144)
def slots(off):
    shard=(mix(off)^mix(4096+0x9e3779b97f4a7c15))%64
    return shard,tuple(shard*2048+i*512+(mix(mix(off+0x9e3779b97f4a7c15*(i+1))^mix(4096+0xd1b54a32d192ed03*(i+1)))%512) for i in range(4))
POLICIES={'R0':(0,False,False),'R1':(0,True,False),'R2':(1,True,False),'R3':(2,True,False),'R4':(4,True,False),'R5':(8,True,False),'R6':(2,True,True),'R7':(4,True,True)}
class Replay:
    def __init__(self,policy):
        w,self.freq,self.second=POLICIES[policy]
        self.wcap=w*4;self.mcap=64-self.wcap
        self.window=[OrderedDict() for _ in range(64)]
        self.main=[OrderedDict() for _ in range(64)]
        self.ghost=array('Q',[0])*(64*1024) if self.second else None
        self.cms=array('I',[0])*131072 if self.freq else None
        self.c=Counter()
    def estimate(self,k):
        return min(self.cms[i] for i in slots(k)[1])
    def evict(self,d,kind):
        k,used=d.popitem(last=False);self.c[kind+'_evictions']+=1
        self.c[kind+'_unused']+=not used
        return k,used
    def admit(self,d,k,used=False):
        if len(d)==self.mcap:
            victim=next(iter(d))
            if self.freq and self.estimate(k)<=self.estimate(victim):
                self.c['rejects']+=1;return False
            self.evict(d,'main')
        d[k]=used;self.c['main_inserts']+=1;return True
    def access(self,k):
        s,ix=slots(k);w=self.window[s];m=self.main[s];c=self.c;c['ops']+=1
        if self.freq:
            for i in ix:
                if self.cms[i]==0xffffffff:c['saturations']+=1
                else:self.cms[i]+=1
        recent=False
        if self.second:
            i=s*1024+mix(k+17)%1024
            recent=self.ghost[i]==k+1;self.ghost[i]=k+1
        for d,kind in ((w,'window'),(m,'main')):
            if k in d:
                d[k]=True;d.move_to_end(k);c[kind+'_hits']+=1;return
        c['misses']+=1
        if not self.wcap or (self.second and not recent):
            self.admit(m,k);return
        if len(w)==self.wcap:
            v,used=self.evict(w,'window')
            if self.admit(m,v,used):c['promotions']+=1
        w[k]=False;c['window_inserts']+=1
    def result(self):
        c=self.c
        keys=('ops','misses','window_hits','main_hits','window_inserts','main_inserts','promotions','rejects','window_evictions','main_evictions','window_unused','main_unused','saturations')
        d={k:c[k] for k in keys}
        d.update(window_resident=sum(map(len,self.window)),main_resident=sum(map(len,self.main)),cms_bytes=len(self.cms)*self.cms.itemsize if self.freq else 0,ghost_bytes=len(self.ghost)*self.ghost.itemsize if self.second else 0)
        d['hits']=d['window_hits']+d['main_hits']
        return d
def validate(d,p):
    w,f,s=POLICIES[p]
    def ck(x):
        if not x:raise ValueError('counter conservation '+p)
    ck(d['ops']==d['hits']+d['misses'])
    ck(d['hits']==d['window_hits']+d['main_hits'])
    ck(d['window_inserts']-d['window_evictions']==d['window_resident'])
    ck(d['main_inserts']-d['main_evictions']==d['main_resident'])
    ck(d['misses']+d['window_evictions']==d['window_inserts']+d['main_inserts']+d['rejects'])
    ck(d['promotions']<=d['window_evictions'] and d['promotions']<=d['main_inserts'])
    ck(d['window_resident']<=w*256 and d['main_resident']<=(16-w)*256)
    ck(d['window_unused']<=d['window_evictions'] and d['main_unused']<=d['main_evictions'])
    ck(d['cms_bytes']==524288*int(f) and d['ghost_bytes']==524288*int(s) and d['saturations']==0)
