"""Resumable, serial B1 runner. Do not run two instances in one output directory."""
import argparse,csv,json,subprocess,os,fcntl
from pathlib import Path
from validate_retention_capacity import matrix,validate_row,validate_saved,validate,digest,FIELDS,check

def atomic(p,s):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(s);os.replace(tmp,p)
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--bench',type=Path,required=True)
    p.add_argument('--profile',choices=['smoke','pilot','formal'],default='smoke');p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--timeout',type=int,default=900);p.add_argument('--retries',type=int,default=1);a=p.parse_args()
    check(a.timeout>0 and a.retries>=0,'timeout/retries')
    check(a.profile!='formal' or a.repeats>=3,'formal repeats')
    bench=a.bench.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    with (out/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        repo=Path(__file__).resolve().parents[2]
        git=lambda *args:subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
        config=dict(profile=a.profile,repeats=a.repeats,commit=git('rev-parse','HEAD'),tracked_dirty=git('status','--porcelain','--untracked-files=no'),bench_sha256=digest(bench))
        cases=matrix(a.profile,a.repeats)
        cp=out/'config.json';mp=out/'manifest.csv'
        if cp.exists():check(json.loads(cp.read_text())==config,'resume configuration/binary mismatch')
        else:atomic(cp,json.dumps(config,indent=2))
        if mp.exists():
            from validate_retention_capacity import read_csv
            check(read_csv(mp)==cases,'resume matrix mismatch')
        else:
            import io
            buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=['file']+FIELDS);w.writeheader();w.writerows(cases);atomic(mp,buf.getvalue())
        (out/'complete').unlink(missing_ok=True)
        for c in cases:
            dest=out/c['file'];receipt=dest.with_suffix('.json')
            try:
                validate_saved(out,c);print('SKIP',c['file'],flush=True);continue
            except (OSError,ValueError,KeyError,TypeError):pass
            receipt.unlink(missing_ok=True)
            for attempt in range(a.retries+1):
                tmp=dest.with_suffix('.partial')
                try:
                    with tmp.open('w') as f,(out/(c['file']+f'.attempt{attempt}.log')).open('a') as err:
                        subprocess.run([str(bench),*[c[k] for k in FIELDS]],stdout=f,stderr=err,timeout=a.timeout,check=True)
                    validate_row(tmp,c)
                    os.replace(tmp,dest);atomic(receipt,json.dumps({'case':c,'sha256':digest(dest)}))
                    print('DONE',c['file'],flush=True);break
                except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:
                    with (out/'failures.log').open('a') as f:f.write(f'{c["file"]} attempt={attempt} {exc}\n')
                    if attempt==a.retries:raise
        atomic(out/'complete',str(len(cases)))
        try:validate(out)
        except Exception:
            (out/'complete').unlink(missing_ok=True);raise
        print(f'PASS {len(cases)}/{len(cases)}')
if __name__=='__main__':main()
