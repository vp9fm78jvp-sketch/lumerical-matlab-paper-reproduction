"""Conservative PDF inventory. Geometry/classification is a proposal until reviewed."""
from __future__ import annotations
import re
from pathlib import Path
import fitz
from .common import sha256, write_json

CAPTION = re.compile(r"^(?:fig(?:ure)?\.?)[ \t]*(S?\d+)\s*[.:]", re.I)
FIGREF = re.compile(r"\bFig(?:ure)?s?\.?\s*(S?\d+)(?:\s*\(([a-z]\d*)\))?", re.I)
PANEL = re.compile(r"\(([a-z]\d*)\)", re.I)
DOI = re.compile(r"10\.\d{4,9}/[^\s<>]+", re.I)


def _rect(r):
    return [round(float(v), 3) for v in r]


def _source(page, block):
    return {"page": page, "bbox": block["bbox"], "text": block["text"]}


def _panel_caption(caption, label):
    parts = list(PANEL.finditer(caption))
    for i, m in enumerate(parts):
        if m[1].lower() == label.lower():
            return caption[m.start():parts[i + 1].start() if i + 1 < len(parts) else len(caption)]
    return ""


def extract(pdf_path, out, dpi=150, ocr=False):
    """Keep full-page renders, lossless embedded assets and vector crop PDFs.

    Candidate regions/subpanels are explicitly incomplete until agent visual review.
    OCR requires local Tesseract; equations remain unverified after OCR.
    """
    pdf_path, out = Path(pdf_path).resolve(), Path(out).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    if doc.needs_pass:
        raise ValueError("PDF is encrypted: provide a readable copy")
    result = {"schema_version": 1, "source": str(pdf_path), "sha256": sha256(pdf_path),
              "metadata": dict(doc.metadata), "pages": [], "figures": [], "equations": [],
              "tables": [], "warnings": [], "coverage_reviewed": False}
    all_text = []
    for pn, page in enumerate(doc, 1):
        folder = out / "pages"
        folder.mkdir(exist_ok=True)
        page.get_pixmap(dpi=dpi).save(folder / f"page-{pn:03}.png")
        tp = None
        if len(page.get_text().strip()) < 30:
            if ocr:
                try:
                    tp = page.get_textpage_ocr(dpi=300, full=True)
                except Exception as e:
                    result["warnings"].append(f"Page {pn}: OCR unavailable: {e}")
            else:
                result["warnings"].append(f"Page {pn}: scanned/empty; request agent OCR review")
        raw = page.get_text("dict", textpage=tp)
        blocks, lines = [], []
        for b in raw["blocks"]:
            if b["type"] != 0:
                continue
            bt = []
            for line in b["lines"]:
                text = "".join(s["text"] for s in line["spans"])
                bt.append(text)
                lines.append({"text": text, "bbox": _rect(line["bbox"])})
            blocks.append({"text": "\n".join(bt), "bbox": _rect(b["bbox"])})
        text = "\n\n".join(b["text"] for b in blocks)
        all_text.append(text)
        (folder / f"page-{pn:03}.txt").write_text(text, encoding="utf-8")
        assets = out / "assets"; assets.mkdir(exist_ok=True)
        image_regions = []
        for index, entry in enumerate(page.get_images(full=True)):
            xref = entry[0]
            try:
                image = doc.extract_image(xref)
                name = f"p{pn:03}-xref{xref}.{image['ext']}"
                (assets / name).write_bytes(image["image"])
                # Preserve an alpha mask separately rather than discarding it.
                if entry[1]:
                    mask = doc.extract_image(entry[1])
                    (assets / f"p{pn:03}-xref{xref}-mask.{mask['ext']}").write_bytes(mask["image"])
                image_regions += [_rect(r) for r in page.get_image_rects(xref)]
            except (ValueError, RuntimeError) as e:
                result["warnings"].append(f"Page {pn} asset {index}: {e}")
        drawings = page.get_drawings()
        # Full native vector geometry, including paths, not rasterized curves.
        write_json(assets / f"p{pn:03}-vectors.json", [
            {"rect": _rect(d["rect"]), "type": d["type"],
             "color": d.get("color"), "fill": d.get("fill"),
             "items": [[str(v) for v in item] for item in d["items"]]} for d in drawings])
        captions = []
        for b in blocks:
            m = CAPTION.match(b["text"].lstrip())
            if m:
                captions.append((m[1].upper(), b))
        for number, cap in captions:
            cb = fitz.Rect(cap["bbox"])
            # Candidate column; never claim semantic segmentation from geometry alone.
            half_column = cb.width < page.rect.width * .65
            left = 0 if not half_column else max(0, cb.x0 - 12)
            right = page.rect.width if not half_column else min(page.rect.width, cb.x1 + 12)
            prior = [fitz.Rect(b["bbox"]).y1 for n,b in captions
                     if fitz.Rect(b["bbox"]).y1 < cb.y0 and fitz.Rect(b["bbox"]).x0 < right
                     and fitz.Rect(b["bbox"]).x1 > left]
            bottom = cb.y0
            candidates = [fitz.Rect(r) for r in image_regions + [_rect(d["rect"]) for d in drawings]
                          if fitz.Rect(r).y1 <= bottom + 3 and fitz.Rect(r).y0 > max(prior, default=20)
                          and fitz.Rect(r).x0 >= left - 3 and fitz.Rect(r).x1 <= right + 3
                          and fitz.Rect(r).height > 2]
            if candidates:
                region = candidates[0]
                for r in candidates[1:]: region |= r
                region = fitz.Rect(max(left, region.x0-8), max(0, region.y0-14),
                                   min(right, region.x1+8), min(bottom, region.y1+10))
            else:
                region = fitz.Rect(left, max(max(prior,default=20), bottom-page.rect.height*.45), right, bottom)
            if region.is_empty:
                region = fitz.Rect(left, max(0,bottom-100), right, bottom)
            figdir = out / "figures"; figdir.mkdir(exist_ok=True)
            fid = f"Fig{number}"
            suffix = f"{fid}-p{pn}"
            page.get_pixmap(clip=region,dpi=max(dpi,240)).save(figdir/f"{suffix}.png")
            vector_doc = fitz.open(); vp = vector_doc.new_page(width=region.width,height=region.height)
            vp.show_pdf_page(vp.rect,doc,pn-1,clip=region)
            vector_doc.save(figdir/f"{suffix}.pdf"); vector_doc.close()
            labels = sorted(set(m[1].lower() for m in PANEL.finditer(cap["text"])))
            located = [l for l in lines if re.fullmatch(r"\(?[a-z]\d*\)?",l["text"].strip())
                       and fitz.Rect(l["bbox"]).intersects(region)]
            for line in located:
                label=line["text"].strip("() ").lower()
                if label not in labels: labels.append(label)
            panels = []
            for label in labels or [""]:
                loc = next((l for l in located if l["text"].strip("() ").lower()==label),None)
                # Subpanel clips need visual review: retain parent image if no reliable box.
                panels.append({"id":fid+(f"({label})" if label else ""),"label":label,
                    "caption":_panel_caption(cap["text"],label) if label else cap["text"],
                    "bbox":None,"label_bbox":loc["bbox"] if loc else None,
                    "crop":f"figures/{suffix}.png","crop_scope":"parent_candidate",
                    "axes":[],"legend":[],"annotations":[],"confidence":.35,
                    "reviewed":False})
            result["figures"].append({"id":fid,"page":pn,"caption":cap["text"],
                "caption_bbox":cap["bbox"],"bbox":_rect(region),"crop":f"figures/{suffix}.png",
                "vector_crop":f"figures/{suffix}.pdf","panels":panels,
                "body_references":[],"geometry_reviewed":False})
        # Candidate equation anchors plus surrounding raw blocks (not invented LaTeX).
        for i,b in enumerate(blocks):
            markers = re.findall(r"\((\d+[a-z]?)\)\s*[.,]?\s*$",b["text"], re.M)
            mathlike = any(c in b["text"] for c in "=∂∑∫τΔκβω")
            if mathlike and (markers or len(b["text"])<400):
                result["equations"].append({"id":f"eq-p{pn}-b{i}","numbers":markers,
                    **_source(pn,b),"verified":False,"latex":None,"warnings":["Verify glyphs, signs, superscripts visually"]})
        try:
            for ti,t in enumerate(page.find_tables().tables):
                result["tables"].append({"id":f"table-p{pn}-{ti}","page":pn,"bbox":_rect(t.bbox),
                    "cells":t.extract(),"reviewed":False})
        except (AttributeError, ValueError, RuntimeError) as e:
            result["warnings"].append(f"Page {pn}: native table detection: {e}")
        result["pages"].append({"page":pn,"width":page.rect.width,"height":page.rect.height,
            "blocks":blocks,"lines":lines,"image_regions":image_regions,"ocr_used":tp is not None,
            "render":f"pages/page-{pn:03}.png"})
    fulltext="\n\n".join(all_text)
    result["document_kind"]="supplement" if re.search(r"SUPPLEMENTARY|SUPPORTING INFORMATION",all_text[0][:1500],re.I) else "paper"
    result["document_id"]=result["sha256"][:12]
    result["external_figure_references"]=[]
    result["metadata"]["doi_candidates"]=sorted(set(DOI.findall(fulltext)))
    result["metadata"]["section_candidates"]=[{"page":p["page"],"text":b["text"]}
        for p in result["pages"] for b in p["blocks"] if re.match(r"^(?:[IVX]+\.|Appendix|References|Supplementary)",b["text"],re.I)]
    known={f["id"] for f in result["figures"]}
    referenced={"Fig"+m[1].upper() for m in FIGREF.finditer(fulltext)}
    for missing in sorted(referenced-known):
        num=missing[3:]
        contexts=[_source(p['page'],b) for p in result['pages'] for b in p['blocks']
            if any(m[1].upper()==num for m in FIGREF.finditer(b['text']))]
        if result['document_kind']=='supplement' and any(re.search(r'main[ -](?:text|paper|article)',c['text'],re.I) for c in contexts):
            result['external_figure_references'].append({'id':missing,'document':'main_text','contexts':contexts})
            continue
        result["warnings"].append(f"{missing} referenced but no caption located: inventory review required")
        result["figures"].append({"id":missing,"page":None,"caption":"","panels":[{
            "id":missing,"label":"","caption":"","crop":None,"bbox":None,"axes":[],
            "legend":[],"annotations":[],"confidence":0,"reviewed":False}],"geometry_reviewed":False,
            "body_references":[],"missing_caption":True})
    for f in result["figures"]:
        num=f["id"][3:]
        f["body_references"]=[_source(p["page"],b) for p in result["pages"] for b in p["blocks"]
            if any(m[1].upper()==num for m in FIGREF.finditer(b["text"])) and not CAPTION.match(b["text"])]
    for f in result['figures']:
        f['qualified_id']=result['document_id']+'::'+f['id']
        for p in f['panels']:p['qualified_id']=result['document_id']+'::'+p['id']
    for e in result['equations']:e['qualified_id']=result['document_id']+'::'+e['id']
    result["referenced_figure_ids"]=sorted(referenced)
    (out/"fulltext.txt").write_text(fulltext,encoding="utf-8")
    write_json(out/"paper.json",result)
    doc.close()
    return result


