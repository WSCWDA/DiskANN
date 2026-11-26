import unittest,tempfile
from pathlib import Path
from grouping_characterization import *
class TestGrouping(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(len(set(plan(3))),24)
        for i,o in enumerate(('original','random','similarity','oracle')*2):
            self.assertEqual(POLICIES[f'Z{i}'],(o,'inflight','cms_512k' if i<4 else 'none'))
        for r in range(1,4):self.assertEqual({i for j,i in plan(3) if j==r},set(POLICIES))
    def test_permutation(self):
        rows=[dict(query_id=0,execution_id=1,group_id=0),dict(query_id=1,execution_id=0,group_id=0)]
        self.assertEqual(permutation(rows,2),[1,0])
        for k,v in [('query_id',1),('execution_id',0),('group_id',1)]:
            bad=[dict(x) for x in rows];bad[0][k]=v
            with self.assertRaises(ValueError):permutation(bad,2)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'order';p.write_text(order_text([1,0]));self.assertEqual(load_order(p,2),[1,0])
            for s in ('1 1','0','0 1 2','0 -1'):
                p.write_text(s)
                with self.assertRaises(ValueError):load_order(p,2)
    def test_command(self):
        c=dict(inputs={k:k for k in ('SEARCH_BIN','INDEX_PREFIX','QUERY_FILE','GT_FILE')},data_type='float')
        for i in POLICIES:
            a=command(c,Path('/tmp/search'),i,Path('/tmp/order'))
            self.assertEqual(a[a.index('--data_type')+1],'float')
            self.assertEqual('--qshape-oracle-file' in a,i in ('Z3','Z7'))
            self.assertEqual(a[a.index('--qshape-retention')+1],'frequency' if int(i[1])<4 else 'none')
    def test_paired(self):
        rows=[dict(case=f'Z{i}',repeat=1,e2e_qps=100+i%4*10,search_qps=100+i%4*10,submitted_reads=100-i%4,grouping_ms=4-i%4,grouping_ns=(4-i%4)*1000000,search_ns=10000000,e2e_ns=15000000) for i in range(8)]
        p=paired(rows,1);self.assertEqual(len(p),2);self.assertAlmostEqual(p[0]['precomputed_gain'],.3);self.assertEqual(p[0]['full_precomputed_ms'],17)
if __name__=='__main__':unittest.main()
