from __future__ import annotations
import csv
import math
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.signal import find_peaks, peak_widths
from scipy.optimize import linear_sum_assignment
from .common import write_json, sha256


def _series(x,y):
    x,y=np.asarray(x,dtype=float).ravel(),np.asarray(y,dtype=float).ravel()
    if len(x)<4 or x.shape!=y.shape or not np.isfinite(x).all() or not np.isfinite(y).all() or not np.all(np.diff(x)>0):
        raise ValueError("Series needs >=4 finite samples with strictly increasing axis")
    return x,y


def dynamics(t,y,min_cycles=4,tail_fraction=.5):
    t,y=_series(t,y)
    if not 0<tail_fraction<=.75:raise ValueError("tail_fraction must be in (0,.75]")
    cut=int(len(y)*(1-tail_fraction));tt,yy=t[cut:],y[cut:]
    amp=float(np.ptp(yy));full=float(np.ptp(y));early=float(np.ptp(y[:max(cut,4)]))
    amp1=float(np.ptp(yy[:len(yy)//2]));amp2=float(np.ptp(yy[len(yy)//2:]))
    prominence=max(full*.03,np.max(np.abs(y))*1e-10,np.finfo(float).tiny)
    peaks,_=find_peaks(yy,prominence=prominence)
    periods=np.diff(tt[peaks]);period=float(np.mean(periods)) if len(periods) else None
    cv=float(np.std(periods)/np.mean(periods)) if len(periods) else None
    retained=amp2/max(amp1,np.finfo(float).tiny)
    candidate=len(periods)>=min_cycles and cv is not None and cv<.03 and .9<retained<1.1 and amp2>prominence*2
    decaying=amp2<amp1*.7 or (early>0 and amp<early*.01)
    label="sustained_oscillation_candidate" if candidate else "decaying_or_fixed" if decaying or amp<prominence else "unresolved"
    return {"classification":label,"tail_amplitude":amp,"early_amplitude":early,
            "late_amplitude_ratio":retained,"tail_cycles":len(periods),"period":period,
            "period_cv":cv,"limit_cycle_proven":False,
            "note":"A finite time trace alone cannot prove an attracting limit cycle; require longer run, convergence and phase-space checks"}


def compare_curves(rx,ry,sx,sy,uncertainty=0.):
    rx,ry=_series(rx,ry);sx,sy=_series(sx,sy)
    if sx[0]>rx[0]+1e-12*max(abs(rx[0]),1e-300) or sx[-1]<rx[-1]-1e-12*max(abs(rx[-1]),1e-300):
        raise ValueError("Simulation does not cover the complete reference interval; extrapolation forbidden")
    # Interpolation is only evaluation on the reference grid, never data generation.
    pred=np.interp(rx,sx,sy);res=pred-ry
    scale=float(np.ptp(ry))
    if scale==0:scale=max(float(np.sqrt(np.mean(ry**2))),1e-300)
    rmse=float(np.sqrt(np.mean(res**2)))
    corr=None
    if np.std(ry)>0 and np.std(pred)>0:corr=float(np.corrcoef(ry,pred)[0,1])
    refd,simd=dynamics(rx,ry),dynamics(sx,sy)
    period_error=None
    if refd['period'] and simd['period']:period_error=abs(simd['period']/refd['period']-1)
    return {"rmse":rmse,"nrmse_range":rmse/scale,"mae":float(np.mean(np.abs(res))),"correlation":corr,
        "peak_error":abs(float(np.max(pred)-np.max(ry))),"valley_error":abs(float(np.min(pred)-np.min(ry))),
        "period_relative_error":period_error,"reference_dynamics":refd,"simulation_dynamics":simd,
        "reference_uncertainty_y":uncertainty,"samples":len(rx),"phase_alignment":"none",
        "similarity_definition":"No universal similarity percent; thresholds apply separately to named physical metrics"}


def compare_maps(reference,simulation,threshold=None):
    a,b=np.asarray(reference,float),np.asarray(simulation,float)
    if a.shape!=b.shape or a.ndim!=2 or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError("Maps require finite matching 2D grids; register physical axes first")
    result={"rmse":float(np.sqrt(np.mean((a-b)**2))),"max_error":float(np.max(np.abs(a-b)))}
    if threshold is not None:
        aa,bb=a>=threshold,b>=threshold;union=(aa|bb).sum()
        result['region_iou']=float((aa&bb).sum()/union) if union else 1.
    return result


def compare_eigenvalues(reference,simulation):
    a,b=np.asarray(reference,complex).ravel(),np.asarray(simulation,complex).ravel()
    if a.size!=b.size or not a.size or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError("Eigenvalue sets require same nonzero size")
    costs=abs(a[:,None]-b[None,:]);rows,cols=linear_sum_assignment(costs)
    return {"max_complex_error":float(costs[rows,cols].max()),"rms_complex_error":float(np.sqrt(np.mean(costs[rows,cols]**2))),
        "unstable_count_reference":int((a.real>0).sum()),"unstable_count_simulation":int((b.real>0).sum())}


def spectrum_features(x,y,dips=True):
    x,y=_series(x,y);z=-y if dips else y
    peaks,props=find_peaks(z,prominence=np.ptp(y)*.05)
    if len(peaks):
        _,_,left,right=peak_widths(z,peaks,rel_height=.5)
        widths=np.interp(right,np.arange(len(x)),x)-np.interp(left,np.arange(len(x)),x)
    else:widths=[]
    return {"centers":x[peaks].tolist(),"values":y[peaks].tolist(),"fwhm_local_prominence":list(map(float,widths)),
        "note":"Local prominence half-width; for overlapping/Fano lines use the paper-specific line model"}


def digitize(image_path,calibration,output):
    """Calibrated color mask; preserves gaps and pixel-derived uncertainty."""
    a=np.asarray(Image.open(image_path).convert("RGB"),float)
    box=list(map(int,calibration["plot_box"]))
    x0,y0,x1,y1=box
    if not(0<=x0<x1<a.shape[1] and 0<=y0<y1<a.shape[0]):raise ValueError("Calibration bbox out of image")
    target=np.asarray(calibration["rgb"],float)
    tolerance=float(calibration.get("color_tolerance",45))
    mask=np.linalg.norm(a[y0:y1+1,x0:x1+1]-target,axis=2)<=tolerance
    for rect in calibration.get("exclude_boxes",[]):
        ex0,ey0,ex1,ey1=map(int,rect)
        mask[max(0,ey0-y0):min(mask.shape[0],ey1-y0+1),max(0,ex0-x0):min(mask.shape[1],ex1-x0+1)]=False
    xx,yy,spread=[],[],[]
    for col in range(mask.shape[1]):
        hits=np.flatnonzero(mask[:,col])
        if len(hits):xx.append(col);yy.append(float(np.median(hits)));spread.append(float(np.ptp(hits)/2+.5))
    if len(xx)<4:raise ValueError("Too few curve pixels; check RGB, crop, and exclusions")
    def axis(v,start,end,extent,scale):
        if scale not in {'linear','log'}:raise ValueError('Axis scale must be linear or log')
        if scale=='log':
            if start<=0 or end<=0:raise ValueError("Log axis limits must be positive")
            return np.exp(np.log(start)+np.asarray(v)/extent*np.log(end/start))
        return start+np.asarray(v)/extent*(end-start)
    x=axis(xx,*calibration["x_limits"],x1-x0,calibration.get("x_scale","linear"))
    # Image y increases downward, data y upward.
    y=axis(yy,calibration["y_limits"][1],calibration["y_limits"][0],y1-y0,calibration.get("y_scale","linear"))
    upper=axis(np.asarray(yy)-spread,calibration["y_limits"][1],calibration["y_limits"][0],y1-y0,calibration.get("y_scale","linear"))
    lower=axis(np.asarray(yy)+spread,calibration["y_limits"][1],calibration["y_limits"][0],y1-y0,calibration.get("y_scale","linear"))
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['x','y','sigma_y_pixel'])
        writer.writerows(zip(x,y,abs(upper-lower)/2))
    gaps=[(int(xx[i]),int(xx[i+1])) for i in range(len(xx)-1) if xx[i+1]-xx[i]>calibration.get('max_gap_pixels',3)]
    meta={"image_sha256":sha256(image_path),"calibration":calibration,"missing_pixel_intervals":gaps,
          "reference_type":"digitized_approximation","reviewed":False,"csv":str(output),
          "warning":"Legend/axis/multiple traces can contaminate mask. Visually verify overlay before accepting reference."}
    write_json(output.with_suffix('.calibration.json'),meta)
    # QA overlay contains only actually detected pixels.
    overlay=np.array(Image.open(image_path).convert('RGB'))
    for col,row in zip(xx,yy):overlay[y0+round(row),x0+col]=[0,255,0]
    Image.fromarray(overlay).save(output.with_suffix('.overlay.png'))
    return meta


def compare_files(reference,simulation,column,ref_x='x',ref_y='y',uncertainty=0.):
    from .data import load_data,verify_receipt
    from .common import read_json
    reference,simulation=Path(reference).resolve(),Path(simulation).resolve()
    ref=load_data(reference,axis=ref_x);sim=load_data(simulation,required=[column])
    receipt=verify_receipt(simulation)
    r=compare_curves(ref[ref_x],ref[ref_y],sim['t'],sim[column],uncertainty)
    r['_evidence']={'reference_file':str(reference),'simulation_file':str(simulation),
        'reference_sha256':sha256(reference),'simulation_sha256':sha256(simulation),
        'run_id':receipt['run_id'],'model_sha256':receipt['model_sha256'],
        'column':column,'ref_x':ref_x,'ref_y':ref_y,'uncertainty_y':uncertainty}
    return r


def recheck_metrics(metrics,data):
    evidence=metrics.get('_evidence',{})
    required=['reference_file','simulation_file','reference_sha256','simulation_sha256','column']
    if any(k not in evidence for k in required):raise ValueError('Comparison lacks data/reference execution evidence')
    if Path(evidence['simulation_file']).resolve()!=Path(data).resolve():raise ValueError('Comparison uses another simulation')
    if sha256(data)!=evidence['simulation_sha256'] or sha256(evidence['reference_file'])!=evidence['reference_sha256']:
        raise ValueError('Comparison input hash changed')
    return compare_files(evidence['reference_file'],data,evidence['column'],evidence.get('ref_x','x'),evidence.get('ref_y','y'),evidence.get('uncertainty_y',0))
