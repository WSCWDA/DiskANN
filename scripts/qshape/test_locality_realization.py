import unittest
from locality_realization import region,stats,combine
import numpy as np
class Test(unittest.TestCase):
    def test_sharing(self):
        e=[(10,0,0,0,1,'OWNER'),(15,1,0,0,1,'INFLIGHT_JOIN'),(20,0,1,0,1,'PUBLISH')]
        z=region(e,{0:0,1:0},{0:0,1:1},30,False)
        self.assertEqual(z['join_remaining'],[5]);self.assertEqual(z['cross_gap'],[5])
    def test_retention(self):
        e=[(10,0,0,0,1,'OWNER'),(20,0,1,0,1,'PUBLISH'),(20,0,2,0,1,'ADMIT'),(25,1,0,0,1,'READY_HIT'),(30,1,1,0,1,'EVICT_CAPACITY'),(35,1,2,1,2,'OWNER'),(40,1,3,1,2,'PUBLISH'),(40,1,4,1,2,'REJECT')]
        z=region(e,{0:0,1:0},{0:0,1:1},50,True)
        self.assertEqual(z['residence_evicted'],[10]);self.assertEqual(z['evict_next'],[5]);self.assertEqual(z['unused_eviction'],[0])
    def test_tie(self):
        e=[(10,0,0,0,0,'BYPASS'),(10,1,0,0,0,'BYPASS')]
        z=region(e,{0:0,1:0},{0:0,1:1},20,False)
        self.assertEqual(z['cross_gap'],[]);self.assertEqual(z['timestamp_tie'],[2])
    def test_invalid(self):
        with self.assertRaises(ValueError):region([(10,0,0,0,1,'OWNER')],{0:0},{0:0},20,False)
    def test_censored(self):
        z=region([(1,0,0,0,1,'OWNER'),(2,0,1,0,1,'PUBLISH'),(2,0,2,0,1,'ADMIT')],{0:0},{0:0},10,True)
        self.assertEqual(z['residence_censored'],[8]);self.assertEqual(z['unused_eviction'],[])
    def test_stats(self):
        z=combine(np.array([stats([1,10001]),stats([])]),np.array([True,True]))
        self.assertEqual(z['samples'],2);self.assertEqual(z['le_10000'],1)
if __name__=='__main__':unittest.main()
