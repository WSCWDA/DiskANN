import unittest
from concurrent_integration import plan,POLICIES,prefix
from pathlib import Path
class Integration(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(len(set(plan(3))),30)
        self.assertEqual(len(set(POLICIES.values())),10)
        self.assertEqual(POLICIES['A6'],('original','inflight','cms_512k'))
        self.assertEqual(POLICIES['A3'],('original','off','cms_512k'))
    def test_prefix(self):
        self.assertEqual(str(prefix(Path('/tmp/x'),2,'A7')),'/tmp/x/2/A7/1_similarity_inflight_stats')
if __name__=='__main__':unittest.main()
