#!/usr/bin/env python3
import argparse, csv, glob, math, os, re, statistics
from collections import defaultdict
p=argparse.ArgumentParser(); p.add_argument("--raw",default="results/raw"); p.add_argument("--output",default="results/summary.csv"); a=p.parse_args()
files=glob.glob(os.path.join(a.raw,"*.metrics.csv")); groups=defaultdict(list); recalls={}
pat=re.compile(r"(?P<dataset>.+)_(?P<backend>libaio|pread-direct|pread-buffered|io-uring|gds)_L(?P<L>\d+)_W(?P<W>\d+)_T(?P<T>\d+)_C(?P<C>\d+)_(?P<state>cold|warm)_r(?P<run>\d+)")
for path in files:
    m=pat.search(os.path.basename(path))
    if not m or int(m["run"])==0: continue
    with open(path,newline="") as f: groups[tuple(m.group(k) for k in ("dataset","backend","L","W","T","C","state","run"))]+=list(csv.DictReader(f))
    recalls[path]=float(groups[tuple(m.group(k) for k in ("dataset","backend","L","W","T","C","state","run"))][-1].get("recall","nan"))
def pct(v,q):
    s=sorted(v); return s[min(len(s)-1,int(q*(len(s)-1)))]
columns="dataset backend destination L beam_width threads cache_nodes cache_state actual_cache_hit_ratio mean_io_size mean_batch_size qps mean_latency_us p50_latency_us p95_latency_us p99_latency_us p999_latency_us mean_ios_per_query mean_bytes_per_query read_iops read_bw_MBps cpu_user_pct cpu_sys_pct recall_at_10 run validity".split()
os.makedirs(os.path.dirname(a.output) or ".",exist_ok=True)
with open(a.output,"w",newline="") as f:
  out=csv.DictWriter(f,fieldnames=columns);out.writeheader()
  for key,rows in sorted(groups.items()):
    dataset,backend,L,W,T,C,state,run=key; lat=[float(r["latency_us"]) for r in rows]; ios=[int(r["io_requests"]) for r in rows]; byt=[int(r["io_bytes"]) for r in rows]; batches=[int(r["io_batches"]) for r in rows]; hits=sum(int(r["cache_hits"]) for r in rows); misses=sum(int(r["cache_misses"]) for r in rows)
    qps=float(rows[0].get("qps","nan")); recall=next((v for pth,v in recalls.items() if os.path.basename(pth).startswith(f"{dataset}_{backend}_L{L}_W{W}_T{T}_C{C}_{state}_r{run}")),math.nan)
    base=[v for pth,v in recalls.items() if os.path.basename(pth).startswith(f"{dataset}_libaio_L{L}_W{W}_T{T}_C{C}_{state}_r{run}")]
    valid=not base or math.isnan(recall) or abs(recall-base[0])<=1e-6
    out.writerow(dict(dataset=dataset,backend=backend,destination="gpu" if backend=="gds" else "cpu",L=L,beam_width=W,threads=T,cache_nodes=C,cache_state=state,actual_cache_hit_ratio=hits/max(1,hits+misses),mean_io_size=sum(byt)/max(1,sum(ios)),mean_batch_size=sum(ios)/max(1,sum(batches)),qps=qps,mean_latency_us=statistics.mean(lat),p50_latency_us=pct(lat,.5),p95_latency_us=pct(lat,.95),p99_latency_us=pct(lat,.99),p999_latency_us=pct(lat,.999),mean_ios_per_query=statistics.mean(ios),mean_bytes_per_query=statistics.mean(byt),read_iops="",read_bw_MBps="",cpu_user_pct="",cpu_sys_pct="",recall_at_10=recall,run=run,validity="PASS" if valid else "INVALID"))
print(a.output)
