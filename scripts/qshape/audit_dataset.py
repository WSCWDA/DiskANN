"""Strict audit for static, full-vector L2 DiskANN indexes (little endian)."""
import argparse, json, struct
from pathlib import Path
from concurrent_integration import digest
from validate_frequency_capacity import ck

WIDTH={'float':4,'uint8':1,'int8':1}
def header(p):
    with Path(p).open('rb') as f:
        h=f.read(8)
    ck(len(h)==8,'short header: '+str(p))
    n,d=struct.unpack('<II',h);ck(n>0 and d>0,'empty matrix')
    return n,d
def matrix(p,width):
    n,d=header(p);ck(Path(p).stat().st_size==8+n*d*width,'matrix size: '+str(p))
    return n,d
def layout(p):
    p=Path(p)
    with p.open('rb') as f:h=f.read(4096)
    ck(len(h)==4096,'short disk metadata')
    n,c=struct.unpack_from('<II',h);ck(c==1 and 8<=n<=511,'metadata shape')
    a=struct.unpack_from('<'+'Q'*n,h,8)
    points,dim,medoid,node,per,frozen,_,reorder=a[:8]
    ck(points>0 and dim>0 and node>0 and medoid<points,'metadata values')
    ck(frozen==0 and reorder==0,'static non-reorder indexes only')
    ck(per==4096//node,'sector packing')
    sectors=(points+per-1)//per if per else points*((node+4095)//4096)
    ck(p.stat().st_size==(1+sectors)*4096,'disk index size')
    return dict(points=points,dimensions=dim,medoid=medoid,node_bytes=node,nodes_per_sector=per,region_bytes=4096 if per else ((node+4095)//4096)*4096,index_bytes=p.stat().st_size)
def audit(c):
    ck(c['data_type'] in WIDTH and c.get('dist_fn','l2')=='l2','unsupported type/metric')
    w=WIDTH[c['data_type']];q,d=matrix(c['query'],w)
    ix=Path(c['index_prefix']);disk=Path(str(ix)+'_disk.index')
    m=layout(disk);ck(m['dimensions']==d,'query/index dimensions')
    ck(m['node_bytes']>=d*w+4 and (m['node_bytes']-d*w)%4==0,'full-vector node layout')
    ck(not Path(str(disk)+'_pq_pivots.bin').exists(),'disk PQ unsupported')
    pq=Path(str(ix)+'_pq_compressed.bin');pn,pd=matrix(pq,1);ck(pn==m['points'],'PQ points')
    ck(Path(str(ix)+'_pq_pivots.bin').is_file(),'PQ pivots missing')
    gn,gk=header(c['gt']);ck(gn==q and gk>=c['k'],'GT shape')
    ck(Path(c['gt']).stat().st_size==8+gn*gk*8,'GT IDs + distances required')
    with Path(c['gt']).open('rb') as f:
        f.seek(8);remaining=gn*gk
        while remaining:
            n=min(remaining,65536);ids=struct.unpack('<'+'I'*n,f.read(n*4));ck(max(ids)<m['points'],'GT ID range');remaining-=n
    if c.get('base'):
        bn,bd=matrix(c['base'],w);ck((bn,bd)==(m['points'],d),'base shape')
    paths=[Path(c[k]) for k in ('binary','query','gt')]+sorted(p for p in ix.parent.glob(ix.name+'*') if p.is_file())
    if c.get('base'):paths.append(Path(c['base']))
    return dict(**m,queries=q,gt_k=gk,data_type=c['data_type'],hashes={str(p.resolve()):digest(p) for p in paths})
def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);a=p.parse_args()
    print(json.dumps(audit(json.loads(a.config.read_text())),indent=2))
if __name__=='__main__':main()
