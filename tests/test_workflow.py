import copy
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.io import savemat
from paper_repro.cli import prepare
from paper_repro.common import write_json,read_json,Blocked
from paper_repro.data import load_data,verify_receipt
from paper_repro.engine import simulate_python,run_worker
from paper_repro.scheduler import Scheduler,check_plan
from paper_repro.validation import grade,convergence
from paper_repro.sweep import sweep
from paper_repro.product import validate_dataset
from paper_repro.plotting import plot_matlab


def test_analytic_ode_and_provenance(model,tmp_path):
    out=tmp_path/'data.mat';receipt=simulate_python(model,out)
    data=load_data(out);expected=.5*(1-np.exp(-2*data['t']))
    assert np.max(abs(data['out_real_field']-expected))<1e-8
    assert not receipt['commercial_solver_executed']
    assert grade(model,out,{'nrmse_range':0},{'nrmse_range':.01})['grade']=='D'
    with out.open('ab') as f:f.write(b'tampered')
    with pytest.raises(ValueError):verify_receipt(out)


def test_pdf_to_manifest_report(sample_pdf,tmp_path):
    out=tmp_path/'project';r=prepare(sample_pdf,out)
    assert r['figures']==2
    assert (out/'REPORT.md').is_file()
    assert read_json(out/'manifest.json')['panel_count']==3
    assert read_json(out/'report.json')['results'][0]['grade']=='D'
    with pytest.raises(ValueError):prepare(sample_pdf,out)


def test_scheduler_cache_resume_and_invalidation(model,tmp_path):
    write_json(tmp_path/'model.json',model)
    plan={'tasks':[{'id':'a','kind':'simulate','model':'model.json','output':'data/a.mat','backend':'python-reference','timeout':30}]}
    s=Scheduler(tmp_path);s.sync(plan);assert s.run(30)[0]['status']=='COMPLETED'
    run_id=verify_receipt(tmp_path/'data/a.mat')['run_id']
    s.sync(plan);assert s.run(30)[0]['attempts']==1
    assert verify_receipt(tmp_path/'data/a.mat')['run_id']==run_id
    (tmp_path/'data/a.mat').unlink();s.sync(plan);assert s.rows()[0]['status']=='PENDING'
    # Interrupted RUNNING lease recovers without destroying completed artifacts.
    with s.connect() as c:c.execute('UPDATE tasks SET status="RUNNING",lease=0,owner="dead"')
    s.recover();assert s.rows()[0]['status']=='PENDING'
    model['parameters'][0]['value']=3;write_json(tmp_path/'model.json',model);s.sync(plan)
    assert s.run(30)[0]['status']=='COMPLETED'
    assert verify_receipt(tmp_path/'data/a.mat')['run_id']!=run_id


def test_dependency_cycle_blocker_and_budget(model,tmp_path,monkeypatch):
    with pytest.raises(ValueError):check_plan({'tasks':[{'id':'a','dependencies':['b']},{'id':'b','dependencies':['a']}]})
    write_json(tmp_path/'model.json',model)
    plan={'tasks':[{'id':'a','kind':'simulate','model':'model.json','output':'a.mat'},
                   {'id':'b','kind':'simulate','model':'model.json','output':'b.mat','dependencies':['a']}]}
    s=Scheduler(tmp_path);s.sync(plan)
    monkeypatch.setattr(s,'_execute',lambda *args: (_ for _ in ()).throw(Blocked('License missing fixture')))
    rows=s.run(2);assert {r['status'] for r in rows}=={'BLOCKED'}
    assert not (tmp_path/'a.mat').exists()
    with pytest.raises(ValueError):s.run(0)


