import unittest,tempfile,csv,json
from pathlib import Path
from validate_retention_capacity import *
from analyze_retention_capacity import derive
class TestCapacity(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(len(matrix('formal',3)),162)
        self.assertEqual(len(matrix('smoke',1)),18)
        self.assertEqual(len({tuple(c[k] for k in FIELDS) for c in matrix('formal',3)}),162)
    def test_row_and_receipt(self):
        c=next(c for c in matrix('smoke',1) if c['policy']=='cms')
        v=dict.fromkeys(COUNTS,0)
        v.update(observed=100,hits=100,reads=19900,admissions=100,rejects=19800,resident=100,ready_peak=409600,inflight_peak=4096,live_peak=413696,frequency_updates=20000,counter_bytes=int(c['meta_budget']),elapsed_ns=100)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);p=out/c['file']
            def save(v):
                with p.open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=FIELDS+COUNTS);w.writeheader();w.writerow(dict({k:c[k] for k in FIELDS},**v))
                p.with_suffix('.json').write_text(json.dumps({'case':c,'sha256':digest(p)}))
            save(v);validate_saved(out,c)
            for key,value in [('hits',101),('resident',101),('counter_bytes',0),('frequency_failures',1),('ready_peak',99999999),('elapsed_ns',0)]:
                save(dict(v,**{key:value}))
                with self.assertRaises(ValueError):validate_saved(out,c)
            save(v);p.write_text(p.read_text()+'\n')
            with self.assertRaises(ValueError):validate_saved(out,c)
    def test_metrics(self):
        rows=[]
        for p,h in [('lru',10),('exact',20),('cms',19)]:
            rows.append(dict(n='100',ops='100',skew='1',seed='42',policy=p,meta_budget='64' if p=='cms' else '0',hits=h,observed=50,counter_bytes=64 if p=='cms' else 0,elapsed_ns=100,admissions=10))
        x=derive(rows)[2];self.assertAlmostEqual(x['incremental_preservation'],.9)
        rows[1]['hits']=10;self.assertIsNone(derive(rows)[2]['incremental_preservation'])
if __name__=='__main__':unittest.main()
