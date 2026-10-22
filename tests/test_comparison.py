import numpy as np
import pytest
from PIL import Image,ImageDraw
from paper_repro.compare import compare_curves,dynamics,digitize,compare_maps,compare_eigenvalues,spectrum_features
from paper_repro.data import validate_arrays,load_data


def test_metrics_and_coverage():
    x=np.linspace(0,10,1001);y=np.sin(2*np.pi*x)
    r=compare_curves(x,y,x,y)
    assert r['nrmse_range']==0 and r['period_relative_error']==0
    with pytest.raises(ValueError):compare_curves(x,y,x[1:],y[1:])


def test_not_transient_limit_cycle():
    t=np.linspace(0,30,10000)
    assert dynamics(t,np.sin(2*np.pi*t))['classification']=='sustained_oscillation_candidate'
    assert dynamics(t,np.exp(-t)*np.sin(2*np.pi*t))['classification']=='decaying_or_fixed'
    assert not dynamics(t,np.sin(2*np.pi*t))['limit_cycle_proven']


def test_data_integrity():
    with pytest.raises(ValueError):validate_arrays({'t':[1,0],'y':[2,3]})
    with pytest.raises(ValueError):validate_arrays({'t':[0,1],'y':[float('nan'),3]})
    with pytest.raises(ValueError):validate_arrays({'t':[0,1],'y':[[1,2],[3,4]]})


def test_digitization_linear_log_and_gaps(tmp_path):
    image=Image.new('RGB',(120,120),'white');draw=ImageDraw.Draw(image)
    draw.line([(10,100),(100,10)],fill='blue',width=1)
    draw.rectangle((45,0,55,119),fill='white')
    path=tmp_path/'curve.png';image.save(path)
    cfg={'plot_box':[10,10,100,100],'rgb':[0,0,255],'color_tolerance':10,'x_limits':[1,100],'x_scale':'log','y_limits':[0,1]}
    r=digitize(path,cfg,tmp_path/'data.csv');data=load_data(tmp_path/'data.csv',axis='x')
    assert np.isclose(data['x'][0],1) and np.isclose(data['x'][-1],100)
    assert r['missing_pixel_intervals'] and not r['reviewed']
    assert (tmp_path/'data.overlay.png').is_file()


def test_map_eigen_spectrum():
    assert compare_maps([[0,1],[1,0]],[[0,1],[1,0]],.5)['region_iou']==1
    assert compare_eigenvalues([1+2j,3],[3,1+2j])['max_complex_error']==0
    x=np.linspace(-5,5,1000);y=1-1/(1+x*x)
    assert abs(spectrum_features(x,y)['centers'][0])<.01