def test_history_sweep_really_integrates(model,tmp_path):
    m=copy.deepcopy(model);m['id']='synthetic-memory';m['time']={'stop':.2,'dt':.01}
    forward=sweep(m,'drive',[1.,2.,3.],tmp_path/'fwd','python-reference',budget_seconds=60)
    assert forward['status']=='COMPLETED'
    states=[p['final_state'][0] for p in forward['points']]
    assert states[0]<states[1]<states[2]
    assert len({p['run_id'] for p in forward['points']})==3
    reverse=sweep(m,'drive',[3.,2.,1.],tmp_path/'rev','python-reference',budget_seconds=60,initial_state=forward['points'][-1]['final_state'])
    assert reverse['status']=='COMPLETED'
    assert reverse['points'][-1]['final_state'][0]!=pytest.approx(states[0])
    again=sweep(m,'drive',[1.,2.,3.],tmp_path/'fwd','python-reference',budget_seconds=30)
    assert [p['run_id'] for p in again['points']]==[p['run_id'] for p in forward['points']]


def test_dataset_contract_nd(tmp_path):
    file=tmp_path/'field.mat';savemat(file,{'x':np.arange(3),'y':np.arange(4),'temperature':np.ones((3,4))})
    cfg={'variables':{'x':{'unit':'m','axis':True},'y':{'unit':'m','axis':True},'temperature':{'unit':'K','axes':['x','y']}}}
    assert validate_dataset(file,cfg)['temperature'].shape==(3,4)
    cfg['variables']['temperature']['shape']=[4,3]
    with pytest.raises(ValueError):validate_dataset(file,cfg)


def test_plotting_contract_mock_only(model,tmp_path,monkeypatch):
    from PIL import Image
    import paper_repro.plotting as module
    data=tmp_path/'data.mat';simulate_python(model,data)
    cfg={'output_dir':str(tmp_path/'plots'),'figures':[{'id':'test','data':str(data),'panels':[{
        'columns':['out_energy'],'x_factor':1,'y_factor':1,'xlabel':'t (s)','ylabel':'U (J)'}]}]}
    monkeypatch.setattr(module,'detect',lambda out:{'matlab':'CONTRACT_FIXTURE_NOT_MATLAB'})
    def fake_run(*args,**kw):
        out=Path(cfg['output_dir']);out.mkdir(exist_ok=True)
        Image.new('RGB',(250,150),'white').save(out/'test.png')
        for ext in ['pdf','svg','fig']:(out/f'test.{ext}').write_bytes(b'fixture, not MATLAB output\n'*20)
        return SimpleNamespace(returncode=0,stdout='fixture',stderr='')
    monkeypatch.setattr(module.subprocess,'run',fake_run)
    receipt=plot_matlab(cfg,tmp_path/'plots.json')
    assert len(receipt['outputs'])==4


def test_convergence_requires_independent_and_bound_models(model,tmp_path):
    files=[]
    for i,(factor,method) in enumerate([(1,'Radau'),(.5,'Radau'),(.5,'DOP853')]):
        m=copy.deepcopy(model);m['time']['dt']*=factor
        f=tmp_path/f'd{i}.mat';simulate_python(m,f,method);write_json(f.with_suffix('.model.json'),m);files.append(f)
    r=convergence(model,*files,tmp_path/'convergence.json',{'out_energy':.001,'out_real_field':.001})
    assert r['passed']
    with pytest.raises(ValueError):convergence(model,files[0],files[1],files[1],tmp_path/'bad.json',{'out_energy':1})


def test_scheduler_invalidates_dependent_after_output_loss(model,tmp_path):
    write_json(tmp_path/'model.json',model)
    s=Scheduler(tmp_path)
    plan={'tasks':[{'id':'a','kind':'simulate','model':'model.json','output':'a.mat','backend':'python-reference'},
        {'id':'b','kind':'simulate','model':'model.json','output':'b.mat','backend':'python-reference','dependencies':['a']}]}
    s.sync(plan)
    # A completed dependency's bytes disappear, but the descendant artifact still exists.
    with s.connect() as c:
        c.execute('UPDATE tasks SET status="COMPLETED",artifacts=? WHERE id="a"',('{"a.mat":"missing-hash"}',))
        c.execute('UPDATE tasks SET status="COMPLETED" WHERE id="b"')
    s.sync(plan)
    assert {r['status'] for r in s.rows()}=={'PENDING'}


