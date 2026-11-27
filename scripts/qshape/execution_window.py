"""Fixed-membership, greedy execution-window ordering; no runtime barriers."""
import numpy as np
import random
def reorder(order,score,g=256,w=64):
    if g<=0 or w<=0:raise ValueError('window')
    result=[]
    for start in range(0,len(order),g):
        group=list(order[start:start+g]);s=np.asarray(score(group),dtype=np.float64)
        if s.shape!=(len(group),len(group)) or not np.isfinite(s).all():raise ValueError('score')
        left=list(range(len(group)))
        while left:
            chosen=[left.pop(0)]
            utility=s[chosen[0]].copy()
            while left and len(chosen)<w:
                j=max(left,key=lambda j:(utility[j],-j))
                left.remove(j);chosen.append(j);utility+=s[j]
            result.extend(group[j] for j in chosen)
    return result
def random_order(order,g=256,seed=42):
    rng=random.Random(seed);out=[]
    for i in range(0,len(order),g):
        x=list(order[i:i+g]);rng.shuffle(x);out.extend(x)
    return out
def vector_score(v,group):
    x=v[group].astype(np.float64);n=(x*x).sum(axis=1)
    return -(n[:,None]+n[None,:]-2*x@x.T)
def oracle_score(sets,group):
    # Distinct physical region intersection, not future timestamps.
    n=len(group);s=np.zeros((n,n))
    for i in range(n):
        for j in range(i):
            s[i,j]=s[j,i]=len(sets[group[i]] & sets[group[j]])
    return s
def check_membership(base,order,g=256):
    if len(base)!=len(order) or sorted(base)!=sorted(order):raise ValueError('permutation')
    for i in range(0,len(base),g):
        if set(base[i:i+g])!=set(order[i:i+g]):raise ValueError('membership')
def window_overlap(order,sets,g=256,w=64):
    total=0
    for i in range(0,len(order),g):
        group=order[i:i+g]
        for j in range(0,len(group),w):
            seen=set()
            for q in group[j:j+w]:
                total+=len(seen & sets[q]);seen.update(sets[q])
    return total
