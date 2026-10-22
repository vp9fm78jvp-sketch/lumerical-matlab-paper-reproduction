"""Execute agent-authored FDTD/MODE/DEVICE/INTERCONNECT projects via a checked data contract."""
from __future__ import annotations
import uuid
from pathlib import Path
import numpy as np
from .data import read_mat
import pint
from .common import Blocked,digest,sha256,write_json,now
from .compiler import lint_lsf,lsf_string
from .environment import detect
from .engine import _lumapi


def validate_dataset(path,contract):
    if not Path(path).is_file():raise FileNotFoundError(path)
    raw=read_mat(path);arrays={};ureg=pint.UnitRegistry()
    if not contract.get('variables'):raise ValueError('Dataset contract needs named variables')
    for name,spec in contract['variables'].items():
        ureg(spec['unit'])
        if name not in raw:raise ValueError('Dataset variable absent: '+name)
        a=np.asarray(raw[name]).squeeze()
        if not np.isfinite(a).all() or a.size<spec.get('min_samples',1):raise ValueError('Empty/nonfinite variable: '+name)
        if spec.get('real',True) and np.iscomplexobj(a):raise ValueError('Unexpected complex output: '+name)
        shape=spec.get('shape')
        if shape and (a.ndim!=len(shape) or any(want is not None and got!=want for got,want in zip(a.shape,shape))):raise ValueError('Wrong shape for '+name)
        if spec.get('axis') and (a.ndim!=1 or len(a)<2 or not np.all(np.diff(a)>0)):raise ValueError('Axis must increase: '+name)
        arrays[name]=a
    for name,spec in contract['variables'].items():
        axes=spec.get('axes',[])
        if axes and arrays[name].shape!=tuple(arrays[x].size for x in axes):raise ValueError('Coordinate/field shape mismatch: '+name)
    return arrays


def run_script(script_path,contract,output,product='FDTD',lumapi_path=None):
    """The script is trusted agent-authored code; PDF text never enters it unreviewed.

    Script exports a MAT file at __OUTPUT_MAT__ and sets pr_completed=1 after solver checks.
    A successful API session alone is not scientific validation.
    """
    script_path=Path(script_path).resolve();output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    text=script_path.read_text(encoding='utf-8')
    issues=lint_lsf(text)
    if issues:raise ValueError(issues)
    if '__OUTPUT_MAT__' not in text:raise ValueError('Authored script needs __OUTPUT_MAT__ export token')
    if not contract.get('review',{}).get('evidence') or not contract['review'].get('physics_reviewed'):
        raise Blocked('Solver geometry/boundaries/material/monitor/export contract requires agent source review')
    if product not in {'FDTD','MODE','DEVICE','INTERCONNECT'}:raise ValueError('Invalid product')
    cfg=detect(output.parent);path=lumapi_path or next(iter(cfg['lumapi_candidates']),None)
    if not path:raise Blocked('Lumerical API not installed; preserve script and dataset contract')
    run_id=uuid.uuid4().hex;work=output.parent/'.runs'/run_id;work.mkdir(parents=True)
    raw=work/'results.mat';generated=work/'simulation.lsf'
    generated.write_text(text.replace('__OUTPUT_MAT__',lsf_string(raw)),encoding='utf-8')
    module=_lumapi(path)
    with getattr(module,product)(hide=True) as app:
        app.eval('switchtolayout;')
        app.eval('cd('+lsf_string(script_path.parent)+');')
        app.eval('feval('+lsf_string(generated)+');')
        if float(np.asarray(app.getv('pr_completed')).ravel()[0])!=1:raise RuntimeError('Completion sentinel missing')
    arrays=validate_dataset(raw,contract)
    # Preserve original MAT bytes from the solver, including complex arrays and multidimensional grids.
    __import__('shutil').copyfile(raw,output)
    meta={'engine':'LUMERICAL_PRODUCT','product':product,'run_id':run_id,'finished_at':now(),
        'model_sha256':digest(contract),'script_sha256':sha256(script_path),'data_sha256':sha256(output),
        'dataset_contract':contract,'variables':list(arrays),'commercial_solver_executed':True,
        'scientific_reproduction_verified':False}
    write_json(output.with_suffix('.provenance.json'),meta);return meta


def run_product_worker(script,contract,output,product='FDTD',timeout=600):
    """Bound commercial product execution in a separate process group."""
    import os,sys,subprocess,signal
    from .data import verify_receipt
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ);env['PYTHONPATH']=str(Path(__file__).resolve().parent.parent)+os.pathsep+env.get('PYTHONPATH','')
    command=[sys.executable,'-m','paper_repro.worker','--script',str(Path(script).resolve()),
        '--contract',str(Path(contract).resolve()),'--output',str(output),'--product',product]
    with output.with_suffix('.execution.log').open('w',encoding='utf-8') as log:
        p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=os.name!='nt',
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
        try:code=p.wait(timeout=timeout)
        except BaseException:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
            else:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            p.wait();raise
    if code==20:raise Blocked('Product execution blocked; inspect '+str(output.with_suffix('.execution.log')))
    if code:raise RuntimeError('Product worker failed; inspect '+str(output.with_suffix('.execution.log')))
    return verify_receipt(output,'LUMERICAL_PRODUCT')
