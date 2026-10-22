import fitz
import pytest
from paper_repro.pdf import extract,apply_review
from paper_repro.manifest import build


def test_native_images_vectors_panels(sample_pdf,tmp_path):
    out=tmp_path/'out';r=extract(sample_pdf,out,dpi=72)
    f=next(f for f in r['figures'] if f['id']=='Fig1')
    assert {p['label'] for p in f['panels']}=={'a','b'}
    assert (out/f['vector_crop']).is_file()
    assert list((out/'assets').glob('*xref*.png'))
    assert list((out/'assets').glob('*vectors.json'))
    assert r['metadata']['doi_candidates']==['10.1234/test.fixture']
    assert any(e['numbers']==['1'] for e in r['equations'])
    assert any(f['id']=='Fig9' and f['missing_caption'] for f in r['figures'])
    assert not r['coverage_reviewed']


def test_agent_panel_review(sample_pdf,tmp_path):
    out=tmp_path/'out';r=extract(sample_pdf,out,dpi=72)
    review={'figures':{'Fig1':{'panels':[
        {'label':'a','bbox':[40,95,275,255],'class':'A','caption':'Simulated time evolution','axes':[{'name':'t','unit':'ns'}]},
        {'label':'b','bbox':[315,95,525,255],'class':'D','caption':'SEM micrograph'}]}},'coverage_reviewed':False}
    r=apply_review(r,review,sample_pdf,out);m=build(r)
    a=next(t for t in m['tasks'] if t['id']=='Fig1(a)');b=next(t for t in m['tasks'] if t['id']=='Fig1(b)')
    assert a['target'] and not b['target']
    assert a['axes'][0]['unit']=='ns'
    assert not a['classification']['provisional']
    assert a['crop']!=b['crop']


def test_missing_file_and_invalid_geometry(tmp_path,sample_pdf):
    with pytest.raises(FileNotFoundError):extract(tmp_path/'missing.pdf',tmp_path/'out')
    r=extract(sample_pdf,tmp_path/'out',dpi=72)
    with pytest.raises(ValueError):apply_review(r,{'figures':{'Fig1':{'panels':[{'bbox':[0,0,900,900]}]}}},sample_pdf,tmp_path/'out')


def test_scanned_warning(tmp_path):
    from PIL import Image
    png=tmp_path/'scan.png';Image.new('RGB',(200,200),'white').save(png)
    doc=fitz.open();p=doc.new_page();p.insert_image(p.rect,filename=png);pdf=tmp_path/'scan.pdf';doc.save(pdf);doc.close()
    r=extract(pdf,tmp_path/'out',dpi=50)
    assert any('scanned' in w for w in r['warnings'])


def test_supplement_main_text_references_are_external(tmp_path):
    doc=fitz.open();p=doc.new_page()
    p.insert_text((40,40),'SUPPLEMENTARY INFORMATION')
    p.insert_text((40,80),'We refer to Fig. 2(a) of the main text.')
    p.draw_rect(fitz.Rect(40,120,300,240))
    p.insert_text((40,270),'Fig. 1. (a) Simulated transmission.')
    path=tmp_path/'supp.pdf';doc.save(path);doc.close()
    r=extract(path,tmp_path/'out',dpi=50)
    assert r['document_kind']=='supplement'
    assert [f['id'] for f in r['figures']]==['Fig1']
    assert r['external_figure_references'][0]['id']=='Fig2'
    assert r['figures'][0]['qualified_id'].endswith('::Fig1')
