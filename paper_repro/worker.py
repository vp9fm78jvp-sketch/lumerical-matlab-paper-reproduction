import argparse
import sys
from .common import Blocked,read_json
from .engine import simulate_python,simulate_lumerical


def main():
    p=argparse.ArgumentParser()
    source=p.add_mutually_exclusive_group(required=True);source.add_argument('--model');source.add_argument('--script')
    p.add_argument('--output',required=True);p.add_argument('--contract');p.add_argument('--product',default='FDTD')
    p.add_argument('--backend',choices=['lumerical','python-reference'],default='lumerical')
    p.add_argument('--method',default='Radau');a=p.parse_args()
    try:
        if a.script:
            from .product import run_script
            if not a.contract:p.error('--script requires --contract')
            run_script(a.script,read_json(a.contract),a.output,a.product)
        else:
            model=read_json(a.model)
            if a.backend=='lumerical':simulate_lumerical(model,a.output)
            else:simulate_python(model,a.output,a.method)
    except Blocked as e:print(e,file=sys.stderr);return 20
    return 0

if __name__=='__main__':sys.exit(main())
