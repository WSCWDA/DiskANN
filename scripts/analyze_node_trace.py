#!/usr/bin/env python3
"""Analyze actual DiskANN node events; output metrics, per-node CSV and plots."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

def analyze(path):
    events=Counter()
    owners=defaultdict(set)
    degree={}
    entries=Counter()
    query_ids=set()
    pages=defaultdict(set)
    with open(path,newline="") as f:
        for row in csv.DictReader(f):
            q=int(row["query_id"]); n=int(row["node_id"]); typ=row["event_type"]
            query_ids.add(q); events[typ]+=1
            if typ=="EXPAND":
                owners[n].add(q)
                pages[int(row["offset"])].add(q)
            elif typ=="ENTRY":
                entries[n]+=1
            elif typ=="NEIGHBORS":
                degree[n]=int(row["degree"])
    visits={n:len(qs) for n,qs in owners.items()}
    total=sum(visits.values())
    ranked=sorted(visits,key=lambda n:(-visits[n],n))
    def coverage(k): return sum(visits[n] for n in ranked[:k])/total if total else 0
    reused=sum(1 for v in visits.values() if v>1)
    # Expansion events are one per selected node, not necessarily a disk read.
    metrics=dict(total_queries=len(query_ids),expansion_events=events["EXPAND"],
        unique_expanded_nodes=len(visits),cross_query_reused_nodes=reused,
        cross_query_reused_node_fraction=reused/len(visits) if visits else 0,
        repeated_expansion_fraction=(total-len(visits))/total if total else 0,
        top_10_node_coverage=coverage(10),top_100_node_coverage=coverage(100),
        top_1000_node_coverage=coverage(1000),entry_events=events["ENTRY"],
        unique_entry_nodes=len(entries),cache_hit_events=events["CACHE_HIT"],
        io_submit_node_events=events["IO_SUBMIT"],
        expanded_page_count=len(pages),
        cross_query_reused_expanded_pages=sum(len(q)>1 for q in pages.values()))
    return metrics,ranked,visits,degree,entries

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--out",default="node_analysis")
    args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    m,ranked,visits,degree,entries=analyze(args.trace)
    with (out/"node_metrics.json").open("w") as f: json.dump(m,f,indent=2)
    with (out/"node_frequency.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["node_id","query_count","out_degree","entry_count"])
        for n in ranked:w.writerow([n,visits[n],degree.get(n,""),entries.get(n,0)])
    with (out/"node_metrics.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["metric","value"]);w.writerows(m.items())
    print(json.dumps(m,indent=2))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib missing: CSV/JSON generated, plots skipped")
        return
    fig,ax=plt.subplots(figsize=(7,4))
    ax.plot(range(1,len(ranked)+1),[visits[n] for n in ranked],linewidth=1)
    ax.set(xlabel="Node rank by query frequency",ylabel="Distinct queries expanding node",
           title="Node access skew")
    ax.set_xscale("log");ax.set_yscale("log");fig.tight_layout()
    fig.savefig(out/"node_frequency_rank.png",dpi=200);plt.close(fig)
    fig,ax=plt.subplots(figsize=(6,4))
    ks=[10,100,1000]
    ax.bar([str(k) for k in ks],[m["top_"+str(k)+"_node_coverage"]*100 for k in ks])
    ax.set(xlabel="Top-K nodes",ylabel="Share of expansion events (%)",
           title="Hot-node coverage")
    fig.tight_layout();fig.savefig(out/"node_topk_coverage.png",dpi=200);plt.close(fig)
    pairs=[(degree[n],visits[n]) for n in ranked if n in degree]
    if pairs:
        fig,ax=plt.subplots(figsize=(6,4))
        ax.scatter([x for x,y in pairs],[y for x,y in pairs],s=4,alpha=.2)
        ax.set(xlabel="Out-degree (observed adjacency length)",
               ylabel="Distinct queries expanding node",
               title="Out-degree versus query frequency")
        fig.tight_layout();fig.savefig(out/"node_degree_frequency.png",dpi=200);plt.close(fig)
if __name__=="__main__":main()
