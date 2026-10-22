from __future__ import annotations
import re
from .model import choose_solver

CLASSES={"A":"numerical scientific data","B":"experimental data","C":"scientific schematic",
         "D":"physical/microscopy photograph","E":"insufficient evidence"}


def classify(caption, reviewed_class=None):
    if reviewed_class:
        if reviewed_class not in CLASSES:raise ValueError("Class must be A-E")
        return {"class":reviewed_class,"confidence":1.,"basis":"agent per-panel visual/source review","provisional":False}
    text=caption.lower()
    categories={
        "D":["sem image","sem micrograph","photograph","micrograph","tem image","optical microscope"],
        "B":["measured","experimental","measurement","oscilloscope"],
        "A":["simulated","simulation","calculated","spectrum","spectra","time evolution","self-pulsation", "transmission", "phase portrait", "bifurcation", "temperature distribution", "eigenvalue"],
        "C":["schematic","diagram","photonic circuit","setup","illustration"]}
    scores={k:[w for w in words if w in text] for k,words in categories.items()}
    hits=[k for k,v in scores.items() if v]
    # Never silently resolve conflicting modalities; request per-panel visual interpretation.
    if not hits or (len(hits)>1 and not (set(hits)=={"A","B"})):
        return {"class":"E","confidence":.2,"basis":scores,"provisional":True,
            "reason":"Ambiguous/mixed caption; inspect this panel and full caption"}
    kind="B" if "B" in hits else hits[0]
    return {"class":kind,"confidence":.65,"basis":scores,"provisional":True}


def build(paper):
    tasks=[]
    for f in paper["figures"]:
        for p in f["panels"]:
            result=classify(p.get("caption") or (f["caption"] if not p.get("label") else ""),p.get("class") if p.get("reviewed") else None)
            eligible=result["class"] in {"A","B"}
            text=(p.get("caption","")+" "+" ".join(b["text"] for b in f.get("body_references",[])))
            eq_numbers=set(re.findall(r"(?:Eq\.?|equation)\s*\((\d+[a-z]?)\)",text,re.I))
            eqs=[e["id"] for e in paper.get("equations",[]) if eq_numbers.intersection(e.get("numbers",[]))]
            priority={"importance":p.get("importance",3),"model_completeness":min(5,len(eqs)),
                "parameter_availability":p.get("parameter_availability",0),"quantifiability":4 if eligible else 0,
                "shared_model":p.get("shared_model_score",0),"cost":p.get("cost_score",3)}
            score=sum(v for k,v in priority.items() if k!="cost")-priority["cost"]
            tasks.append({"id":p["id"],"qualified_id":p.get("qualified_id",paper["sha256"][:12]+"::"+p["id"]),"parent":f["id"],"page":f["page"],"caption":p.get("caption",""),
                "full_caption":f["caption"],"crop":p.get("crop"),"bbox":p.get("bbox"),
                "classification":result,"target":eligible,"priority":priority,"priority_score":score,
                "equation_ids":eqs,"parameter_ids":[],"model_id":None,"device_id":None,
                "solver_candidates":choose_solver(text),"dependencies":[],"conditions":{},
                "axes":p.get("axes",[]),"legend":p.get("legend",[]),"annotations":p.get("annotations",[]),
                "status":"PENDING" if eligible else "BLOCKED",
                "reason":"Needs physical model and reference data" if eligible else CLASSES[result["class"]],
                "grade":"D","grade_reason":"No verified simulation evidence", "acceptance":{},
                "confidence":p.get("confidence",0),"reviewed":p.get("reviewed",False),"executions":[]})
    tasks.sort(key=lambda x:(-x["priority_score"],x["id"]))
    return {"schema_version":1,"paper_sha256":paper["sha256"],"coverage_reviewed":paper.get("coverage_reviewed",False),
        "document_id":paper.get("document_id",paper["sha256"][:12]),"external_figure_references":paper.get("external_figure_references",[]),"figure_count":len(paper["figures"]),"panel_count":len(tasks),"tasks":tasks,
        "warnings":paper.get("warnings",[]),"classification_policy":"All heuristic results are provisional until agent review"}
