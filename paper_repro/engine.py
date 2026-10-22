from __future__ import annotations
import copy
import importlib.util
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from scipy.io import loadmat
from .common import Blocked,digest,now,write_json,sha256
from .compiler import compile_lsf,lsf_string
from .data import save_data,load_data
from .environment import detect
from .model import audit,param_values,evaluate


def numeric_functions(model):
    params=param_values(model)
    def env(t,y):
        d={**params,'t':t,**dict(zip([s['name'] for s in model['states']],y))}
        for a in model.get('algebra',[]):d[a['name']]=evaluate(a['expression'],d)
        return d
    def rhs(t,y):
        d=env(t,y)
        return np.array([evaluate(model['rhs'][s['name']],d) for s in model['states']],float)
    return env,rhs


def simulate_python(model,output,method='Radau'):
    """Explicit numerical reference backend; never labeled as commercial simulation."""
    check=audit(model)
    if not check['can_execute']:raise Blocked(str(check))
    env,rhs=numeric_functions(model)
    tm=model['time'];start=tm.get('start',0);stop=tm['stop']
    count=int(np.ceil((stop-start)/tm['dt']))+1
    if count>tm.get('max_steps',5000000)+1:raise Blocked('Output exceeds point budget')
    times=np.linspace(start,stop,count)
    scales=np.array([s['scale'] for s in model['states']]);y0=np.array([s['initial'] for s in model['states']])
    started=now();clock=time.monotonic()
    def scaled_rhs(t,z):return rhs(t,z*scales)/scales
    sol=solve_ivp(scaled_rhs,(start,stop),y0/scales,t_eval=times,method=method,
        rtol=model.get('rtol',1e-7),atol=model.get('atol',1e-9),max_step=tm.get('max_step',np.inf))
    if not sol.success:raise RuntimeError(sol.message)
    state=sol.y*scales[:,None];arrays={'t':sol.t}
    for o in model['observables']:
        arrays['out_'+o['name']]=np.array([evaluate(o['expression'],env(t,y)) for t,y in zip(sol.t,state.T)],float)
    metadata={'engine':'PYTHON_REFERENCE','integrator':method,'run_id':uuid.uuid4().hex,'model_sha256':digest(model),
        'started_at':started,'finished_at':now(),'elapsed_seconds':time.monotonic()-clock,'nfev':sol.nfev,
        'units':{'t':'s',**{'out_'+o['name']:o['unit'] for o in model['observables']}},
        'final_state':state[:,-1].tolist(),'final_time':float(sol.t[-1]),'commercial_solver_executed':False}
    result=save_data(output,arrays,metadata)
    write_json(Path(output).with_suffix(".model.json"),model)
    return result


