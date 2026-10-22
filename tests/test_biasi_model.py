"""Independent analytic matrix-exponential limit, not experimental Biasi validation."""
import copy
from pathlib import Path
import numpy as np
from scipy.linalg import expm
from paper_repro.common import read_json
from paper_repro.engine import simulate_python
from paper_repro.data import load_data
from paper_repro.model import audit,param_values


def test_biasi_linear_limit_matches_matrix_exponential(tmp_path):
    root=Path(__file__).resolve().parents[1]
    model=copy.deepcopy(read_json(root/'examples/biasi/candidate.model.json'))
    # Deliberately disable nonlinear effects only for this independently solvable control.
    for p in model['parameters']:
        if p['name'] in {'betaTPA','sigmaFCA','dndT','dndN'}:p['value']=0.
    model['time'].update(stop=5e-10,dt=5e-12)
    model['rtol']=1e-9;model['atol']=1e-11
    assert audit(model)['can_execute']
    values=param_values(model)
    loss=5*values['couplingRate']+values['lossIntrinsic']
    delta=values['omegaR']-values['omegaInput']
    beta12=values['beta12mag']*np.exp(1j*values['phase12'])
    beta21=values['beta21mag']*np.exp(1j*values['phase21'])
    jac=np.array([[1j*delta-loss/2,-beta21],[-beta12,1j*delta-loss/2]])
    forcing=np.array([0,1j*np.sqrt(values['couplingRate']*values['powerIn'])])
    steady=-np.linalg.solve(jac,forcing)
    simulate_python(model,tmp_path/'control.mat')
    d=load_data(tmp_path/'control.mat')
    fields=np.array([steady-expm(jac*t)@steady for t in d['t']])
    expected=np.sum(abs(fields)**2,axis=1)
    assert np.max(abs(d['out_energy']-expected))/expected.max()<1e-7
    transmission=abs(1+1j*np.sqrt(values['couplingRate']/values['powerIn'])*fields[:,1])**2
    assert np.max(abs(d['out_transmission']-transmission))<1e-7
