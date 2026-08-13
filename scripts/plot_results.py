#!/usr/bin/env python3
import argparse, os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
p=argparse.ArgumentParser();p.add_argument("summary");p.add_argument("--trace");p.add_argument("--out",default="results/figures");a=p.parse_args();os.makedirs(a.out,exist_ok=True)
d=pd.read_csv(a.summary);d=d[d.validity=="PASS"]
def line(x,y,name):
  plt.figure();sns.lineplot(data=d,x=x,y=y,hue="backend",marker="o");plt.tight_layout();plt.savefig(os.path.join(a.out,name),dpi=200);plt.close()
line("beam_width","qps","qps_vs_beam.png");line("beam_width","p99_latency_us","p99_vs_beam.png");line("threads","qps","qps_vs_threads.png");line("threads","p99_latency_us","p99_vs_threads.png");line("actual_cache_hit_ratio","qps","performance_vs_cache_hit.png")
for col,name in [("cpu_user_pct","cpu_vs_backend.png"),("read_iops","iops_vs_backend.png")]:
 numeric=pd.to_numeric(d[col],errors="coerce")
 if numeric.notna().any():
  plt.figure();sns.barplot(data=d.assign(value=numeric),x="backend",y="value");plt.tight_layout();plt.savefig(os.path.join(a.out,name),dpi=200);plt.close()
best=d.sort_values("qps",ascending=False).drop_duplicates(["threads","actual_cache_hit_ratio"])
if not best.empty:
 codes={name:i for i,name in enumerate(sorted(best.backend.unique()))};pivot=best.assign(code=best.backend.map(codes)).pivot(index="actual_cache_hit_ratio",columns="threads",values="code")
 plt.figure();sns.heatmap(pivot,annot=True,cbar=False);plt.title("Fastest backend: "+", ".join(f"{v}={k}" for k,v in codes.items()));plt.tight_layout();plt.savefig(os.path.join(a.out,"backend_crossover_heatmap.png"),dpi=200);plt.close()
if a.trace:
 t=pd.read_csv(a.trace)
 for col,name in [("len","io_size_distribution.png"),("batch_size","batch_size_distribution.png")]:
  plt.figure();sns.histplot(t[col],discrete=True);plt.tight_layout();plt.savefig(os.path.join(a.out,name),dpi=200);plt.close()
