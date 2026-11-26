import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/qshape'))
from validate_frequency_capacity import validate_query,compare,quantile
class Tests(unittest.TestCase):
 def test_query(self):
    keys='reader_requests submitted_reads shared_hits reader_bytes submitted_bytes shared_bytes completed_reads completion_errors ready_hits ready_hit_bytes peak_ready_bytes peak_inflight_bytes peak_shared_bytes frequency_updates frequency_update_failures frequency_gate_checks frequency_gate_accepts frequency_gate_rejects frequency_saturations frequency_counter_bytes frequency_shard_entries ready_admissions ready_rejects bypass ready_ttl_evictions ready_capacity_evictions arrival_ns search_start_ns search_end_ns'.split()
    q=dict.fromkeys(keys,0)
    q.update(reader_requests=1,submitted_reads=1,completed_reads=1,reader_bytes=4096,submitted_bytes=4096,frequency_updates=1,frequency_counter_bytes=65536,ready_admissions=1)
    validate_query(q,'cms_64k',65536)
    for k in ('frequency_shard_entries','completion_errors','frequency_saturations','shared_hits','frequency_update_failures'):
        bad=dict(q);bad[k]=1
        with self.assertRaises(ValueError):validate_query(bad,'cms_64k',65536)
 def test_targets(self):
    e=dict(e2e_qps=100,submitted_reads=100,p999_us=100,ready_admissions=1)
    l=dict(ready_admissions=100)
    self.assertTrue(compare(e,e,l)['meets_targets'])
    self.assertFalse(compare(dict(e,e2e_qps=97),e,l)['meets_targets'])
    self.assertEqual(quantile([1,2,3,4],.99),4)
if __name__=='__main__':unittest.main()
