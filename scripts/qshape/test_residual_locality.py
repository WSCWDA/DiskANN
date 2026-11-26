import unittest,tempfile,csv,hashlib,struct
from pathlib import Path
import numpy as np
from residual_locality import analyze,contributions,rank_regions
from analyze_region_frequency import bands
from extract_query_regions import extract_events
class Test(unittest.TestCase):
    def test_overlap(self):
        ptr=np.array([0,2,4,6,8]);ids=np.array([0,1,0,2,1,3,2,3])
        f,d,g=contributions(ptr,ids,[0,1,2,3],4,2)
        self.assertEqual(d.tolist(),[1,0,0,1])
        self.assertEqual(sum(x[-1] for x in g),2)
        orders=dict(original=[0,1,2,3],random=[0,3,1,2],similarity=[0,2,1,3])
        rows,gains,f,ds,gs,rank=analyze(ptr,ids,orders,4,2)
        self.assertEqual(len(rows),21)
        self.assertEqual([x['raw'] for x in rows[::7]],[2,0,2])
        self.assertTrue(all(x['residual']==0 for x in rows if x['budget_mib']))
        self.assertEqual(sum(x['delta_similarity'] for x in bands(f,ds,rank)),0)
    def test_ties(self):
        self.assertEqual(rank_regions(np.array([2,3,3,1])).tolist(),[1,2,0,3])
    def test_partial_group(self):
        f,d,g=contributions(np.arange(4),np.array([0,0,0]),[0,1,2],1,2)
        self.assertEqual(d.tolist(),[1]);self.assertEqual(g[-1][1],1)
    def test_extract(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'trace.csv'
            p.write_text('query_id,offset,length,event_type\n0,4096,4096,OWNER\n0,4096,4096,PUBLISH\n0,4096,4096,READY_HIT\n1,8192,4096,OWNER\n')
            q=[dict(query_id=0,reader_requests=2),dict(query_id=1,reader_requests=1)]
            s,h,n=extract_events(p,q)
            self.assertEqual(n,3);self.assertEqual(s[0].tolist(),[4096])
            self.assertEqual(h,hashlib.sha256(struct.pack('<QQQQQQQQQQ',0,2,4096,4096,4096,4096,1,1,8192,4096)).hexdigest())
            q[0]['reader_requests']=1
            with self.assertRaises(ValueError):extract_events(p,q)
if __name__=='__main__':unittest.main()
