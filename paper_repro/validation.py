from __future__ import annotations
import copy
from pathlib import Path
import numpy as np
from .common import read_json,write_json,digest,sha256
from .model import audit
from .consistency import material_hash
from .data import load_data,verify_receipt
from .compare import compare_curves,dynamics


def family_hash(model):
    m=copy.deepcopy(model)
    for k in ('dt','max_step'):m['time'].pop(k,None)
    for k in ('rtol','atol','integration'):m.pop(k,None)
    return digest(m)


def convergence(model,coarse,fine,independent,output,tolerances):
    """Check two refinements and an independent integrator; no boolean-only evidence."""
    paths=[Path(p).resolve() for p in (coarse,fine,independent)]
    if len(set(paths))!=3:raise ValueError('Convergence requires three independent run artifacts')
    receipts=[verify_receipt(p) for p in paths]
    if len({r['run_id'] for r in receipts})!=3:raise ValueError('Repeated execution receipt')
    records=[]
    for p,r in zip(paths,receipts):
        snapshot=read_json(p.with_suffix('.model.json'))
        if digest(snapshot)!=r['model_sha256'] or family_hash(snapshot)!=family_hash(model):raise ValueError('Convergence models differ in physics/conditions')
        records.append(snapshot)
    if records[1]['time']['dt']>records[0]['time']['dt']/2*(1+1e-10):raise ValueError('Fine run must at least halve dt')
    if receipts[2]['integrator']==receipts[1]['integrator']:raise ValueError('Independent run needs a different integrator')
    arrays=[load_data(p) for p in paths];metrics={};passed=True
    for o in model['observables']:
        name='out_'+o['name'];threshold=tolerances.get(name)
        if threshold is None:raise ValueError('Convergence tolerance required for every observable')
        pair=compare_curves(arrays[1]['t'],arrays[1][name],arrays[0]['t'],arrays[0][name])
        independent_metrics=compare_curves(arrays[1]['t'],arrays[1][name],arrays[2]['t'],arrays[2][name])
        ok=pair['nrmse_range']<=threshold and independent_metrics['nrmse_range']<=threshold
        metrics[name]={'refinement':pair,'independent':independent_metrics,'passed':ok};passed &= ok
    result={'type':'convergence','family_sha256':family_hash(model),'passed':bool(passed),'metrics':metrics,
        'artifacts':[{'path':str(p),'sha256':sha256(p),'run_id':r['run_id'],'model_sha256':r['model_sha256']} for p,r in zip(paths,receipts)],
        'tolerances':tolerances}
    if output is not None:write_json(output,result)
    return result


def thresholds_pass(metrics,thresholds):
    checks={}
    if not thresholds:return False,{'error':'No predefined physical acceptance thresholds'}
    for key,rule in thresholds.items():
        value=metrics.get(key)
        if value is None or not isinstance(value,(int,float)):checks[key]=False;continue
        if isinstance(rule,(int,float)):checks[key]=bool(value<=rule)
        elif 'max' in rule:checks[key]=bool(value<=rule['max'])
        elif 'min' in rule:checks[key]=bool(value>=rule['min'])
        else:raise ValueError('Threshold needs min or max')
    return all(checks.values()),checks


def grade(model,data,metrics,thresholds,convergence_path=None,physics_path=None,heldout_path=None):
    audit_result=audit(model)
    result={'grade':'D','reasons':[],'model_sha256':digest(model),'acceptance':thresholds,'metrics':metrics}
    try:
        receipt=verify_receipt(data)
        load_data(data)
        if receipt['model_sha256']!=digest(model):raise ValueError('Result belongs to another model')
    except (FileNotFoundError,ValueError) as e:
        result['reasons'].append(str(e));return result
    if receipt['engine']!='LUMERICAL_SCRIPT':
        result['reasons'].append('Only a Python reference/fixture ran; no Lumerical reproduction grade');return result
    result['grade']='C'
    try:
        from .compare import recheck_metrics
        metrics=recheck_metrics(metrics,data)
        result['metrics']=metrics
    except (ValueError,FileNotFoundError) as e:result['reasons'].append(str(e))
    ok,checks=thresholds_pass(metrics,thresholds);result['threshold_checks']=checks
    if not ok:result['reasons'].append('Physical comparison thresholds not met')
    if not audit_result['can_execute']:result['reasons'].append('Model/unit review failed')
    if not convergence_path:result['reasons'].append('No convergence evidence')
    else:
        conv=read_json(convergence_path)
        if conv.get('type')!='convergence' or conv.get('family_sha256')!=family_hash(model) or not conv.get('passed'):
            result['reasons'].append('Convergence failed or wrong model family')
        else:
            artifacts=conv.get('artifacts',[])
            if len(artifacts)!=3:result['reasons'].append('Three convergence artifacts required')
            else:
                for artifact in artifacts:
                    if sha256(artifact['path'])!=artifact['sha256']:result['reasons'].append('Convergence evidence changed')
                recomputed=convergence(model,*[a['path'] for a in artifacts],None,conv['tolerances'])
                if not recomputed['passed']:result['reasons'].append('Recomputed convergence failed')
    if not physics_path:result['reasons'].append('No physical mechanism/energy-budget evidence')
    else:
        phys=read_json(physics_path)
        if phys.get('model_sha256')!=digest(model) or not phys.get('passed') or not phys.get('checks'):
            result['reasons'].append('Physical checks failed or unbound evidence')
        else:
            for c in phys['checks']:
                if not c.get('passed') or not c.get('method') or not c.get('source') or not c.get('artifact'):
                    result['reasons'].append('Physical check lacks source/method/artifact')
                elif sha256(c['artifact'])!=c.get('artifact_sha256'):result['reasons'].append('Physical evidence hash mismatch')
    inferred=any(p['category'] in {'C','D'} for p in model['parameters']) or bool(model.get('anomalies'))
    if inferred:
        if not heldout_path:result['reasons'].append('Inferred/corrected model needs independent held-out validation')
        else:
            hold=read_json(heldout_path)
            if not hold.get('passed') or hold.get('training_condition')==hold.get('validation_condition') or not hold.get('validation_condition'):
                result['reasons'].append('Invalid held-out condition')
            if hold.get('parameter_sha256')!=material_hash(model):result['reasons'].append('Held-out parameters differ')
            for a in hold.get('artifacts',[]):
                if sha256(a['path'])!=a['sha256']:result['reasons'].append('Held-out artifact changed')
            if not hold.get('artifacts'):result['reasons'].append('Held-out artifacts missing')
            validation=hold.get('comparison')
            if not validation:result['reasons'].append('Held-out physical comparison missing')
            else:
                from .compare import recheck_metrics
                evidence=validation.get('_evidence',{})
                try:
                    recomputed=recheck_metrics(validation,evidence['simulation_file'])
                    held_receipt=verify_receipt(evidence['simulation_file'],'LUMERICAL_SCRIPT')
                    snapshot=read_json(Path(evidence['simulation_file']).with_suffix('.model.json'))
                    if digest(snapshot)!=held_receipt['model_sha256'] or material_hash(snapshot)!=material_hash(model):
                        result['reasons'].append('Held-out actual model parameters differ')
                    if not thresholds_pass(recomputed,hold.get('thresholds',{}))[0]:result['reasons'].append('Held-out thresholds failed')
                except (KeyError,ValueError,FileNotFoundError) as e:result['reasons'].append('Held-out evidence invalid: '+str(e))
    if not result['reasons']:result['grade']='B' if inferred else 'A'
    return result
