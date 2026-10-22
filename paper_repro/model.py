"""Small auditable expression IR, shared by unit audit, Python checks and LSF emission."""
from __future__ import annotations
import ast
from functools import lru_cache
import math
import re
from pathlib import Path
import numpy as np
import pint
from .common import digest, write_json

UREG=pint.UnitRegistry()
FUNCTIONS={"sqrt":lambda x:x**.5,"abs":abs,"abs2":lambda x:abs(x)**2,
           "exp":np.exp,"sin":np.sin,"cos":np.cos,"log":np.log,
           "real":lambda x:x.real,"imag":lambda x:x.imag,
           "conj":lambda x:x.conjugate()}
RESERVED={"c","pi","cross","run","matrix","length","time","t","dt","h","i","j",
          "clear","switchtolayout","matlabsave","feval","eval","set","get"}


@lru_cache(maxsize=4096)
def parse(expr):
    node=ast.parse(expr,mode="eval")
    for n in ast.walk(node):
        if not isinstance(n,(ast.Expression,ast.BinOp,ast.UnaryOp,ast.Add,ast.Sub,ast.Mult,
            ast.Div,ast.Pow,ast.USub,ast.UAdd,ast.Name,ast.Load,ast.Constant,ast.Call)):
            raise ValueError(f"Forbidden expression construct: {type(n).__name__}")
        if isinstance(n,ast.Constant) and (isinstance(n.value,bool) or not isinstance(n.value,(int,float,complex))):
            raise ValueError("Only numeric constants are allowed")
        if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in FUNCTIONS or n.keywords or len(n.args)!=1):
            raise ValueError("Only supported one-argument mathematical functions are allowed")
    return node.body


def evaluate(expr, env):
    def go(n):
        if isinstance(n,ast.Constant):return n.value
        if isinstance(n,ast.Name):
            if n.id not in env:raise ValueError(f"Unknown symbol: {n.id}")
            return env[n.id]
        if isinstance(n,ast.UnaryOp):return -go(n.operand) if isinstance(n.op,ast.USub) else go(n.operand)
        if isinstance(n,ast.Call):return FUNCTIONS[n.func.id](go(n.args[0]))
        a,b=go(n.left),go(n.right)
        if isinstance(n.op,ast.Add):return a+b
        if isinstance(n.op,ast.Sub):return a-b
        if isinstance(n.op,ast.Mult):return a*b
        if isinstance(n.op,ast.Div):return a/b
        return a**b
    return go(parse(expr))


def lsf_expr(expr, mapping=None):
    mapping=mapping or {}
    def go(n):
        if isinstance(n,ast.Constant):
            if isinstance(n.value,complex):return f"({n.value.real:.17g}+1i*({n.value.imag:.17g}))"
            return repr(n.value)
        if isinstance(n,ast.Name):return mapping.get(n.id,n.id)
        if isinstance(n,ast.UnaryOp):return f"({'-' if isinstance(n.op,ast.USub) else '+'}{go(n.operand)})"
        if isinstance(n,ast.Call):
            v=go(n.args[0]); f=n.func.id
            return f"(abs({v})^2)" if f=="abs2" else f"{f}({v})"
        op={ast.Add:"+",ast.Sub:"-",ast.Mult:"*",ast.Div:"/",ast.Pow:"^"}[type(n.op)]
        return f"({go(n.left)}{op}{go(n.right)})"
    return go(parse(expr))


def param_values(model, quantities=False):
    env={}
    for p in model["parameters"]:
        v=evaluate(p["expression"],env) if p.get("expression") else p["value"]*UREG(p["unit"])
        if not isinstance(v,pint.Quantity):v=v*UREG.dimensionless
        v=v.to(p.get("expected_unit",p["unit"]))
        env[p["name"]]=v.to_base_units()
    return env if quantities else {k:float(v.magnitude) for k,v in env.items()}


def environment(model,state,t,quantities=False):
    env=param_values(model,quantities)
    env["t"]=t*UREG.second if quantities else t
    for s,v in zip(model["states"],state):
        env[s["name"]]=v*UREG(s["unit"]) if quantities else v
    for term in model.get("algebra",[]):env[term["name"]]=evaluate(term["expression"],env)
    return env


