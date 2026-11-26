import unittest
import numpy as np
from runtime_attribution import aggregate,compare,summarize,FIELDS
class Test(unittest.TestCase):
    def test_events(self):
        def e(k,q,o=0):return dict(event_type=k,offset=4096,length=4096,query_id=q,group_id=int(q==2),owner_query=o)
        a,c=aggregate([e('OWNER',0),e('PUBLISH',0),e('INFLIGHT_JOIN',1),e('INFLIGHT_JOIN',2),e('INFLIGHT_JOIN',0),e('READY_HIT',1),e('ADMIT',0),e('EVICT_CAPACITY',0)], [4096],{0:0,1:0,2:1})
        self.assertEqual(a[0].tolist(),[5,1,1,3,1,1,1,1,0,1,0])
    def test_quadrants(self):
        a=np.zeros((4,len(FIELDS)),dtype=int);a[:,0]=4;a[:,1]=2;a[:,2]=2
        b=a.copy();b[:,1]=[1,1,3,3];b[:,2]=[3,3,1,1]
        g,h,j,q=compare(a,b,np.array([1,-1,-1,1]))
        self.assertEqual(q.tolist(),[1,2,3,4]);self.assertEqual(g.tolist(),[1,1,-1,-1])
        self.assertEqual(summarize(q==4,np.array([1,-1,-1,1]),g,h,j)['read_gain'],-1)
    def test_zero(self):
        a=np.zeros((1,len(FIELDS)),dtype=int)
        self.assertEqual(compare(a,a,np.array([0]))[-1].tolist(),[3])
    def test_bad_count(self):
        a=np.zeros((1,len(FIELDS)),dtype=int);b=a.copy();b[0,0]=1
        with self.assertRaises(ValueError):compare(a,b,np.array([0]))
if __name__=='__main__':unittest.main()
