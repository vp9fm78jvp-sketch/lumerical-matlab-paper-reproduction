"""History-preserving scans; a point is a real solve from its predecessor state."""
from __future__ import annotations
import copy
import time
from pathlib import Path
from .common import read_json,write_json,digest,sha256,Blocked
from .data import verify_receipt,load_data
from .engine import run_worker
from .compare import dynamics


def sweep(model,parameter,values,root,backend='lumerical',reset_each=False,budget_seconds=600,initial_state=None):
    values=list(values)
    if not values:raise ValueError('Empty scan')
    if parameter not in {p['name'] for p in model['parameters'] if not p.get('expression')}:raise ValueError('Scan parameter missing or derived')
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    identity=digest({'model':model,'parameter':parameter,'values':values,'backend':backend,'reset_each':reset_each,'initial_state':initial_state})
    checkpoint=root/'sweep.json'
    state=read_json(checkpoint) if checkpoint.exists() else {'identity':identity,'points':[],'status':'PENDING'}
    if state['identity']!=identity:raise ValueError('Scan definition changed; use a new directory to preserve previous evidence')
    last=initial_state or [s['initial'] for s in model['states']]
    if len(last)!=len(model['states']):raise ValueError('Wrong initial state length')
    deadline=time.monotonic()+budget_seconds
    for i,value in enumerate(values):
        sub=root/f'point-{i:05}';sub.mkdir(exist_ok=True);output=sub/'data.mat'
        if i<len(state['points']):
            point=state['points'][i]
            receipt=verify_receipt(output)
            if point['sha256']!=sha256(output) or point['input_state_sha256']!=digest(last if not reset_each else [s['initial'] for s in model['states']]):
                raise ValueError('Scan checkpoint integrity or history mismatch')
            last=receipt['final_state'];continue
        if time.monotonic()>=deadline:
            state['status']='PENDING';state['reason']='Compute budget exhausted; resume identical scan'
            write_json(checkpoint,state);return state
        variant=copy.deepcopy(model)
        next(p for p in variant['parameters'] if p['name']==parameter)['value']=value
        if not reset_each:
            for s,v in zip(variant['states'],last):s['initial']=v
        init=[s['initial'] for s in variant['states']]
        write_json(sub/'model.json',variant)
        state.update(status='RUNNING',current=i);write_json(checkpoint,state)
        try:receipt=run_worker(sub/'model.json',output,backend,min(600,deadline-time.monotonic()))
        except Exception as e:
            state.update(status='BLOCKED' if isinstance(e,Blocked) else 'FAILED',reason=str(e));write_json(checkpoint,state)
            return state
        arrays=load_data(output)
        features={k:dynamics(arrays['t'],v) for k,v in arrays.items() if k!='t'}
        point={'index':i,'parameter_value':value,'output':str(output),'sha256':sha256(output),
            'run_id':receipt['run_id'],'model_sha256':receipt['model_sha256'],
            'input_state_sha256':digest(init),'final_state':receipt['final_state'],'features':features,'status':'COMPLETED'}
        state['points'].append(point);last=receipt['final_state'];write_json(checkpoint,state)
    state['status']='COMPLETED';state.pop('reason',None);write_json(checkpoint,state)
    return state
