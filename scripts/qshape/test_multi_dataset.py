import unittest, tempfile, struct
from pathlib import Path
from audit_dataset import matrix, layout
from multi_dataset_eval import plan
from validate_multi_dataset import run_files
class Tests(unittest.TestCase):
    def test_matrix(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'q';p.write_bytes(struct.pack('<II',2,3)+bytes(24));self.assertEqual(matrix(p,4),(2,3))
            with self.assertRaises(ValueError):matrix(p,1)
    def test_layout(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'idx';p.write_bytes(struct.pack('<II8Q',8,1,7,128,0,644,6,0,0,0).ljust(12288,b'\0'));self.assertEqual(layout(p)['nodes_per_sector'],6)
    def test_multisector(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'idx';p.write_bytes(struct.pack('<II8Q',8,1,2,2048,0,9000,0,0,0,0).ljust(28672,b'\0'));self.assertEqual(layout(p)['region_bytes'],12288)
    def test_plan(self):
        c=dict(repeats=3,policies=['A0','A7']);self.assertEqual(len(set(plan(c))),6);self.assertEqual(plan(c),plan(c))
    def test_missing_baseline(self):
        with self.assertRaises(ValueError):plan(dict(repeats=1,policies=['A7']))
    def test_paths(self):
        self.assertTrue(str(run_files(Path('x'),150)[1]).endswith('_L150_run0_queries.csv'))
if __name__=='__main__':unittest.main()
