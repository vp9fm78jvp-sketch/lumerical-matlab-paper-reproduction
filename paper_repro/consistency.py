"""Check shared device models without erasing legitimate condition differences."""
from .common import digest
from .model import param_values


def material_hash(model):
    conditions=set(model.get('condition_parameters',[]))
    return digest([p for p in model['parameters'] if p['name'] not in conditions])


def check(models):
    devices={};issues=[]
    for m in models:
        key=(m.get('device_id',m['id']),m.get('variant_id','default'))
        vals=param_values(m);conditions=set(m.get('condition_parameters',[]))
        if key not in devices:devices[key]=(m,vals);continue
        baseline,bvals=devices[key]
        if conditions!=set(baseline.get('condition_parameters',[])):
            issues.append({'device':key[0],'models':[baseline['id'],m['id']],'reason':'Condition parameter declaration differs'})
        for name in set(vals)|set(bvals):
            if name in conditions:continue
            if name not in vals or name not in bvals or vals[name]!=bvals[name]:
                # Derived parameters can change when a declared condition changes; verify expression identity.
                p=next((p for p in m['parameters'] if p['name']==name),{})
                b=next((p for p in baseline['parameters'] if p['name']==name),{})
                if p.get('expression') and p.get('expression')==b.get('expression'):continue
                issues.append({'device':key[0],'parameter':name,'models':[baseline['id'],m['id']],
                    'reason':'Shared device parameter changed without an explicit variant/device declaration'})
    return {'passed':not issues,'issues':issues,'model_count':len(models)}
