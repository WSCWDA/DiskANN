import argparse
from pathlib import Path
from grouping_characterization import validate
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);validate(p.parse_args().out.resolve())
