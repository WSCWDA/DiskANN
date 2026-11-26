import argparse
from pathlib import Path
import grouping_characterization as a1
from validate_frequency_capacity import read
from locality_realization import require,LIMITS
def validate(out):
    m=read(out/'matrix.csv')
    expected={(s,str(r),'D'+str(i),'') for r in range(1,4) for s,ids in [('A',range(6)),('B',range(3,6))] for i in ids}
    expected|={('C',str(r),'D'+str(b+j),'D'+str(b)) for r in range(1,4) for b in (0,3) for j in (1,2)}
    require(len(m)==39 and {(x['stage'],x['repeat'],x['case'],x['base']) for x in m}==expected and all(x['status']=='PASS' for x in m),'matrix')
    for name,n in [('temporal',720),('retention',360),('joint',5760)]:
        rows=read(out/(name+'.csv'))
        # Joint: 6 off pairs * 20 strata * 2 sides * 8 metrics + 6 on * 20 * 2 * 16.
        require(len(rows)==n,'row count '+name)
        for x in rows+read(out/(name+'_sensitivity.csv')):
            n=int(x['samples']);t=int(x['total']);require(n>=0 and t>=0,'negative')
            require((not x['mean'] and n==0 and t==0) or (n>0 and abs(float(x['mean'])-t/n)<=1e-6*max(1,t/n)),'mean')
            c=[int(x['le_'+str(k)]) for k in LIMITS if x['le_'+str(k)]!='']
            require(c==sorted(c) and all(0<=v<=n for v in c),'CDF')
    a1.atomic_json(out/'validation_summary.json',dict(status='PASS',analyses=39,files={p.name:a1.digest(p) for p in out.glob('*.csv')}))
    print('PASS 39/39 analyses')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);validate(p.parse_args().out)
