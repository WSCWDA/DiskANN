import unittest,math
from final_factorial import plan,effects,POLICIES,prefix
from pathlib import Path
class Tests(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(len(plan('smoke')),10)
        self.assertEqual(len(plan('core')),50)
        self.assertEqual(len(plan('sensitivity')),170)
        a=plan('core')+plan('sensitivity')
        self.assertEqual(len(set(a)),220)
    def test_no_redundancy(self):
        for r,t,b,i in plan('core')+plan('sensitivity'):
            if POLICIES[i][2]=='none':self.assertEqual(b,16)
    def test_factors(self):
        z={('A0','A1','A2','A4','A3','A5','A6','A7')[j]:{'e2e_qps':2**(j&1)*3**((j>>1)&1)*5**((j>>2)&1)} for j in range(8)}
        e=effects(z)
        for k,n in [('G',2),('S',3),('R',5)]:self.assertAlmostEqual(e['effect_'+k],math.log(n))
        for k in ('GS','GR','SR','GSR'):self.assertAlmostEqual(e['effect_'+k],0)
    def test_paths(self):
        a=plan('core')+plan('sensitivity')
        self.assertEqual(len({prefix(Path('/tmp'),c) for c in a}),220)
    def test_reproducible(self):self.assertEqual(plan('sensitivity'),plan('sensitivity'))
if __name__=='__main__':unittest.main()