def audit(model):
    errors,warnings=[],[]
    names=[p["name"] for p in model["parameters"]]+[s["name"] for s in model["states"]]+[a["name"] for a in model.get("algebra",[])]
    if len(names)!=len(set(names)):errors.append("Duplicate symbol")
    for name in names:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*",name) or name in RESERVED or name in FUNCTIONS or name.startswith("pr_"):
            errors.append(f"Unsafe/reserved Lumerical symbol: {name}")
    for p in model["parameters"]:
        if p.get("category") not in {"A","B","C","D"}:errors.append(f"{p['name']}: missing source category")
        if not p.get("source"):errors.append(f"{p['name']}: missing provenance")
        if p.get("category")=="B" and not p.get("expression"):errors.append(f"{p['name']}: derived parameter needs expression")
        if p.get("optimize") and (p.get("category")!="D" or not p.get("bounds") or not p.get("rationale")):
            errors.append(f"{p['name']}: optimization requires D, physical bounds and rationale")
        if p.get("category")=="D" and not p.get("bounds"):errors.append(f"{p['name']}: missing identification bounds")
        if p.get("bounds") and p.get("value") is not None and not p["bounds"][0]<=p["value"]<=p["bounds"][1]:errors.append(f"{p['name']}: value outside physical bounds")
    try:
        env=environment(model,[max(abs(s.get("initial",0)),s.get("scale",1)) for s in model["states"]],1,True)
        for s in model["states"]:
            unit=UREG(s["unit"])
            if unit.to_base_units().magnitude!=1:errors.append(f"{s['name']}: state unit must be SI base-scale")
            value=evaluate(model["rhs"][s["name"]],env)
            if not isinstance(value,pint.Quantity):value=value*UREG.dimensionless
            value.to(unit.units/UREG.second)
            if not s.get("scale",0)>0:errors.append(f"{s['name']}: positive solver scale required")
        for a in model.get("algebra",[]):
            if a.get("unit"):
                v=env[a["name"]]
                if not isinstance(v,pint.Quantity):v=v*UREG.dimensionless
                v.to(a["unit"])
        for o in model["observables"]:
            v=evaluate(o["expression"],env)
            if not isinstance(v,pint.Quantity):v=v*UREG.dimensionless
            v.to(o["unit"])
    except Exception as e:errors.append(f"Dimension/expression audit: {type(e).__name__}: {e}")
    for s in model["states"]:
        if s["name"] not in model["rhs"]:errors.append(f"Missing derivative: {s['name']}")
    tm=model["time"]
    if not 0<tm["dt"]<=tm["stop"]-tm.get("start",0):errors.append("Invalid timestep/time interval")
    if (tm["stop"]-tm.get("start",0))/tm["dt"]>tm.get("max_steps",5000000):errors.append("Time integration exceeds configured step budget")
    required={"equations","normalization","loss_budget","detuning_sign","initial_boundary","parameter_sources"}
    review=model.get("review",{})
    missing=sorted(k for k in required if not review.get(k))
    if missing:warnings.append("Scientific review missing: "+", ".join(missing))
    if not review.get("evidence"):warnings.append("Scientific review needs source/page/equation evidence")
    if not model.get("provenance",{}).get("sources"):errors.append("Model source list is missing")
    if model.get("anomalies"):warnings.append("Open source anomalies: explicit variant required; strict grade A unavailable")
    return {"model_id":model["id"],"model_sha256":digest(model),"errors":errors,"warnings":warnings,
        "units_passed":not errors,"scientific_review_passed":not missing and bool(review.get("evidence")),
        "can_execute":not errors and not missing and bool(review.get("evidence"))}


def choose_solver(text):
    """Rank suggestions; the agent confirms actual geometry and available APIs."""
    text=text.lower()
    rules=[("CHARGE",["carrier transport","drift-diffusion","poisson"]),
           ("HEAT",["temperature field","heat conduction","thermal boundary"]),
           ("MODE",["effective index","waveguide mode","dispersion","fde"]),
           ("FDTD",["maxwell","scattering","electromagnetic field","photonic crystal"]),
           ("INTERCONNECT_SCRIPT",["coupled mode","tcmt","rate equation","self-puls","bifurcation","non-hermitian"]),
           ("INTERCONNECT",["circuit","cascade","network"])]
    scores=[{"solver":n,"score":sum(k in text for k in keys),"evidence":[k for k in keys if k in text]} for n,keys in rules]
    return sorted(scores,key=lambda x:-x["score"])
