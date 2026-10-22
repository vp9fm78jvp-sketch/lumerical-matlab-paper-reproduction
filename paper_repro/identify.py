"""Bounded identification of explicitly uncertain physical parameters, with immutable baseline."""
from __future__ import annotations
import copy
import time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from .common import Blocked,write_json,read_json,digest,sha256,now
from .engine import run_worker
from .data import load_data
from .model import audit
from .consistency import material_hash


def identify(model,reference,column,root,backend='lumerical',max_evaluations=20,budget_seconds=600):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    params=[p for p in model['parameters'] if p.get('optimize')]
    if not params or not audit(model)['can_execute']:raise ValueError('Audited D parameters with bounds/rationale required')
    ref=load_data(reference,axis='x',required=['y']);rx,ry=ref['x'],ref['y']
    scale=max(float(np.ptp(ry)),float(np.sqrt(np.mean(ry**2))),1e-300)
    low=np.array([p['bounds'][0] for p in params]);high=np.array([p['bounds'][1] for p in params])
    if np.any(high<=low):raise ValueError('Strictly ordered bounds required')
    x0=(np.array([p['value'] for p in params])-low)/(high-low)
    # Never overwrite evidence from a prior identification experiment.
    if (root/'identification.json').exists():raise ValueError('Identification output already exists; use a new experiment directory')
    write_json(root/'baseline.model.json',model)
    deadline=time.monotonic()+budget_seconds;cache={};ledger=[];best=None
    identity={'training_reference_sha256':sha256(reference),'training_condition':model.get('condition_id',model['id']),
        'backend':backend,'parameters':[p['name'] for p in params],'bounds':[[p['bounds'][0],p['bounds'][1]] for p in params],
        'baseline_sha256':digest(model),'trials':ledger,'status':'RUNNING','heldout_validated':False}
    def residual(x):
        nonlocal best
        key=digest(x.tolist())
        if key in cache:return cache[key]
        if len(ledger)>=max_evaluations or time.monotonic()>=deadline:raise Blocked('Identification budget exhausted')
        index=len(ledger);folder=root/f'trial-{index:04}';folder.mkdir()
        variant=copy.deepcopy(model);values=low+x*(high-low)
        for p,value in zip(params,values):
            target=next(q for q in variant['parameters'] if q['name']==p['name'])
            target['value']=float(value)
        write_json(folder/'model.json',variant)
        trial={'index':index,'values':values.tolist(),'model_sha256':digest(variant),'status':'RUNNING'}
        ledger.append(trial);write_json(root/'identification.json',identity)
        try:
            receipt=run_worker(folder/'model.json',folder/'data.mat',backend,min(600,deadline-time.monotonic()))
            data=load_data(folder/'data.mat',required=[column])
            if data['t'][0]>rx[0] or data['t'][-1]<rx[-1]:raise ValueError('Reference interval not covered')
            r=(np.interp(rx,data['t'],data[column])-ry)/scale
            cost=float(np.mean(r*r));trial.update(status='COMPLETED',cost=cost,run_id=receipt['run_id'])
            if best is None or cost<best[0]:best=(cost,variant,index)
        except Blocked:
            trial['status']='BLOCKED';raise
        except Exception as e:
            trial.update(status='FAILED',error=str(e));r=np.full_like(ry,1e6)
        cache[key]=r;write_json(root/'identification.json',identity);return r
    try:
        # First trial is the unmodified baseline. Finite-difference perturbations are part of budget.
        residual(x0)
        result=least_squares(residual,x0,bounds=(np.zeros(len(params)),np.ones(len(params))),
            diff_step=1e-3,max_nfev=max_evaluations,ftol=1e-5,xtol=1e-5,gtol=1e-5)
        identity['status']='COMPLETED';identity['optimizer_message']=result.message
    except Blocked as e:identity.update(status='BLOCKED',reason=str(e))
    if best:
        cost,variant,index=best
        write_json(root/'best-candidate.model.json',variant)
        identity.update(best_trial=index,best_cost=cost,best_parameter_sha256=material_hash(variant))
    write_json(root/'identification.json',identity)
    return identity
