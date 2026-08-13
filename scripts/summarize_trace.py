#!/usr/bin/env python3
import argparse, csv, statistics
from collections import Counter, defaultdict

p=argparse.ArgumentParser(); p.add_argument("trace"); a=p.parse_args()
with open(a.trace,newline="") as f: rows=[{**r,"query_id":int(r["query_id"]),"batch_id":int(r["batch_id"]),"offset":int(r["offset"]),"len":int(r["len"]),"batch_size":int(r["batch_size"])} for r in csv.DictReader(f)]
if not rows: raise SystemExit("empty trace")
def pct(v,q):
    s=sorted(v); return s[min(len(s)-1,int(q*(len(s)-1)))]
queries=defaultdict(list); batches={}
for r in rows: queries[r["query_id"]].append(r); batches[(r["query_id"],r["batch_id"])]=r["batch_size"]
offsets=[r["offset"] for r in rows]; sizes=[r["len"] for r in rows]; bs=list(batches.values())
intra=sum(len(v)-len(set(x["offset"] for x in v)) for v in queries.values())
owners=defaultdict(set)
for q,v in queries.items():
    for r in v: owners[r["offset"]].add(q)
inter=sum(1 for q in owners.values() if len(q)>1)
adj=sum(1 for x,y in zip(rows,rows[1:]) if x["offset"]+x["len"]==y["offset"])
jumps=[abs(y["offset"]-x["offset"]) for x,y in zip(rows,rows[1:])]
print(f"total_queries,{len(queries)}\ntotal_io,{len(rows)}\nio_per_query,{len(rows)/len(queries):.6f}\nbytes_per_query,{sum(sizes)/len(queries):.6f}")
print(f"batch_mean,{statistics.mean(bs):.6f}\nbatch_p50,{pct(bs,.5)}\nbatch_p95,{pct(bs,.95)}\nbatch_p99,{pct(bs,.99)}\nbatch_max,{max(bs)}")
print(f"unique_offsets,{len(set(offsets))}\noffset_reuse_ratio,{1-len(set(offsets))/len(rows):.6f}\nintra_query_reuses,{intra}\ninter_query_reused_offsets,{inter}")
print(f"sequential_adjacency_ratio,{adj/max(1,len(rows)-1):.6f}\nmean_random_jump_bytes,{statistics.mean(jumps):.6f}\nbatches_per_query,{len(batches)/len(queries):.6f}")
print("io_size_distribution,"+";".join(f"{k}:{v}" for k,v in sorted(Counter(sizes).items())))
