"""Extract verified per-query sets from A2.1 D0, preserving multiset digest."""
import csv, hashlib, json, struct
from pathlib import Path
import numpy as np
import grouping_characterization as a1
from validate_frequency_capacity import ck,read
from validate_residual_locality import ACCESS,KINDS
from run_residual_locality import receipt
def extract(source,out):
    m=json.loads((source/'manifest.json').read_text())
    v=json.loads((source/'validation_summary.json').read_text())
    ck(m['queries']==10000 and m['repeats']==3 and m['data_type']=='float' and v['status']=='PASS' and v['runs']==18 and v['dropped']==0,'A2.1 formal provenance')
    metrics=read(source/'trace_metrics.csv')
    ck(len(metrics)==18 and {(int(x['repeat']),x['case']) for x in metrics}=={(r,'D'+str(i)) for r in range(1,4) for i in range(6)},'formal matrix')
    ck(all(x['region_multiset_sha256']==v['region_multiset_sha256'] and int(x['dropped'])==0 for x in metrics),'formal digest')
    orders={}; hashes={}
    for case,name in [('D0','original'),('D1','random'),('D2','similarity')]:
        p=a1.prefix(source,1,case);rec=json.loads((p.parent/'receipt.json').read_text())
        ck(rec==receipt(p),'source receipt '+case)
        q=read(a1.files(p)[1]);orders[name]=a1.permutation(q,10000)
        hashes[case]=rec
        if case=='D0':base=q;trace=Path(str(p)+'_L100_run0_regions.csv')
    ck(orders['original']==list(range(10000)),'original order')
    ck(orders['similarity']==a1.load_order(source/'similarity_order.txt',10000) and a1.digest(source/'similarity_order.txt')==m['permutation_sha256'],'fixed order')
    for case,name in [('D0','original'),('D1','random'),('D2','similarity')]:
        z=next(x for x in metrics if int(x['repeat'])==1 and x['case']==case)
        ck(hashlib.sha256(a1.order_text(orders[name]).encode()).hexdigest()==z['order_sha256'],'order digest')
    sets,digest,logical=extract_events(trace,base)
    ck(digest==v['region_multiset_sha256'] and logical==3265956,'multiset digest/count')
    keys=np.unique(np.concatenate(sets));ck(len(keys)==165446,'unique regions')
    indptr=np.zeros(len(sets)+1,dtype=np.uint64)
    indptr[1:]=np.cumsum([len(x) for x in sets],dtype=np.uint64)
    ids=np.searchsorted(keys,np.concatenate(sets)).astype(np.uint32)
    np.savez_compressed(out/'query_regions.npz',query_indptr=indptr,region_ids=ids,region_keys=np.column_stack((keys,np.full(len(keys),4096,dtype=np.uint64))))
    for name,order in orders.items():(out/(name+'_order.txt')).write_text(a1.order_text(order))
    a1.atomic_json(out/'extraction_manifest.json',dict(source=str(source),source_manifest_sha256=a1.digest(source/'manifest.json'),source_validation_sha256=a1.digest(source/'validation_summary.json'),source_receipts=hashes,region_multiset_sha256=digest,logical_requests=logical,queries=len(sets),unique_regions=len(keys),distinct_query_region_pairs=len(ids),group_size=256))
def extract_events(path,q):
    n=len(q);counts={int(x['query_id']):int(x['reader_requests']) for x in q}
    ck(set(counts)==set(range(n)),'query IDs')
    access=[[] for _ in range(n)]
    with path.open() as f:
        for e in csv.DictReader(f):
            k=e['event_type'];ck(k in KINDS,'event kind')
            if k not in ACCESS:continue
            i,off,length=map(int,(e['query_id'],e['offset'],e['length']))
            ck(0<=i<n and off>=0 and off%4096==0 and length==4096,'region')
            access[i].append(off)
    h=hashlib.sha256();sets=[];total=0
    for i,a in enumerate(access):
        ck(len(a)==counts[i],'query count');total+=len(a)
        h.update(struct.pack('<QQ',i,len(a)))
        for off in sorted(a):h.update(struct.pack('<QQ',off,4096))
        sets.append(np.unique(np.asarray(a,dtype=np.uint64)))
    return sets,h.hexdigest(),total
