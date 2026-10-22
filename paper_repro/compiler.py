"""Generate standalone LSF programs from an audited real-state ODE model."""
from __future__ import annotations
import re
from pathlib import Path
from .model import audit,param_values,lsf_expr
from .common import Blocked


def lsf_string(value):
    # Lumerical accepts forward slash paths on Windows; reject control characters.
    v=str(value).replace('\\','/')
    if any(ord(c)<32 for c in v) or '"' in v:raise ValueError("Unsafe LSF string/path")
    return '"'+v+'"'


def lint_lsf(text):
    issues=[]
    # Strip comments/string literals before checking assignments and delimiters.
    code=re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    code=re.sub(r'#.*','',code)
    for name in ('c','pi','cross','run','matlabsave','feval'):
        if re.search(r'\b'+name+r'\s*=(?!=)',code):issues.append(f"Assignment to built-in {name}")
    if re.search(r'\brun\s*\(\s*"',text):issues.append("run is not a general script execution interface; use feval")
    if re.search(r'\b(end|elseif)\b',code):issues.append("Possible MATLAB syntax in LSF")
    stack=[]
    pairs={')':'(',']':'[','}':'{'}
    for ch in code:
        if ch in '([{':stack.append(ch)
        elif ch in ')]}':
            if not stack or stack.pop()!=pairs[ch]:issues.append('Unbalanced delimiter');break
    if stack:issues.append('Unclosed delimiter')
    return issues


