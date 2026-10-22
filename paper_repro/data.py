from __future__ import annotations
import csv
from pathlib import Path
import numpy as np
from scipy.io import loadmat, savemat
from .common import write_json, read_json, sha256


def vector(v,name):
    a=np.asarray(v)
    if a.ndim>2 or (a.ndim==2 and min(a.shape)>1):raise ValueError(f"{name}: expected a vector, got {a.shape}")
    a=a.reshape(-1)
    if len(a)<2 or not np.isfinite(a).all():raise ValueError(f"{name}: needs at least two finite samples")
    if np.iscomplexobj(a):raise ValueError(f"{name}: export real/imaginary components separately")
    return a.astype(float)


def validate_arrays(arrays,axis="t",required=None):
    if axis not in arrays:raise ValueError(f"Missing axis {axis}")
    clean={k:vector(v,k) for k,v in arrays.items() if not k.startswith("__")}
    n=len(clean[axis])
    if not np.all(np.diff(clean[axis])>0):raise ValueError("Axis must be strictly increasing, no duplicate points")
    for k,v in clean.items():
        if len(v)!=n:raise ValueError(f"{k}: inconsistent length")
    for k in required or []:
        if k not in clean:raise ValueError(f"Missing output {k}")
    return clean


def read_mat(path):
    """Read numeric MATLAB MAT exports, including HDF5-backed v7.3 arrays."""
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    import h5py
    if not h5py.is_hdf5(path):return loadmat(path)
    data={}
    with h5py.File(path,'r') as f:
        for name,item in f.items():
            if name.startswith('#'):continue
            if not isinstance(item,h5py.Dataset):raise ValueError('Export numeric arrays rather than MATLAB structs: '+name)
            a=np.asarray(item)
            if a.dtype.names:
                if set(a.dtype.names)=={'real','imag'}:a=a['real']+1j*a['imag']
                else:raise ValueError('Unsupported MATLAB compound datatype: '+name)
            if a.dtype.kind not in 'biufc':raise ValueError('Non-numeric MATLAB export: '+name)
            if a.ndim>1:a=a.transpose(tuple(reversed(range(a.ndim))))
            data[name]=a
    return data


def load_data(path,axis="t",required=None):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    if path.suffix==".mat":d=read_mat(path)
    elif path.suffix==".npz":
        with np.load(path,allow_pickle=False) as f:d=dict(f)
    elif path.suffix==".csv":
        with path.open(encoding="utf-8",newline="") as f:
            rows=list(csv.DictReader(f))
        if not rows:raise ValueError("Empty CSV")
        d={k:[float(r[k]) for r in rows] for k in rows[0]}
    else:raise ValueError("Supported data formats: numeric .mat (including v7.3), .npz, .csv")
    return validate_arrays(d,axis,required)


def save_data(path,arrays,metadata):
    arrays=validate_arrays(arrays)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    savemat(path,{k:v.reshape(-1,1) for k,v in arrays.items()},do_compression=True)
    meta={**metadata,"data_sha256":sha256(path),"columns":list(arrays),"samples":len(arrays['t'])}
    write_json(path.with_suffix(".provenance.json"),meta)
    return meta


def verify_receipt(path,expected_engine=None):
    path=Path(path);meta=read_json(path.with_suffix(".provenance.json"))
    if meta.get("data_sha256")!=sha256(path):raise ValueError("Data hash differs from execution receipt")
    if expected_engine and meta.get("engine")!=expected_engine:raise ValueError("Wrong execution backend")
    if not meta.get("run_id") or not meta.get("model_sha256"):raise ValueError("Missing run/model identity")
    return meta
