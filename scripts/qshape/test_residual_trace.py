import unittest
from pathlib import Path
from run_residual_locality import plan,MAP,command
from validate_residual_locality import validate_events
class TraceTest(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(len(set(plan(3))),18)
        self.assertEqual(list(MAP.values()),['Z4','Z5','Z7','Z0','Z1','Z3'])
        c=dict(inputs={k:k for k in ('SEARCH_BIN','INDEX_PREFIX','QUERY_FILE','GT_FILE')},data_type='float')
        for i in MAP:
            a=command(c,Path('/tmp/search'),i,Path('/tmp/order'))
            self.assertEqual(a[a.index('--qshape-region-trace')+1],'1')
            self.assertEqual('--qshape-oracle-file' in a,i in ('D2','D5'))
    def fixture(self,active):
        kinds=['OWNER','PUBLISH']+(['ADMIT','READY_HIT'] if active else [])
        e=[dict(query_id=0,group_id=0,sequence=i,owner_query=0,lifecycle=1,timestamp_ns=i+1,offset=4096,length=4096,event_type=k) for i,k in enumerate(kinds)]
        q=[dict(query_id=0,group_id=0,reader_requests=1+int(active),reader_bytes=4096*(1+int(active)),submitted_reads=1,completed_reads=1,ready_hits=int(active),shared_hits=int(active),ready_admissions=int(active),ready_rejects=0,ready_capacity_evictions=0,ready_ttl_evictions=0,ready_unused_evictions=0)]
        return e,q,[dict(query_id=0,events=len(e),dropped=0)]
    def test_lifecycle(self):
        for active in (False,True):
            e,q,m=self.fixture(active);self.assertEqual(validate_events(e,q,m,active)['resident_regions'],int(active))
            with self.assertRaises(ValueError):validate_events(e,q,m,not active)
    def test_dropped(self):
        e,q,m=self.fixture(False);m[0]['dropped']=1
        with self.assertRaises(ValueError):validate_events(e,q,m,False)
    def test_duplicate(self):
        e,q,m=self.fixture(False);e.append(e[0])
        with self.assertRaises(ValueError):validate_events(e,q,m,False)
if __name__=='__main__':unittest.main()
