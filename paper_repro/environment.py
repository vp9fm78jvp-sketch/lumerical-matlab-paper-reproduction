from __future__ import annotations
import glob
import importlib.util
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path


def detect(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    writable=False
    try:
        with tempfile.TemporaryFile(dir=out):writable=True
    except OSError:pass
    candidates=[]
    if os.environ.get('LUMAPI_PATH'):candidates.append(Path(os.environ['LUMAPI_PATH']))
    patterns=['/opt/lumerical/*/api/python/lumapi.py','/opt/lumerical/api/python/lumapi.py',
        '/opt/ansys_inc/v*/Lumerical/api/python/lumapi.py',
        'C:/Program Files/Lumerical/*/api/python/lumapi.py',
        'C:/Program Files/ANSYS Inc/v*/Lumerical/api/python/lumapi.py',
        '/Applications/Lumerical*.app/Contents/API/Python/lumapi.py']
    for pattern in patterns:candidates.extend(Path(p) for p in glob.glob(pattern))
    existing=[]
    for p in candidates:
        if p.is_dir():p=p/'lumapi.py'
        if p.is_file():existing.append(str(p.resolve()))
    matlab=os.environ.get('MATLAB_EXECUTABLE') or shutil.which('matlab')
    if not matlab:
        possible=glob.glob('C:/Program Files/MATLAB/R*/bin/matlab.exe')+glob.glob('/Applications/MATLAB_R*.app/bin/matlab')+glob.glob('/usr/local/MATLAB/R*/bin/matlab')
        matlab=sorted(possible)[-1] if possible else None
    return {'python':sys.version,'supported_python':sys.version_info>=(3,10), 'platform':platform.platform(),
        'dependencies':{m:importlib.util.find_spec(m) is not None for m in ['fitz','numpy','scipy','PIL','pint','yaml','h5py']},
        'lumapi_candidates':existing,'matlab':matlab,'tesseract':shutil.which('tesseract'),
        'writable_output':writable,'license_status':'UNKNOWN: installation is not license validation; run explicit runtime probe',
        'fallback':'Complete extraction/audit/codegen. PYTHON_REFERENCE is opt-in numerical cross-check, never Lumerical evidence.'}
