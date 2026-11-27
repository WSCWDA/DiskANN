import unittest
from dual_timescale import *
from run_dual_timescale import plan
class Test(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(len(set(plan(3))),48)
    def test_hit(self):
        for p in POLICIES:
            m=Replay(p);m.access(4096);m.access(4096);d=m.result();validate(d,p);self.assertEqual(d['hits'],1)
    def test_capacity(self):
        keys=[i*4096 for i in range(20000) if slots(i*4096)[0]==0][:150]
        self.assertEqual(len(keys),150)
        for p in POLICIES:
            m=Replay(p)
            for k in keys:m.access(k)
            validate(m.result(),p);self.assertLessEqual(m.result()['window_resident']+m.result()['main_resident'],64)
    def test_strict_gate(self):
        m=Replay('R1');d=OrderedDict((i,False) for i in range(64));m.estimate=lambda k:1
        self.assertFalse(m.admit(d,100));self.assertEqual(len(d),64)
    def test_promotion(self):
        m=Replay('R2');keys=[i*4096 for i in range(2000) if slots(i*4096)[0]==0][:5]
        for k in keys:m.access(k)
        self.assertEqual(m.result()['promotions'],1);validate(m.result(),'R2')
    def test_ghost(self):
        m=Replay('R6');m.access(0);self.assertEqual(m.result()['window_inserts'],0)
        self.assertEqual(m.result()['ghost_bytes'],524288)
    def test_hash(self):
        self.assertEqual(mix(0),0)
        for k in (0,4096,8192):
            s,ix=slots(k);self.assertTrue(all(s*2048<=i<(s+1)*2048 for i in ix))
if __name__=='__main__':unittest.main()
