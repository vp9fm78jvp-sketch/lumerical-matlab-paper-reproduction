import copy
from pathlib import Path
import pytest
from paper_repro.common import read_json

ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def model():
    return copy.deepcopy(read_json(ROOT/'examples/minimal/model.json'))

@pytest.fixture
def sample_pdf(tmp_path):
    import fitz
    from PIL import Image
    image=tmp_path/'asset.png';Image.new('RGB',(80,60),'#406090').save(image)
    doc=fitz.open();p=doc.new_page(width=600,height=800)
    p.insert_text((40,40),'Synthetic photonics test paper',fontsize=18)
    p.insert_text((40,65),'DOI 10.1234/test.fixture',fontsize=10)
    p.draw_rect(fitz.Rect(40,100,270,250),color=(0,0,0))
    p.draw_line((45,240),(260,110),color=(0,0,1),width=2)
    p.insert_text((50,120),'(a)');p.insert_image(fitz.Rect(320,100,520,250),filename=image)
    p.insert_text((330,120),'(b)')
    p.insert_textbox(fitz.Rect(40,280,550,340),'Fig. 1. (a) Simulated time evolution. (b) SEM micrograph of the device.',fontsize=10)
    p.insert_textbox(fitz.Rect(40,400,550,440),'The model in Eq. (1) predicts Fig. 1(a). A referenced but absent Fig. 9 must be registered.',fontsize=10)
    p.insert_text((40,470),'da/dt = -gamma*a + drive    (1)',fontsize=11)
    doc.save(tmp_path/'test.pdf');doc.close();return tmp_path/'test.pdf'