def compile_lsf(model,output):
    check=audit(model)
    if not check['can_execute']:raise Blocked(f"Model not executable: {check}")
    states=model['states'];n=len(states)
    mapping={s['name']:f'pr_y({i+1})' for i,s in enumerate(states)}
    mapping.update({p['name']:f'pr_p({i+1})' for i,p in enumerate(model['parameters'])})
    mapping['t']='pr_time'
    algebra=[]
    for a in model.get('algebra',[]):
        expr=lsf_expr(a['expression'],mapping);name='pr_a_'+a['name']
        algebra.append(f'  {name}={expr};');mapping[a['name']]=name
    pre='\n'.join(algebra)
    lines=['# Generated from audited paper-specific ODE IR. No fabricated output.',
           '# Fixed-step integration requires dt, dt/2 and independent-integrator verification.',
           'function pr_rhs(pr_y,pr_time,pr_p) {',pre,f'  pr_f=matrix({n},1);']
    lines += [f'  pr_f({i+1})={lsf_expr(model["rhs"][s["name"]],mapping)};' for i,s in enumerate(states)]
    lines += ['  return pr_f;','}', 'function pr_observe(pr_y,pr_time,pr_p) {',pre,
              f'  pr_o=matrix({len(model["observables"])},1);']
    lines += [f'  pr_o({i+1})={lsf_expr(o["expression"],mapping)};' for i,o in enumerate(model['observables'])]
    lines += ['  return pr_o;','}']
    split=model.get('split_fields',[])
    if split:
        lines += ['function pr_coeff(pr_y,pr_time,pr_p) {',pre,f'  pr_l=matrix({len(split)},2);']
        for i,f in enumerate(split):
            lines += [f'  pr_l({i+1},1)={lsf_expr(f["coefficient"],mapping)};',f'  pr_l({i+1},2)={lsf_expr(f["drive"],mapping)};']
        lines += ['  return pr_l;','}',
            'function pr_propagate(pr_a,pr_l,pr_b,pr_h) {',
            '  pr_z=pr_l*pr_h;',
            '  if (abs(pr_z)<1e-6) { pr_phi=1+pr_z/2+pr_z^2/6+pr_z^3/24; }',
            '  else { pr_phi=(exp(pr_z)-1)/pr_z; }',
            '  return exp(pr_z)*pr_a+pr_h*pr_phi*pr_b;','}']
    values=param_values(model)
    lines += [f'pr_p=matrix({len(values)},1);']
    lines += [f'pr_p({i+1})={values[p["name"]]:.17g};' for i,p in enumerate(model['parameters'])]
    lines += [f'pr_y=matrix({n},1);']+[f'pr_y({i+1})={s["initial"]:.17g};' for i,s in enumerate(states)]
    tm=model['time'];start=tm.get('start',0);stop=tm['stop'];dt=tm['dt']
    steps=__import__('math').ceil((stop-start)/dt)
    lines += [f'pr_steps={steps};',f'pr_dt={dt:.17g};',f'pr_time={start:.17g};',
              f'pr_stop={stop:.17g};',f'pr_times=matrix(pr_steps+1,1);',
              f'pr_values=matrix(pr_steps+1,{len(model["observables"])});',
              f'pr_states=matrix(pr_steps+1,{n});', 'pr_times(1)=pr_time;',
              'pr_values(1,:)=transpose(pr_observe(pr_y,pr_time,pr_p));',
              'pr_states(1,:)=transpose(pr_y);','for(pr_step=1:pr_steps) {',
              '  pr_h=min([pr_dt,pr_stop-pr_time]);']
    if model.get('integration')=='exponential_midpoint':
        if not split:raise ValueError('exponential_midpoint needs split_fields')
        lines += ['  pr_k1=pr_rhs(pr_y,pr_time,pr_p);','  pr_mid=pr_y+pr_h/2*pr_k1;',
                  '  pr_coeff0=pr_coeff(pr_y,pr_time,pr_p);']
        indexes={s['name']:i+1 for i,s in enumerate(states)}
        for j,f in enumerate(split,1):
            r,im=indexes[f['real']],indexes[f['imag']]
            lines += [f'  pr_a=pr_y({r})+1i*pr_y({im});',f'  pr_b=pr_propagate(pr_a,pr_coeff0({j},1),pr_coeff0({j},2),pr_h/2);',
                f'  pr_mid({r})=real(pr_b);',f'  pr_mid({im})=imag(pr_b);']
        lines += ['  pr_coeffm=pr_coeff(pr_mid,pr_time+pr_h/2,pr_p);',
                  '  pr_next=pr_y+pr_h*pr_rhs(pr_mid,pr_time+pr_h/2,pr_p);']
        for j,f in enumerate(split,1):
            r,im=indexes[f['real']],indexes[f['imag']]
            lines += [f'  pr_a=pr_y({r})+1i*pr_y({im});',f'  pr_b=pr_propagate(pr_a,pr_coeffm({j},1),pr_coeffm({j},2),pr_h);',
                f'  pr_next({r})=real(pr_b);',f'  pr_next({im})=imag(pr_b);']
        lines += ['  pr_y=pr_next;']
    elif model.get('integration','rk4')=='rk4':
        lines += ['  pr_k1=pr_rhs(pr_y,pr_time,pr_p);',
            '  pr_k2=pr_rhs(pr_y+pr_h/2*pr_k1,pr_time+pr_h/2,pr_p);',
            '  pr_k3=pr_rhs(pr_y+pr_h/2*pr_k2,pr_time+pr_h/2,pr_p);',
            '  pr_k4=pr_rhs(pr_y+pr_h*pr_k3,pr_time+pr_h,pr_p);',
            '  pr_y=pr_y+pr_h/6*(pr_k1+2*pr_k2+2*pr_k3+pr_k4);']
    else:raise ValueError('LSF integrator must be rk4 or exponential_midpoint')
    lines += ['  pr_time=pr_time+pr_h;','  pr_times(pr_step+1)=pr_time;',
              '  pr_states(pr_step+1,:)=transpose(pr_y);',
              '  pr_values(pr_step+1,:)=transpose(pr_observe(pr_y,pr_time,pr_p));','}', 't=pr_times;']
    names=[]
    for i,o in enumerate(model['observables'],1):
        name=o['name']
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',name) or name=='t':raise ValueError('Unsafe observable name')
        name='out_'+name;names.append(name);lines.append(f'{name}=pr_values(:,{i});')
    lines += ['matlabsave('+lsf_string(Path(output).resolve())+',t,'+','.join(names)+');',
              'pr_completed=1;','?"PAPER_REPRO_NUMERICS_FINISHED";']
    script='\n'.join(lines)+'\n'
    issues=lint_lsf(script)
    if issues:raise ValueError(issues)
    return script
