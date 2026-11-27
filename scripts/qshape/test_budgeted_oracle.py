import unittest
from budgeted_oracle import *
from dual_timescale import Replay
from run_budgeted_oracle import plan
class Tests(unittest.TestCase):
    def test_matrix(self):self.assertEqual(len(set(plan(3))),36)
    def test_utility(self):
        p=future_index([0,1,0,0,1])
        self.assertEqual(utility(p,0,0,2),1)
        self.assertEqual(utility(p,0,0,3),2)
        self.assertEqual(utility(p,2,0,3),0)
    def test_baseline(self):
        ids=[i*4096 for i in range(10000)]*2
        a=Replay('R1');b=Oracle('O0',len(ids),future_index(ids))
        for k in ids:a.access(k);b.access(k)
        d=b.result();validate(d,'O0')
        for k,v in a.result().items():self.assertEqual(v,d[k])
    def test_budget(self):
        a=Oracle('O1',1000,{100:[1,2]})
        a.estimate=lambda k:1
        d=a.main[0];d.update((i,False) for i in range(64));a.c['ops']=1
        self.assertTrue(a.admit(d,100))
        self.assertFalse(a.admit(d,101))
        self.assertEqual(a.c['exceptions'],1)
    def test_tie(self):
        a=Oracle('O5',1000,{100:[1],0:[1]})
        a.estimate=lambda k:1
        d=a.main[0];d.update((i,False) for i in range(64));a.c['ops']=1
        self.assertFalse(a.admit(d,100))
        self.assertEqual(a.c['utility_denials'],1)
    def test_all(self):
        ids=[i*4096 for i in range(10000)]*2
        p=future_index(ids)
        for policy in BPS:
            a=Oracle(policy,len(ids),p)
            for k in ids:a.access(k)
            validate(a.result(),policy)
    def test_normal_admit(self):
        a=Oracle('O0',1,{})
        a.access(0)
        self.assertEqual(a.result()['main_inserts'],1)
        self.assertEqual(a.result()['exceptions'],0)
if __name__=='__main__':unittest.main()
