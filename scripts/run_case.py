#!/usr/bin/env python3
"""Reproducible case driver; backend identity and blockers are always retained."""
from __future__ import annotations
import argparse
import copy
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paper_repro.common import read_json,write_json,Blocked
from paper_repro.compiler import compile_lsf
from paper_repro.engine import run_worker
from paper_repro.compare import dynamics
from paper_repro.data import load_data
from paper_repro.environment import detect
from paper_repro.sweep import sweep


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case',choices=['minimal','xiang','biasi'])
    p.add_argument('--out',required=True);p.add_argument('--backend',choices=['lumerical','python-reference'],default='lumerical')
    p.add_argument('--budget',type=float,default=600);args=p.parse_args()
    if args.budget<=0:p.error('budget must be positive')
    root=Path(__file__).resolve().parents[1];out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    write_json(out/'environment.json',detect(out));deadline=time.monotonic()+args.budget
    model_paths=[root/'examples/minimal/model.json'] if args.case=='minimal' else [root/f'examples/{args.case}/candidate.model.json']
    if args.case=='xiang':model_paths.append(root/'examples/xiang/eq10-literal-sign-with-si.model.json')
    results=[]
    for source in model_paths:
        model=read_json(source);folder=out/model['id'];folder.mkdir(exist_ok=True)
        model_file=folder/'model.json'
        if model_file.exists() and read_json(model_file)!=model:raise ValueError('Existing case model differs; preserve it and select a new output directory')
        write_json(model_file,model)
        (folder/'simulation.lsf').write_text(compile_lsf(model,folder/'data.mat'),encoding='utf-8')
        try:
            if args.case=='biasi':
                if args.backend=='python-reference':
                    # Adaptive Python internal integration is separate from output sampling.
                    model=copy.deepcopy(model);model['time']['dt']=5e-10
                    write_json(folder/'python-output-grid.model.json',model)
                forward=read_json(root/'examples/biasi/forward.json')
                f=sweep(model,forward['parameter'],forward['values'],folder/'forward',args.backend,False,max(.01,deadline-time.monotonic()))
                entry={'status':f['status'],'forward_points':len(f['points']),'backend':args.backend}
                if f['status']=='COMPLETED':
                    reverse=read_json(root/'examples/biasi/reverse.json')
                    r=sweep(model,reverse['parameter'],reverse['values'],folder/'reverse',args.backend,False,max(.01,deadline-time.monotonic()),f['points'][-1]['final_state'])
                    entry.update(status=r['status'],reverse_points=len(r['points']))
                results.append(entry);continue
            data=folder/'data.mat'
            receipt=run_worker(model_file,data,args.backend,max(.01,deadline-time.monotonic()))
            write_json(data.with_suffix('.model.json'),model)
            arrays=load_data(data);features={k:dynamics(arrays['t'],v) for k,v in arrays.items() if k!='t'}
            entry={'model':model['id'],'status':'COMPLETED','backend':receipt['engine'],'run_id':receipt['run_id'],
                'scientific_grade':'D','reason':'No complete paper-reference/convergence/physical/heldout validation','diagnostics':features}
            if args.case=='minimal':
                import numpy as np
                error=float(np.max(abs(arrays['out_real_field']-.5*(1-np.exp(-2*arrays['t'])))))
                entry['analytic_max_abs_error']=error
                if error>1e-6:raise ValueError('Analytic regression failed')
            results.append(entry)
        except Exception as e:results.append({'model':model['id'],'status':'BLOCKED' if isinstance(e,Blocked) else 'FAILED','reason':str(e),'scientific_grade':'D'})
    summary={'case':args.case,'results':results,'commercial_results_verified':False}
    write_json(out/'case-result.json',summary);print(__import__('json').dumps(summary,indent=2))
    return 20 if any(r['status']=='BLOCKED' for r in results) else 1 if any(r['status']=='FAILED' for r in results) else 0

if __name__=='__main__':raise SystemExit(main())
