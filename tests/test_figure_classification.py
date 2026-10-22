import pytest
from paper_repro.manifest import classify
from paper_repro.model import choose_solver

@pytest.mark.parametrize('caption,kind',[
 ('Simulated transmission spectrum','A'),('Measured transmission spectra','B'),
 ('SEM micrograph','D'),('Schematic diagram of setup','C'),('Unspecified panel','E'),
 ('Schematic and simulated spectrum','E')])
def test_classification(caption,kind):
    r=classify(caption);assert r['class']==kind and r['provisional']


def test_solver_selection():
    assert choose_solver('TCMT self-pulsation coupled mode bifurcation')[0]['solver']=='INTERCONNECT_SCRIPT'
    assert choose_solver('carrier transport drift-diffusion poisson')[0]['solver']=='CHARGE'
    assert choose_solver('Maxwell scattering electromagnetic field')[0]['solver']=='FDTD'
