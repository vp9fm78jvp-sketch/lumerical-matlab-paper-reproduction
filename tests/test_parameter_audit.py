import copy
import pytest
from paper_repro.model import audit,evaluate,param_values
from paper_repro.compiler import compile_lsf,lint_lsf
from paper_repro.consistency import check


def test_unit_mismatch_and_provenance(model):
    assert audit(model)['can_execute']
    model['parameters'][0]['unit']='m'
    assert not audit(model)['units_passed']


def test_missing_physical_review(model):
    model['review']={};assert not audit(model)['can_execute']


def test_derived_parameters_keep_dimensions(model):
    model['parameters'].append({'name':'doubleGamma','expression':'2*gamma','unit':'1/s','category':'B','source':'analytic'})
    assert param_values(model)['doubleGamma']==4

@pytest.mark.parametrize('expr',["__import__('os')",'a.b','x[0]','[1,2]','lambda x:x','sum(x,y=2)'])
def test_no_code_execution(expr):
    with pytest.raises((ValueError,SyntaxError)):evaluate(expr,{})


def test_reserved_names(model,tmp_path):
    model['parameters'][0]['name']='cross'
    assert not audit(model)['can_execute']
    assert lint_lsf('cross=2;')
    assert lint_lsf('run("script.lsf");')


def test_compile_exponential_and_rk4(model,tmp_path):
    script=compile_lsf(model,tmp_path/'real data.mat')
    assert 'pr_propagate' in script and 'matlabsave(' in script and not lint_lsf(script)
    model['integration']='rk4';assert 'pr_k4' in compile_lsf(model,tmp_path/'a.mat')


def test_shared_parameters(model):
    other=copy.deepcopy(model);other['id']='other';other['parameters'][0]['value']=3
    assert not check([model,other])['passed']