def apply_review(paper, review, pdf_path, out):
    """Agent-generated exact per-panel boxes/metadata; crop from original PDF."""
    doc=fitz.open(pdf_path)
    for fid,update in review.get("figures",{}).items():
        figure=next((f for f in paper["figures"] if f["id"]==fid),None)
        if figure is None: raise ValueError(f"Unknown figure {fid}")
        pn=update.get("page",figure.get("page"))
        if not isinstance(pn,int) or not 1<=pn<=len(doc): raise ValueError("Invalid review page")
        figure["page"]=pn
        if "caption" in update: figure["caption"]=update["caption"]
        if "panels" in update:
            panels=[]
            for p in update["panels"]:
                r=fitz.Rect(p["bbox"])
                if r.is_empty or not doc[pn-1].rect.contains(r): raise ValueError("Invalid panel bbox")
                label=p.get("label",""); pid=fid+(f"({label})" if label else "")
                rel=f"figures/{pid}.png"
                doc[pn-1].get_pixmap(clip=r,dpi=300).save(Path(out)/rel)
                panels.append({**p,"id":pid,"crop":rel,"crop_scope":"panel_reviewed",
                    "reviewed":True,"qualified_id":paper.get("document_id",paper["sha256"][:12])+"::"+pid,"confidence":p.get("confidence",.9)})
            if not panels: raise ValueError("A registered figure cannot lose all panels")
            figure["panels"]=panels
        figure["geometry_reviewed"]=True
    paper["coverage_reviewed"]=bool(review.get("coverage_reviewed",False))
    paper["review_evidence"]=review.get("evidence","")
    if paper["coverage_reviewed"] and (not paper["review_evidence"] or
            not all(f["geometry_reviewed"] for f in paper["figures"])):
        raise ValueError("Coverage approval needs evidence and review of every figure")
    doc.close()
    write_json(Path(out)/"paper.json",paper)
    return paper
