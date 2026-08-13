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
if a.trace:
 t=pd.read_csv(a.trace)
 for col,name in [("len","io_size_distribution.png"),("batch_size","batch_size_distribution.png")]:
  plt.figure();sns.histplot(t[col],discrete=True);plt.tight_layout();plt.savefig(os.path.join(a.out,name),dpi=200);plt.close()
