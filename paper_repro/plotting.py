from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from PIL import Image
from .common import Blocked,write_json,sha256,now
from .data import load_data,verify_receipt
from .environment import detect


def matlab_quote(path):return "'"+str(Path(path).resolve()).replace("'","''")+"'"


def plot_matlab(config,config_path,timeout=300):
    for fig in config['figures']:
        if not __import__('re').fullmatch(r'[A-Za-z0-9_()-]+',fig['id']):raise ValueError('Unsafe figure filename')
        receipt=verify_receipt(fig['data'])
        if receipt.get('dataset_contract'):
            from .product import validate_dataset
            validate_dataset(fig['data'],receipt['dataset_contract'])
        else:
            load_data(fig['data'],required=[c for p in fig['panels'] for c in p['columns']])
    config_path=Path(config_path).resolve();write_json(config_path,config)
    cfg=detect(config_path.parent)
    if not cfg['matlab']:raise Blocked('MATLAB unavailable; plotting script/config are generated but not executed')
    root=Path(__file__).resolve().parent.parent
    template=Path(__file__).resolve().parent/'assets'/'plot_all.m'
    if not template.exists():raise Blocked('Install the whole skill repository: templates/plot_all.m missing')
    script_dir=config_path.parent/'matlab';script_dir.mkdir(exist_ok=True)
    shutil.copyfile(template,script_dir/'plot_all.m')
    command=[cfg['matlab']]
    if __import__('os').name=='nt':command+=['-wait']
    command+=['-batch','addpath('+matlab_quote(script_dir)+'); plot_all('+matlab_quote(config_path)+');']
    process=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
    (config_path.parent/'matlab.log').write_text(process.stdout+'\n'+process.stderr,encoding='utf-8')
    if process.returncode:raise RuntimeError('MATLAB failed: inspect matlab.log')
    outputs=[]
    for f in config['figures']:
        for ext in ['png','pdf','svg','fig']:
            file=Path(config['output_dir'])/(f['id']+'.'+ext)
            if not file.exists() or file.stat().st_size<100:raise ValueError('Missing/empty plot: '+str(file))
            if ext=='png':
                with Image.open(file) as im:im.verify()
            outputs.append({'file':str(file),'sha256':sha256(file)})
    receipt={'engine':'MATLAB','time':now(),'outputs':outputs,'config_sha256':sha256(config_path)}
    write_json(config_path.with_suffix('.plot-receipt.json'),receipt)
    return receipt
