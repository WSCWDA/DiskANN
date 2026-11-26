import unittest
from concurrent_integration import plan,POLICIES,prefix
from pathlib import Path
class Integration(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(len(set(plan(3))),30)
        self.assertEqual(len(set(POLICIES.values())),10)
        expected = ['000','100','010','001','110','101','011','111']
        for i,bits in enumerate(expected):
            with self.subTest(case=i):
                g,s,r=bits
                self.assertEqual(POLICIES[f'A{i}'],(
                    'similarity' if g=='1' else 'original',
                    'inflight' if s=='1' else 'off',
                    'cms_512k' if r=='1' else 'none'))
        self.assertEqual(POLICIES['R1'],('similarity','inflight','lru'))
        self.assertEqual(POLICIES['R2'],('similarity','inflight','exact'))
        for repeat in range(1,4):
            self.assertEqual({i for r,i in plan(3) if r==repeat},set(POLICIES))
    def test_prefix(self):
        self.assertEqual(str(prefix(Path('/tmp/x'),2,'A7')),'/tmp/x/2/A7/1_similarity_inflight_stats')
if __name__=='__main__':unittest.main()
