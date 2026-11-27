import unittest, math
from merge_final_factorial import *
def fixture():
    rows=[]
    for c in plan('core')+plan('sensitivity'):
        r,t,b,i=key(c)
        rows.append(dict(repeat=r,threads=t,ready_mib=b,case=i,source_stage='core' if t==64 and (b==16 or b==0) else 'sensitivity',ids_sha256='a',dists_sha256='b',recall=99.57,reader_requests=100,reader_bytes=409600,submitted_reads=80,submitted_bytes=327680,inflight_hits=10,ready_hits=10,e2e_qps=1000,search_qps=1000,search_ms=10,e2e_ms=10,grouping_ms=0))
    return rows
class Tests(unittest.TestCase):
    def test_complete_matrix(self):self.assertEqual([len(x) for x in analyze(fixture()).values()],[220,44,30,72,42,6])
    def test_duplicate_rejection(self):
        a=fixture()
        with self.assertRaises(ValueError):analyze(a+[a[0]])
    def test_manifest_mismatch(self):
        with self.assertRaises(ValueError):compatible(dict(commit='a',hashes='a'),dict(commit='a',hashes='b'))
    def test_baseline_reuse(self):
        z=index(fixture(),[key(c) for c in plan('core')+plan('sensitivity')])
        self.assertIs(block(z,1,64,4)['A0'],block(z,1,64,64)['A0'])
        self.assertIsNot(block(z,1,16,4)['A0'],block(z,1,64,4)['A0'])
    def test_missing_baseline(self):
        with self.assertRaises(ValueError):analyze(fixture()[1:])
    def test_factor_mapping(self):
        z={i:dict(e2e_qps=2**(j&1)*3**((j>>1)&1)*5**((j>>2)&1)) for j,i in enumerate(('A0','A1','A2','A4','A3','A5','A6','A7'))}
        e=effects(z)
        for k,n in [('G',2),('S',3),('R',5)]:self.assertAlmostEqual(e['effect_'+k],math.log(n))
        for k in ('GS','GR','SR','GSR'):self.assertAlmostEqual(e['effect_'+k],0)
    def test_io_conservation(self):
        a=fixture();a[0]['submitted_reads']+=1
        with self.assertRaises(ValueError):analyze(a)
    def test_break_even(self):
        a,b=fixture()[:2];a.update(search_ms=8,e2e_ms=11,grouping_ms=3)
        d=attribution(a,b);self.assertEqual((d['search_saved_ms'],d['extra_grouping_ms'],d['net_saved_ms']),(2,3,-1))
    def test_confidence_interval(self):
        d=stats([1]*5);self.assertEqual((d['mean'],d['ci_low'],d['ci_high'],d['positive']),(1,1,1,5))
if __name__=='__main__':unittest.main()