def test_comparison_evidence_recomputes_and_binds(model,tmp_path):
    from paper_repro.compare import compare_files,recheck_metrics
    import csv
    data=tmp_path/'data.mat';simulate_python(model,data)
    arrays=load_data(data);ref=tmp_path/'ref.csv'
    with ref.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['x','y']);w.writerows(zip(arrays['t'],arrays['out_real_field']))
    metrics=compare_files(ref,data,'out_real_field');metrics['nrmse_range']=999
    assert recheck_metrics(metrics,data)['nrmse_range']==0
    ref.write_text('x,y\n0,0\n1,1\n')
    with pytest.raises(ValueError):recheck_metrics(metrics,data)


def test_commercial_sentinel_without_data_is_not_success(model,tmp_path,monkeypatch):
    import paper_repro.engine as engine
    class FakeSession:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def eval(self,*args):pass
        def getv(self,key):return {'pr_completed':1,'pr_y':[0,0],'pr_time':3.,'pr_steps':150}[key]
    monkeypatch.setattr(engine,'_lumapi',lambda path:SimpleNamespace(INTERCONNECT=FakeSession))
    with pytest.raises(FileNotFoundError):engine.simulate_lumerical(model,tmp_path/'out.mat','fixture-sdk.py')
    assert not (tmp_path/'out.provenance.json').exists()


def test_missing_matlab_still_writes_config(model,tmp_path,monkeypatch):
    import paper_repro.plotting as module
    simulate_python(model,tmp_path/'data.mat')
    monkeypatch.setattr(module,'detect',lambda out:{'matlab':None})
    cfg={'output_dir':str(tmp_path/'plots'),'figures':[{'id':'test','data':str(tmp_path/'data.mat'),
        'panels':[{'columns':['out_energy'],'x_factor':1,'y_factor':1,'xlabel':'s','ylabel':'J'}]}]}
    with pytest.raises(Blocked):plot_matlab(cfg,tmp_path/'config.json')
    assert (tmp_path/'config.json').is_file()


def test_identification_is_bounded_and_keeps_baseline(model,tmp_path):
    from paper_repro.identify import identify
    import csv
    target=copy.deepcopy(model);target['parameters'][1]['value']=1.3
    target_data=tmp_path/'target.mat';simulate_python(target,target_data);arrays=load_data(target_data)
    ref=tmp_path/'ref.csv'
    with ref.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['x','y']);w.writerows(zip(arrays['t'],arrays['out_real_field']))
    model['parameters'][1].update(category='D',optimize=True,bounds=[.5,2.],rationale='Synthetic control parameter identification')
    r=identify(model,ref,'out_real_field',tmp_path/'fit','python-reference',max_evaluations=5,budget_seconds=30)
    assert (tmp_path/'fit/baseline.model.json').is_file()
    assert read_json(tmp_path/'fit/baseline.model.json')['parameters'][1]['value']==1
    assert len(r['trials'])<=5 and not r['heldout_validated']
    assert all(.5<=trial['values'][0]<=2 for trial in r['trials'])


def test_numeric_mat73_orientation(tmp_path):
    import h5py
    path=tmp_path/'fixture73.mat'
    with h5py.File(path,'w') as f:
        f['t']=np.arange(4).reshape(1,4)
        f['out_energy']=np.arange(4).reshape(1,4)**2
    data=load_data(path)
    assert data['out_energy'].tolist()==[0,1,4,9]
    field=tmp_path/'field73.mat'
    with h5py.File(field,'w') as f:
        f['x']=np.arange(3).reshape(1,3);f['y']=np.arange(4).reshape(1,4)
        f['temperature']=np.arange(12).reshape(3,4).T
    contract={'variables':{'x':{'unit':'m','axis':True},'y':{'unit':'m','axis':True},'temperature':{'unit':'K','axes':['x','y']}}}
    assert validate_dataset(field,contract)['temperature'].shape==(3,4)
