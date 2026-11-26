"""Frequency bands use disjoint rank intervals; signed gains may cancel."""
import numpy as np
def bands(f,ds,rank):
    u=len(f);edges=sorted(set([0,int(u*.001),int(u*.01),min(u,4096),int(u*.1),u]))
    rows=[]
    for lo,hi in zip(edges,edges[1:]):
        k=rank[lo:hi];delta=ds['similarity'][k]-ds['original'][k]
        rows.append(dict(rank_start=lo,rank_end=hi,regions=len(k),min_frequency=int(f[k].min()),max_frequency=int(f[k].max()),query_region_pairs=int(f[k].sum()),original=int(ds['original'][k].sum()),random=int(ds['random'][k].sum()),similarity=int(ds['similarity'][k].sum()),delta_similarity=int(delta.sum()),positive_gain=int(delta[delta>0].sum()),negative_gain=int(delta[delta<0].sum())))
    return rows
