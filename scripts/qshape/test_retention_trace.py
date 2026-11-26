import unittest,tempfile,csv
from pathlib import Path
from retention_trace import extract,fingerprint,cases
class TestTrace(unittest.TestCase):
    def test_extract(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace'
            def put(s,content):Path(str(p)+s).write_text(content)
            put('_queries.csv','query_id,reader_requests\n0,2\n')
            put('_region_meta.csv','query_id,events,dropped\n0,3,0\n')
            put('_regions.csv','query_id,sequence,offset,length,timestamp_ns,event_type\n0,1,8192,4096,20,READY_HIT\n0,0,4096,4096,10,OWNER\n0,2,4096,4096,30,PUBLISH\n')
            self.assertEqual(extract(p)[0],[1,2])
            put('_region_meta.csv','query_id,events,dropped\n0,3,1\n')
            with self.assertRaises(ValueError):extract(p)
    def test_matrix(self):
        self.assertEqual(len(list(cases(3,'perf'))),18)
        self.assertNotEqual(fingerprint([1,2]),fingerprint([2,1]))
if __name__=='__main__':unittest.main()