def _lumapi(path):
    path=Path(path)
    if path.is_dir():path=path/'lumapi.py'
    if not path.is_file():raise Blocked('lumapi.py missing; set LUMAPI_PATH')
    # Keep official SDK directory on path for its companion libraries.
    sys.path.insert(0,str(path.parent))
    if os.name=='nt' and hasattr(os,'add_dll_directory'):
        for p in [path.parent,path.parent.parent.parent/'bin']:
            if p.is_dir():os.add_dll_directory(str(p))
    spec=importlib.util.spec_from_file_location('lumapi',path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe_lumerical(path,product='INTERCONNECT'):
    if product not in {'FDTD','MODE','DEVICE','INTERCONNECT'}:raise ValueError('Unsupported product')
    module=_lumapi(path)
    try:
        with getattr(module,product)(hide=True) as app:
            app.eval('pr_api_probe=19+23;')
            value=float(np.asarray(app.getv('pr_api_probe')).ravel()[0])
            if value!=42:raise RuntimeError('Script round-trip failed')
    except Exception as e:raise Blocked(f'Lumerical runtime/license probe failed: {e}') from e
    return {'runtime_callable':True,'script_roundtrip':True,'product':product,
        'physical_simulation_executed':False,'license_scope':'Only this product/session was exercised'}


def simulate_lumerical(model,output,lumapi_path=None,product=None):
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    check=audit(model)
    if not check['can_execute']:raise Blocked(str(check))
    cfg=detect(output.parent)
    path=lumapi_path or next(iter(cfg['lumapi_candidates']),None)
    if not path:raise Blocked('Lumerical API unavailable; code generation and static audit remain available')
    product=product or model.get('product','INTERCONNECT')
    if product not in {'FDTD','MODE','DEVICE','INTERCONNECT'}:raise ValueError('Unsupported product constructor')
    # A private new workspace per attempt prevents old files masquerading as fresh success.
    run_id=uuid.uuid4().hex;work=output.parent/'.runs'/run_id;work.mkdir(parents=True)
    raw=work/'solver-output.mat';script=work/'simulation.lsf'
    script.write_text(compile_lsf(model,raw),encoding='utf-8')
    module=_lumapi(path);started=now();clock=time.monotonic()
    try:
        with getattr(module,product)(hide=True) as app:
            app.eval('switchtolayout;')
            app.eval('cd('+lsf_string(work)+');')
            app.eval('feval('+lsf_string(script)+');')
            complete=float(np.asarray(app.getv('pr_completed')).ravel()[0])
            if complete!=1:raise RuntimeError('Numerical completion sentinel absent')
            final=np.asarray(app.getv('pr_y'),float).ravel().tolist()
            final_time=float(np.asarray(app.getv('pr_time')).ravel()[0])
            steps=int(np.asarray(app.getv('pr_steps')).ravel()[0])
    except Exception as e:
        write_json(work/'failure.json',{'error':str(e),'script_sha256':sha256(script),'time':now()})
        raise RuntimeError(f'Lumerical {product} execution failed; inspect {work}: {e}') from e
    arrays=load_data(raw,required=['out_'+o['name'] for o in model['observables']])
    if len(arrays['t'])!=steps+1 or not np.isclose(final_time,model['time']['stop'],rtol=1e-10,atol=1e-30):
        raise ValueError('Incomplete time integration')
    metadata={'engine':'LUMERICAL_SCRIPT','product':product,'integrator':model.get('integration','rk4'),
        'run_id':run_id,'model_sha256':digest(model),'script_sha256':sha256(script),'script':str(script),
        'lumapi_path':str(path),'started_at':started,'finished_at':now(),'elapsed_seconds':time.monotonic()-clock,
        'units':{'t':'s',**{'out_'+o['name']:o['unit'] for o in model['observables']}},
        'final_state':final,'final_time':final_time,'commercial_solver_executed':True,'numerical_steps':steps}
    result=save_data(output,arrays,metadata)
    write_json(Path(output).with_suffix(".model.json"),model)
    return result


def run_worker(model_path,output,backend='lumerical',timeout=600,method='Radau'):
    model_path,output=Path(model_path).resolve(),Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,'-m','paper_repro.worker','--model',str(model_path),'--output',str(output),
        '--backend',backend,'--method',method]
    log=output.with_suffix('.execution.log')
    env=dict(os.environ)
    package_root=str(Path(__file__).resolve().parent.parent)
    env['PYTHONPATH']=package_root+os.pathsep+env.get('PYTHONPATH','')
    with log.open('w',encoding='utf-8') as f:
        p=subprocess.Popen(command,stdout=f,stderr=subprocess.STDOUT,env=env,
            start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
        try:returncode=p.wait(timeout=timeout)
        except BaseException:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
            else:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            p.wait()
            raise
    if returncode==20:raise Blocked(log.read_text(encoding='utf-8')[-4000:])
    if returncode:raise RuntimeError(f'Worker exit {returncode}; {log.read_text(encoding="utf-8")[-4000:]}')
    from .data import verify_receipt
    return verify_receipt(output,'LUMERICAL_SCRIPT' if backend=='lumerical' else 'PYTHON_REFERENCE')
