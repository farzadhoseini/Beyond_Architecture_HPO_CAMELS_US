#!/usr/bin/env python
"""
CAMELS-US global Rank-1 / Top-1 micro-control.

Goal
----
Decompose the current global benchmark into:
    Kratzert reference -> optimized global Top-1 -> global Top-10 ensemble
and preserve the existing Top-18 / hydrologically informed controls separately.

This script is intentionally conservative:
- no training;
- no test-based model selection;
- global Rank-1 must be established from explicit archived rank evidence OR supplied
  manually with --rank1-source-token;
- Top-10 raw member archive is rebuilt and checked against the frozen Top-10 ensemble;
- the same ten final seeds and the same basin/metric aggregation convention are used.

Expected historical root (default):
    F:\\Experiments\\CAMELS_US\\Clean_4_upload
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import pickle
import re
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

try:
    import yaml
except Exception as e:
    raise SystemExit("PyYAML is required in the active Python environment: pip install pyyaml") from e

try:
    from scipy.stats import wilcoxon, binomtest
except Exception as e:
    raise SystemExit("SciPy is required in the active Python environment: pip install scipy") from e

SEEDS = [191889, 307443, 328237, 385445, 473461, 643969, 665980, 845563, 985957, 993061]
CORE = ["NSE", "KGE", "Pearson-r", "RMSE"]
BOOT_SEED = 20260826
N_BOOT = 10_000
TOKEN_RE = re.compile(r"(?<!\d)(\d{4}_\d{6})(?!\d)")
BASIN_RE = re.compile(r"(?<!\d)(\d{8})(?!\d)")

# Fields sufficient to establish scientific configuration identity while ignoring
# run-specific paths, dates and random seed.
FINGERPRINT_FIELDS = [
    "model", "seq_length", "hidden_size", "initial_forget_bias", "output_dropout",
    "batch_size", "learning_rate", "target_noise_std", "loss", "epochs",
    "dynamic_inputs", "static_attributes", "forcings", "target_variables",
    "clip_targets_to_zero", "predict_last_n",
]


def log(msg: str = "") -> None:
    print(msg, flush=True)


def _install_legacy_pandas_pickle_shims() -> None:
    """Install minimal aliases required by pandas<2 pickles under pandas>=2.

    Older pandas versions serialized numeric Index subclasses from
    ``pandas.core.indexes.numeric``.  pandas 2.x removed that private module
    and consolidated those classes into ``pandas.Index``.  The historical
    CAMELS ensemble pickle may therefore fail to unpickle even though the
    scientific payload is intact.  These aliases affect deserialization only;
    they do not alter any numerical values.
    """
    import types

    module_name = "pandas.core.indexes.numeric"
    if module_name in sys.modules:
        return

    legacy = types.ModuleType(module_name)
    for cls_name in ("NumericIndex", "Int64Index", "UInt64Index", "Float64Index"):
        setattr(legacy, cls_name, pd.Index)
    sys.modules[module_name] = legacy


def load_pickle(path: Path) -> Any:
    log(f"Loading pickle: {path}")
    try:
        with path.open("rb") as f:
            return pickle.load(f)
    except ModuleNotFoundError as exc:
        # Compatibility bridge for historical pandas 1.x Index pickles opened
        # with pandas 2.x.  Retry only for this known private-module migration.
        if exc.name != "pandas.core.indexes.numeric":
            raise
        log("  Legacy pandas numeric-index pickle detected; installing pandas>=2 compatibility shim and retrying.")
        _install_legacy_pandas_pickle_shims()
        with path.open("rb") as f:
            return pickle.load(f)


def read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        x = yaml.safe_load(f)
    return x if isinstance(x, dict) else {}


def norm_obj(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): norm_obj(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple)):
        return [norm_obj(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, Path):
        return str(x)
    if hasattr(x, "isoformat") and not isinstance(x, str):
        try:
            return x.isoformat()
        except Exception:
            pass
    return x


def config_core(cfg: dict) -> dict:
    return {k: norm_obj(cfg.get(k)) for k in FINGERPRINT_FIELDS if k in cfg}


def config_fingerprint(cfg: dict) -> str:
    payload = json.dumps(config_core(cfg), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def token_from_path_or_text(x: Any) -> str | None:
    m = TOKEN_RE.search(str(x))
    return m.group(1) if m else None


def normalize_basin(x: Any) -> str | None:
    s = str(x)
    m = BASIN_RE.search(s)
    if m:
        return m.group(1)
    # support integer basin ids whose leading zero was lost
    if s.isdigit() and 6 <= len(s) <= 8:
        return s.zfill(8)
    return None


def normalize_seed(x: Any) -> int | None:
    try:
        v = int(str(x))
        return v if v in SEEDS else None
    except Exception:
        return None


def is_xarray_obj(x: Any) -> bool:
    return x.__class__.__module__.startswith("xarray")


def is_pandas_obj(x: Any) -> bool:
    return isinstance(x, (pd.Series, pd.DataFrame, pd.Index))


def choose_numeric_column(cols: list[str], role: str) -> str | None:
    low = {c: c.lower() for c in cols}
    if role == "sim":
        keys = ["_sim", "sim", "prediction", "pred", "qsim", "q_sim"]
    else:
        keys = ["_obs", "obs", "observation", "qobs", "q_obs"]
    for k in keys:
        for c, lc in low.items():
            if k in lc:
                return c
    return None


def series_from_obj(obj: Any, role: str) -> np.ndarray | None:
    """Return a 1-D float series from a likely prediction/observation leaf."""
    if obj is None:
        return None
    if isinstance(obj, np.ndarray):
        a = np.asarray(obj)
        if a.size < 100:
            return None
        a = np.squeeze(a)
        if a.ndim == 1:
            return a.astype(float, copy=False)
        if a.ndim == 2 and 1 in a.shape:
            return a.reshape(-1).astype(float, copy=False)
        return None
    if isinstance(obj, pd.Series):
        a = pd.to_numeric(obj, errors="coerce").to_numpy(float)
        return a if a.size >= 100 else None
    if isinstance(obj, pd.DataFrame):
        cols = [str(c) for c in obj.columns]
        c = choose_numeric_column(cols, role)
        if c is None:
            numeric = [cc for cc in obj.columns if pd.api.types.is_numeric_dtype(obj[cc])]
            if len(numeric) == 1:
                c = numeric[0]
        if c is not None:
            a = pd.to_numeric(obj[c], errors="coerce").to_numpy(float)
            return a if a.size >= 100 else None
        return None
    if is_xarray_obj(obj):
        try:
            # Dataset
            if hasattr(obj, "data_vars"):
                names = [str(v) for v in obj.data_vars]
                v = choose_numeric_column(names, role)
                if v is None and len(names) == 1:
                    v = names[0]
                if v is not None:
                    a = np.asarray(obj[v].values)
                    a = np.squeeze(a)
                    if a.ndim == 1 and a.size >= 100:
                        return a.astype(float, copy=False)
            # DataArray
            if hasattr(obj, "values"):
                a = np.squeeze(np.asarray(obj.values))
                if a.ndim == 1 and a.size >= 100:
                    return a.astype(float, copy=False)
        except Exception:
            return None
    return None


def walk_prediction_leaves(obj: Any, path: tuple = ()) -> Iterable[tuple[tuple, np.ndarray]]:
    """Recursively find likely time-series leaves without descending into dataframe/xarray internals."""
    arr = series_from_obj(obj, "sim")
    if arr is not None and not isinstance(obj, dict):
        yield path, arr
        return
    if isinstance(obj, dict):
        # A compact dict may itself contain a sim object; prefer it if explicit.
        for key in ("sim", "simulation", "prediction", "pred", "qsim", "QObs(mm/d)_sim"):
            if key in obj:
                a = series_from_obj(obj[key], "sim")
                if a is not None:
                    yield path + (key,), a
                    return
        for k, v in obj.items():
            yield from walk_prediction_leaves(v, path + (k,))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from walk_prediction_leaves(v, path + (i,))


def extract_ids_from_path(path: tuple, basin_set: set[str] | None = None) -> tuple[str | None, int | None, str | None]:
    basin = None
    seed = None
    token = None
    for p in path:
        if seed is None:
            seed = normalize_seed(p)
        if token is None:
            token = token_from_path_or_text(p)
        if basin is None:
            b = normalize_basin(p)
            if b is not None and (basin_set is None or b in basin_set):
                basin = b
    return basin, seed, token


def load_basin_list(root: Path) -> list[str]:
    candidates = [root / "531_basin_list.txt", root / "camels_531_master_attributes_clusters.csv"]
    for p in candidates:
        if not p.exists():
            continue
        if p.suffix.lower() == ".txt":
            vals = [normalize_basin(x.strip()) for x in p.read_text(errors="ignore").splitlines()]
            vals = [x for x in vals if x]
        else:
            df = pd.read_csv(p)
            col = next((c for c in df.columns if "basin" in c.lower() or "gauge" in c.lower()), None)
            if col is None:
                continue
            vals = [normalize_basin(x) for x in df[col]]
            vals = [x for x in vals if x]
        if len(set(vals)) == 531:
            return sorted(set(vals))
    raise RuntimeError("Could not establish the frozen 531-basin list.")


def extract_member_archive(all_obj: Any, basins: list[str]) -> dict[tuple[str,int,str], np.ndarray]:
    basin_set = set(basins)
    out: dict[tuple[str,int,str], np.ndarray] = {}
    bad = []
    for path, arr in walk_prediction_leaves(all_obj):
        b, s, tok = extract_ids_from_path(path, basin_set)
        if b and s and tok:
            key = (b, s, tok)
            if key in out:
                # identical duplicate is harmless; non-identical is not.
                if out[key].shape != arr.shape or not np.allclose(out[key], arr, equal_nan=True, atol=0, rtol=0):
                    raise RuntimeError(f"Non-identical duplicate prediction leaf for {key}")
            else:
                out[key] = arr
        else:
            if len(bad) < 10:
                bad.append((path, arr.shape))
    if len(out) != 531 * 10 * 10:
        counts = defaultdict(int)
        for b,s,t in out:
            counts[(b,s)] += 1
        vals = list(counts.values())
        raise RuntimeError(
            f"All_Top10 extraction gate failed: extracted {len(out)} leaves; expected 53100. "
            f"basin-seed member counts min/median/max={min(vals) if vals else None}/"
            f"{np.median(vals) if vals else None}/{max(vals) if vals else None}. "
            f"Sample unresolved leaves={bad}"
        )
    return out


def extract_ensemble_archive(obj: Any, basins: list[str]) -> dict[tuple[str,int], np.ndarray]:
    basin_set = set(basins)
    out: dict[tuple[str,int], np.ndarray] = {}
    for path, arr in walk_prediction_leaves(obj):
        b, s, _ = extract_ids_from_path(path, basin_set)
        if b and s:
            key=(b,s)
            if key in out:
                if out[key].shape != arr.shape or not np.allclose(out[key], arr, equal_nan=True, atol=0, rtol=0):
                    raise RuntimeError(f"Non-identical duplicate ensemble leaf for {key}")
            else:
                out[key]=arr
    if len(out) != 531*10:
        raise RuntimeError(f"Top10 ensemble extraction gate failed: {len(out)} series, expected 5310")
    return out


def extract_observations(obj: Any, basins: list[str]) -> dict[str,np.ndarray]:
    basin_set=set(basins)
    out={}
    # First try recursive leaves and treat each leaf as observation.
    def walk_obs(x: Any, path: tuple=()):
        a=series_from_obj(x,"obs")
        if a is not None and not isinstance(x,dict):
            yield path,a; return
        if isinstance(x,dict):
            for key in ("obs","observation","qobs","QObs(mm/d)_obs"):
                if key in x:
                    a=series_from_obj(x[key],"obs")
                    if a is not None:
                        yield path+(key,),a; return
            for k,v in x.items():
                yield from walk_obs(v,path+(k,))
        elif isinstance(x,(list,tuple)):
            for i,v in enumerate(x): yield from walk_obs(v,path+(i,))
    for path,arr in walk_obs(obj):
        b,_,_=extract_ids_from_path(path,basin_set)
        if b and b not in out: out[b]=arr
    if len(out)!=531:
        raise RuntimeError(f"Observation extraction gate failed: {len(out)} basins, expected 531")
    return out


def align(obs: np.ndarray, sim: np.ndarray) -> tuple[np.ndarray,np.ndarray]:
    n=min(len(obs),len(sim))
    o=np.asarray(obs[:n],float); s=np.asarray(sim[:n],float)
    m=np.isfinite(o)&np.isfinite(s)
    return o[m],s[m]


def metrics(obs: np.ndarray, sim: np.ndarray) -> dict[str,float]:
    o,s=align(obs,sim)
    if o.size < 2:
        return {k:np.nan for k in CORE}
    den=np.sum((o-o.mean())**2)
    nse=np.nan if den<=0 else 1.0-np.sum((s-o)**2)/den
    rmse=float(np.sqrt(np.mean((s-o)**2)))
    if np.std(o)==0 or np.std(s)==0:
        r=np.nan
    else:
        r=float(np.corrcoef(o,s)[0,1])
    mo=float(np.mean(o)); ms=float(np.mean(s))
    alpha=float(np.std(s,ddof=0)/np.std(o,ddof=0)) if np.std(o,ddof=0)>0 else np.nan
    beta=float(ms/mo) if mo!=0 else np.nan
    kge=float(1.0-np.sqrt((r-1)**2+(alpha-1)**2+(beta-1)**2)) if np.all(np.isfinite([r,alpha,beta])) else np.nan
    return {"NSE":float(nse),"KGE":kge,"Pearson-r":r,"RMSE":rmse}


def bh_fdr(pvals: list[float]) -> list[float]:
    p=np.asarray(pvals,float)
    out=np.full_like(p,np.nan)
    good=np.isfinite(p)
    idx=np.where(good)[0]
    if idx.size==0: return out.tolist()
    order=idx[np.argsort(p[idx])]
    m=len(order); q=np.empty(m,float)
    prev=1.0
    for j in range(m-1,-1,-1):
        rank=j+1
        val=min(prev,p[order[j]]*m/rank)
        q[j]=val; prev=val
    for j,i in enumerate(order): out[i]=min(q[j],1.0)
    return out.tolist()


def bootstrap_ci_median(x: np.ndarray) -> tuple[float,float]:
    x=np.asarray(x,float); x=x[np.isfinite(x)]
    rng=np.random.default_rng(BOOT_SEED)
    meds=np.empty(N_BOOT,float)
    n=len(x)
    for i in range(N_BOOT):
        meds[i]=np.median(x[rng.integers(0,n,n)])
    return tuple(np.percentile(meds,[2.5,97.5]).tolist())


def paired_stats(df: pd.DataFrame, first: str, ref: str) -> pd.DataFrame:
    rows=[]
    pvals=[]
    temp=[]
    for met in CORE:
        a=df.loc[df.method==first,["basin",met]].rename(columns={met:"a"})
        b=df.loc[df.method==ref,["basin",met]].rename(columns={met:"b"})
        z=a.merge(b,on="basin",how="inner").dropna()
        if met=="RMSE": d=z.b.to_numpy()-z.a.to_numpy()
        else: d=z.a.to_numpy()-z.b.to_numpy()
        nz=d[d!=0]
        wp=float(wilcoxon(nz,alternative="two-sided").pvalue) if len(nz) else 1.0
        pos=int(np.sum(d>0)); neg=int(np.sum(d<0)); ties=int(np.sum(d==0))
        sp=float(binomtest(pos,n=pos+neg,p=0.5,alternative="two-sided").pvalue) if pos+neg else 1.0
        lo,hi=bootstrap_ci_median(d)
        row=dict(comparison=f"{first} vs {ref}", metric=met, n=len(d), wins=pos, losses=neg, ties=ties,
                 win_rate=pos/len(d), mean_effect=float(np.mean(d)), median_effect=float(np.median(d)),
                 ci95_lo=lo, ci95_hi=hi, wilcoxon_p=wp, sign_p=sp)
        temp.append(row); pvals.append(wp)
    qs=bh_fdr(pvals)
    for row,q in zip(temp,qs): row["wilcoxon_fdr_p"]=q; rows.append(row)
    return pd.DataFrame(rows)


def scan_configs(root: Path, prediction_tokens: set[str]) -> pd.DataFrame:
    search_roots=[root/"Models", root/"Revision_2026_Top18_4Framework"]
    rows=[]
    seen=set()
    for sr in search_roots:
        if not sr.exists(): continue
        for p in sr.rglob("config.y*ml"):
            tok=token_from_path_or_text(p)
            if tok not in prediction_tokens: continue
            key=str(p.resolve()).lower()
            if key in seen: continue
            seen.add(key)
            try:
                cfg=read_yaml(p); fp=config_fingerprint(cfg)
                seed=cfg.get("seed")
                try: seed=int(seed)
                except Exception: seed=None
                rows.append({"prediction_token":tok,"seed":seed,"fingerprint":fp,"config_path":str(p),
                             "core_json":json.dumps(config_core(cfg),sort_keys=True,ensure_ascii=False,default=str)})
            except Exception as e:
                rows.append({"prediction_token":tok,"seed":None,"fingerprint":None,"config_path":str(p),"error":str(e)})
    if not rows: raise RuntimeError("No run config.yml files could be mapped to All_Top10 prediction tokens.")
    df=pd.DataFrame(rows)
    # collapse equivalent copies per token; ambiguous fingerprints are fatal
    amb=df.dropna(subset=["fingerprint"]).groupby("prediction_token").fingerprint.nunique()
    bad=amb[amb>1]
    if len(bad): raise RuntimeError(f"Ambiguous scientific config identity for tokens: {bad.index.tolist()[:10]}")
    first=df.sort_values("config_path").drop_duplicates(["prediction_token","fingerprint"])
    return first


def discover_rank1(root: Path, token_cfg: pd.DataFrame, manual_token: str | None, out: Path) -> tuple[str,str,str]:
    """Return (rank1_source_token, rank1_fingerprint, evidence)."""
    if manual_token:
        hits=token_cfg[token_cfg.prediction_token==manual_token]
        if hits.empty:
            # Manual may be a source token not present among final run tokens; find its config on disk.
            paths=list((root/"Models").rglob(f"*{manual_token}*/config.y*ml")) if (root/"Models").exists() else []
            fps=set()
            for p in paths:
                try: fps.add(config_fingerprint(read_yaml(p)))
                except Exception: pass
            if len(fps)!=1: raise RuntimeError(f"Manual rank1 token {manual_token} maps to {len(fps)} fingerprints; expected 1.")
            fp=next(iter(fps))
        else:
            fps=set(hits.fingerprint.dropna())
            if len(fps)!=1: raise RuntimeError(f"Manual rank1 token {manual_token} ambiguous in mapped configs.")
            fp=next(iter(fps))
        return manual_token,fp,"manual --rank1-source-token"

    # Scan likely small rank/selection/manifest files. Do not infer from row order.
    roots=[root, root.parent/"New_experiments", Path(r"D:\research\CAMELS_US_paper")]
    candidates=[]
    for sr in roots:
        if not sr.exists(): continue
        for p in sr.rglob("*"):
            if not p.is_file() or p.stat().st_size>20_000_000: continue
            nm=p.name.lower()
            if not any(k in nm for k in ("rank","manifest","select","top10","top18","configs")): continue
            if p.suffix.lower() not in (".csv",".tsv",".xlsx",".xls",".json",".txt",".md"): continue
            candidates.append(p)
    evidence=[]
    for p in candidates:
        try:
            tables=[]
            suf=p.suffix.lower()
            if suf in (".xlsx",".xls"):
                xls=pd.ExcelFile(p)
                for sh in xls.sheet_names:
                    try: tables.append((sh,pd.read_excel(p,sheet_name=sh)))
                    except Exception: pass
            elif suf in (".csv",".tsv"):
                sep="\t" if suf==".tsv" else ","
                tables.append(("",pd.read_csv(p,sep=sep,engine="python")))
            elif suf==".json":
                x=json.loads(p.read_text(encoding="utf-8",errors="replace"))
                if isinstance(x,list): tables.append(("",pd.DataFrame(x)))
                elif isinstance(x,dict):
                    try: tables.append(("",pd.DataFrame(x)))
                    except Exception: pass
            else:
                txt=p.read_text(encoding="utf-8",errors="replace")
                # Explicit rank-1 textual evidence: require rank and token on same line.
                for ln_no,line in enumerate(txt.splitlines(),1):
                    if re.search(r"\brank\s*[_:= -]*0*1\b",line,re.I):
                        toks=TOKEN_RE.findall(line)
                        for tok in toks: evidence.append((tok,str(p),f"line {ln_no}: {line[:400]}"))
            for sh,df in tables:
                if df.empty: continue
                cols=[str(c) for c in df.columns]
                rank_cols=[c for c in cols if "rank" in c.lower()]
                if not rank_cols: continue
                for rc in rank_cols:
                    rr=pd.to_numeric(df[rc],errors="coerce")
                    sub=df.loc[rr==1]
                    for idx,row in sub.iterrows():
                        toks=[]
                        for v in row.values:
                            toks.extend(TOKEN_RE.findall(str(v)))
                        for tok in toks:
                            evidence.append((tok,str(p),f"sheet={sh}; rank_col={rc}; row={idx}"))
        except Exception:
            continue
    evdf=pd.DataFrame(evidence,columns=["rank1_token_candidate","evidence_path","evidence_detail"]).drop_duplicates()
    evdf.to_csv(out/"00_rank1_manifest_evidence_candidates.csv",index=False)
    mapped=[]
    for tok,path,detail in evidence:
        # First direct final-token mapping
        hits=token_cfg[token_cfg.prediction_token==tok]
        fps=set(hits.fingerprint.dropna())
        # Else locate source token config anywhere under Models
        if not fps and (root/"Models").exists():
            for cp in (root/"Models").rglob("config.y*ml"):
                if tok in str(cp):
                    try: fps.add(config_fingerprint(read_yaml(cp)))
                    except Exception: pass
        if len(fps)==1:
            fp=next(iter(fps))
            # Require that fingerprint is represented in AllTop10 archive.
            if fp in set(token_cfg.fingerprint.dropna()):
                mapped.append((tok,fp,path,detail))
    if mapped:
        fps={x[1] for x in mapped}
        if len(fps)==1:
            tok,fp,path,detail=mapped[0]
            return tok,fp,f"auto evidence: {path}; {detail}"
        pd.DataFrame(mapped,columns=["token","fingerprint","path","detail"]).to_csv(out/"00_rank1_AMBIGUOUS.csv",index=False)
        raise RuntimeError("Multiple different Top10 fingerprints were found as Rank-1 in archived evidence. See 00_rank1_AMBIGUOUS.csv")
    raise RuntimeError(
        "Could not establish global Rank-1 from explicit archived rank evidence. "
        "No test-based or positional guess was made. Inspect 00_rank1_manifest_evidence_candidates.csv, "
        "then rerun with --rank1-source-token TOKEN once the validation-ranked source token is verified."
    )


def audit_inputs(token_cfg: pd.DataFrame, out: Path) -> dict:
    cfgs=[]
    for p in token_cfg.config_path.dropna().unique():
        try: cfgs.append((p,read_yaml(Path(p))))
        except Exception: pass
    if not cfgs: raise RuntimeError("No readable configs for input audit")
    fields=["dataset","dynamic_inputs","static_attributes","forcings","target_variables","clip_targets_to_zero","train_data_file"]
    audit=[]
    result={}
    for fld in fields:
        vals=[]
        for p,c in cfgs:
            if fld in c: vals.append(json.dumps(norm_obj(c[fld]),ensure_ascii=False,sort_keys=True,default=str))
        uniq=sorted(set(vals))
        audit.append({"field":fld,"n_configs":len(cfgs),"n_unique_values":len(uniq),"value":uniq[0] if len(uniq)==1 else " || ".join(uniq[:5])})
        result[fld]=json.loads(uniq[0]) if len(uniq)==1 else None
    pd.DataFrame(audit).to_csv(out/"01_input_configuration_consistency.csv",index=False)
    if any(r["n_unique_values"]!=1 for r in audit if r["field"] in ["dynamic_inputs","static_attributes","forcings","target_variables"]):
        raise RuntimeError("Input-configuration consistency gate failed. See 01_input_configuration_consistency.csv")
    # manuscript-friendly exact list
    with (out/"01_input_configuration_MANUSCRIPT.txt").open("w",encoding="utf-8") as f:
        f.write("FIXED INPUT / TARGET CONFIGURATION\n\n")
        f.write(f"Dataset: {result.get('dataset')}\n")
        f.write(f"Forcing products: {result.get('forcings')}\n")
        f.write("Dynamic inputs (ordered):\n")
        for i,v in enumerate(result.get("dynamic_inputs") or [],1): f.write(f"  {i:02d}. {v}\n")
        f.write("\nStatic attributes (ordered):\n")
        for i,v in enumerate(result.get("static_attributes") or [],1): f.write(f"  {i:02d}. {v}\n")
        f.write(f"\nTarget: {result.get('target_variables')}\n")
        f.write(f"clip_targets_to_zero: {result.get('clip_targets_to_zero')}\n")
        f.write(f"train_data_file: {result.get('train_data_file')}\n")
        f.write("\nNormalization statement already documented in manuscript: dynamic-input normalization is estimated from the training period and applied unchanged to validation and test data.\n")
        f.write("Static-attribute scaling should be described only as supported by the frozen preprocessing/scaler metadata; this script does not infer an undocumented scaler rule.\n")
    return result


def build_top10_median(member: dict, basins:list[str]) -> dict[tuple[str,int],np.ndarray]:
    buckets=defaultdict(list)
    for (b,s,t),a in member.items(): buckets[(b,s)].append(a)
    out={}
    counts=[]
    for key,arrs in buckets.items():
        counts.append(len(arrs))
        if len(arrs)!=10: raise RuntimeError(f"Top10 member count !=10 for {key}: {len(arrs)}")
        lens={len(a) for a in arrs}
        if len(lens)!=1: raise RuntimeError(f"Top10 time-series length mismatch for {key}")
        out[key]=np.nanmedian(np.stack(arrs,axis=0),axis=0)
    if len(out)!=5310 or min(counts)!=10 or max(counts)!=10:
        raise RuntimeError("Top10 rebuild member gate failed")
    return out


def compare_series_dict(a:dict,b:dict) -> tuple[float,float,int]:
    mx=0.0; means=[]; n=0
    for k in sorted(set(a)&set(b)):
        x,y=a[k],b[k]; m=min(len(x),len(y)); x=x[:m]; y=y[:m]
        d=np.abs(x-y); d=d[np.isfinite(d)]
        if d.size:
            mx=max(mx,float(d.max())); means.append(float(d.mean())); n+=1
    return mx,float(np.mean(means)) if means else np.nan,n


def primary_metrics(method_series:dict[str,dict[tuple[str,int],np.ndarray]], obs:dict[str,np.ndarray]) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows=[]
    for method,series in method_series.items():
        for (b,s),sim in series.items():
            mm=metrics(obs[b],sim)
            rows.append({"method":method,"basin":b,"seed":s,**mm})
    seed_df=pd.DataFrame(rows)
    agg=seed_df.groupby(["method","basin"],as_index=False)[CORE].agg(["mean","median"])
    agg.columns=["method","basin"]+[f"{m}_{a}" for m,a in agg.columns.tolist()[2:]] if False else agg.columns
    # pandas MultiIndex-safe reshape
    mean_df=seed_df.groupby(["method","basin"],as_index=False)[CORE].mean()
    med_df=seed_df.groupby(["method","basin"],as_index=False)[CORE].median()
    med_df=med_df.rename(columns={m:f"{m}_seedmedian" for m in CORE})
    basin=mean_df.merge(med_df,on=["method","basin"],how="left")
    return seed_df,basin


def absolute_summary(basin_mean:pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for method,g in basin_mean.groupby("method"):
        for met in CORE:
            x=g[met].to_numpy(float)
            rows.append({"method":method,"metric":met,"n":np.isfinite(x).sum(),"across_basin_mean":np.nanmean(x),"across_basin_median":np.nanmedian(x),"q25":np.nanpercentile(x,25),"q75":np.nanpercentile(x,75)})
    return pd.DataFrame(rows)


def seed_regional(seed_df:pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for (method,seed),g in seed_df.groupby(["method","seed"]):
        r={"method":method,"seed":seed}
        for met in CORE:
            x=g[met].to_numpy(float); r[f"{met}_mean"]=np.nanmean(x); r[f"{met}_median"]=np.nanmedian(x)
        rows.append(r)
    return pd.DataFrame(rows)


def extract_baseline_metrics_pickle(path:Path, basins:list[str]) -> pd.DataFrame | None:
    """Best-effort scalar-path parser for legacy metrics_all_test_period.p."""
    try: obj=load_pickle(path)
    except Exception: return None
    basin_set=set(basins); rows=[]
    method_aliases=("benchmark","kratzert","reference")
    metric_alias={"nse":"NSE","kge":"KGE","pearson-r":"Pearson-r","pearson_r":"Pearson-r","pearson":"Pearson-r","r":"Pearson-r","rmse":"RMSE"}
    def walk(x,path=()):
        if isinstance(x,dict):
            for k,v in x.items(): yield from walk(v,path+(k,))
        elif isinstance(x,(list,tuple)):
            for i,v in enumerate(x): yield from walk(v,path+(i,))
        elif np.isscalar(x) and not isinstance(x,(str,bytes,bool)):
            yield path,x
    for path,val in walk(obj):
        txt="/".join(map(str,path)).lower()
        if not any(a in txt for a in method_aliases): continue
        basin=None; seed=None; met=None
        for p in path:
            if basin is None:
                b=normalize_basin(p)
                if b in basin_set: basin=b
            if seed is None: seed=normalize_seed(p)
            lp=str(p).lower().strip()
            for a,m in metric_alias.items():
                if lp==a or a in lp: met=m
        if basin and met:
            try: vv=float(val)
            except Exception: continue
            rows.append({"basin":basin,"seed":seed,"metric":met,"value":vv})
    if not rows: return None
    d=pd.DataFrame(rows).drop_duplicates()
    # Prefer 10-seed values; otherwise accept already-aggregated basin metrics.
    out=[]
    for (b,m),g in d.groupby(["basin","metric"]):
        if g.seed.notna().sum()>=10:
            vals=g.dropna(subset=["seed"]).drop_duplicates("seed").value.to_numpy(float)
            v=float(np.mean(vals))
        else:
            vals=g.value.to_numpy(float)
            if len(vals)!=1: continue
            v=float(vals[0])
        out.append({"method":"Kratzert","basin":b,m:v})
    if not out: return None
    # pivot safely
    records=defaultdict(dict)
    for r in out:
        records[r["basin"]][r["metric"]]=r[r["metric"]]
    df=pd.DataFrame([{"method":"Kratzert","basin":b,**vals} for b,vals in records.items()])
    if len(df)!=531 or "NSE" not in df: return None
    return df



def load_canonical_kratzert(root: Path, basins: list[str]) -> pd.DataFrame | None:
    """Load the frozen canonical 10-seed Kratzert basin metrics if present."""
    candidates = [
        root / "Revision_2026_Top18_4Framework" / "Top18_vs_Top10_Final_Analysis" /
        "CANONICAL_MEANSEED_REAGGREGATION" / "01_basin_mean_across_10_seeds.csv",
        root / "Revision_2026_Top18_4Framework" / "Top18_vs_Top10_Final_Analysis" /
        "CANONICAL_MEANSEED_REAGGREGATION" / "01_basin_mean_across_10_seeds.csv",
    ]
    basin_set=set(basins)
    for p in candidates:
        if not p.exists():
            continue
        try:
            d=pd.read_csv(p)
        except Exception:
            continue
        need={"basin","method","metric","basin_seed_mean"}
        if not need.issubset(d.columns):
            continue
        # Historical canonical table uses Benchmark for Kratzert.
        k=d[d["method"].astype(str).str.lower().isin(["benchmark","kratzert","kratzert reference","reference"])].copy()
        if k.empty:
            continue
        k["basin"]=k["basin"].map(normalize_basin)
        k=k[k["basin"].isin(basin_set)]
        piv=k.pivot_table(index="basin",columns="metric",values="basin_seed_mean",aggfunc="first").reset_index()
        if len(piv)!=531 or "NSE" not in piv.columns:
            continue
        aliases={"Pearson_r":"Pearson-r","Pearson":"Pearson-r"}
        piv=piv.rename(columns=aliases)
        for m in CORE:
            if m not in piv.columns:
                piv[m]=np.nan
        piv.insert(0,"method","Kratzert")
        mean=float(piv["NSE"].mean()); med=float(piv["NSE"].median())
        if abs(mean-0.753311)<=0.0015 and abs(med-0.792028)<=0.0015:
            return piv[["method","basin"]+CORE]
    # Fallback to legacy metrics pickle parser.
    p=root/"Pickles"/"metrics_all_test_period.p"
    if p.exists():
        kr=extract_baseline_metrics_pickle(p,basins)
        if kr is not None and len(kr)==531:
            mean=float(kr.NSE.mean()); med=float(kr.NSE.median())
            if abs(mean-0.753311)<=0.003 and abs(med-0.792028)<=0.003:
                for m in CORE:
                    if m not in kr.columns: kr[m]=np.nan
                return kr[["method","basin"]+CORE]
    return None


def global_bh_add(df: pd.DataFrame, pcol: str="wilcoxon_p", outcol: str="wilcoxon_global_fdr_p") -> pd.DataFrame:
    z=df.copy()
    z[outcol]=bh_fdr(z[pcol].tolist())
    return z


def config_table(token_cfg: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    fps=sorted(token_cfg.fingerprint.dropna().unique())
    for i,fp in enumerate(fps,1):
        g=token_cfg[token_cfg.fingerprint==fp]
        core=json.loads(g.core_json.dropna().iloc[0])
        seeds=sorted({int(x) for x in g.seed.dropna().astype(int)})
        rows.append({
            "constituent_id":f"CFG-{i:02d}",
            "fingerprint":fp,
            "short_fingerprint":fp[:12],
            "n_prediction_tokens":g.prediction_token.nunique(),
            "n_seeds":len(seeds),
            "seeds":"|".join(map(str,seeds)),
            "seq_length":core.get("seq_length"),
            "hidden_size":core.get("hidden_size"),
            "initial_forget_bias":core.get("initial_forget_bias"),
            "output_dropout":core.get("output_dropout"),
            "batch_size":core.get("batch_size"),
            "lr0":(core.get("learning_rate") or {}).get("0"),
            "lr10":(core.get("learning_rate") or {}).get("10"),
            "lr25":(core.get("learning_rate") or {}).get("25"),
            "target_noise_std":core.get("target_noise_std"),
            "loss":core.get("loss"),
        })
    return pd.DataFrame(rows)


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=r"F:\Experiments\CAMELS_US\Clean_4_upload")
    ap.add_argument("--out",default=None)
    args=ap.parse_args()
    root=Path(args.root)
    out=Path(args.out) if args.out else root/"Revision_2026_Top18_4Framework"/"TOP10_CONSTITUENT_DECOMPOSITION_FINAL"
    out.mkdir(parents=True,exist_ok=True)
    log("="*92)
    log("CAMELS-US TOP-10 CONSTITUENT DECOMPOSITION — PUBLICATION-GRADE READ-ONLY ANALYSIS")
    log("No training. No test-based model selection. Global Rank-1 identity is NOT required.")
    log("="*92)
    log(f"ROOT: {root}")
    log(f"OUT : {out}")
    try:
        basins=load_basin_list(root); log(f"BASIN GATE: PASS ({len(basins)})")
        pdir=root/"Pickles"
        p_all=pdir/"All_Top10_Configs_CAMELSUS_test.p"
        p_ens=pdir/"ensemble_Top10_CAMELSUS_test.p"
        p_obs=pdir/"Obs_test.p"
        for p in (p_all,p_ens,p_obs):
            if not p.exists(): raise FileNotFoundError(p)

        all_obj=load_pickle(p_all); ens_obj=load_pickle(p_ens); obs_obj=load_pickle(p_obs)
        members=extract_member_archive(all_obj,basins)
        ensemble=extract_ensemble_archive(ens_obj,basins)
        obs=extract_observations(obs_obj,basins)
        log("ARCHIVE STRUCTURE GATE: PASS (531 basins x 10 seeds x 10 Top10 members)")

        rebuilt=build_top10_median(members,basins)
        mx,md,n=compare_series_dict(rebuilt,ensemble)
        max_tol=1.0e-5; mean_tol=1.0e-7
        log(f"TOP10 REBUILD GATE: n={n}, max_abs_diff={mx:.9g}, mean_abs_diff={md:.9g}; tolerances max<={max_tol:.1e}, mean<={mean_tol:.1e}")
        if n!=5310 or mx>max_tol or md>mean_tol:
            raise RuntimeError("Frozen Top10 ensemble does not match the member-wise pointwise median within legacy float precision tolerance.")
        log("TOP10 REBUILD GATE: PASS")

        tokens={t for _,_,t in members}
        token_cfg=scan_configs(root,tokens)
        token_cfg.to_csv(out/"02_prediction_token_config_map.csv",index=False)
        fp_by_token=token_cfg.dropna(subset=["fingerprint"]).drop_duplicates("prediction_token").set_index("prediction_token")["fingerprint"].to_dict()
        missing=sorted(tokens-set(fp_by_token))
        if missing: raise RuntimeError(f"CONFIG IDENTITY GATE failed; missing fingerprints for {len(missing)} tokens")
        fps=sorted(set(fp_by_token.values()))
        if len(fps)!=10: raise RuntimeError(f"Expected 10 unique scientific configurations; found {len(fps)}")
        log("CONFIG IDENTITY GATE: PASS (100 final-run tokens -> 10 unique scientific configurations)")

        inputs=audit_inputs(token_cfg,out)
        log(f"INPUT CONFIG GATE: PASS; dynamic={len(inputs.get('dynamic_inputs') or [])}, static={len(inputs.get('static_attributes') or [])}, forcings={inputs.get('forcings')}")

        ctab=config_table(token_cfg)
        ctab.to_csv(out/"03_unique_scientific_configurations.csv",index=False)
        fp_to_id=dict(zip(ctab.fingerprint,ctab.constituent_id))
        # IDs are identifiers only, sorted by fingerprint; never validation/test ranks.

        method_series={"Top-10":ensemble}
        member_gate=[]
        for fp in fps:
            cid=fp_to_id[fp]
            tokset={t for t,x in fp_by_token.items() if x==fp}
            seeds={s for t,s in zip(token_cfg.prediction_token,token_cfg.seed) if t in tokset and pd.notna(s)}
            single={(b,s):a for (b,s,t),a in members.items() if t in tokset}
            cnt=defaultdict(int)
            for (b,s,t) in members:
                if t in tokset: cnt[(b,s)]+=1
            vals=set(cnt.values()) if cnt else set()
            member_gate.append({"constituent_id":cid,"fingerprint":fp,"n_tokens":len(tokset),"n_seed_ids":len(seeds),"n_basin_seed_series":len(single),"min_members":min(vals) if vals else np.nan,"max_members":max(vals) if vals else np.nan})
            if len(tokset)!=10 or len(seeds)!=10 or len(single)!=5310 or vals!={1}:
                raise RuntimeError(f"CONSTITUENT MEMBER GATE failed for {cid}: tokens={len(tokset)}, seeds={len(seeds)}, series={len(single)}, member_counts={vals}")
            method_series[cid]=single
        pd.DataFrame(member_gate).to_csv(out/"03_constituent_member_gate.csv",index=False)
        log("CONSTITUENT MEMBER GATE: PASS (10 configurations x 10 seeds; exactly one prediction per basin-seed for each constituent)")

        seed_df,basin_df=primary_metrics(method_series,obs)
        seed_df.to_csv(out/"04_seed_level_metrics_top10_and_constituents.csv",index=False)
        basin_df.to_csv(out/"05_basin_mean_across_10_seeds_top10_and_constituents.csv",index=False)

        top10=basin_df[basin_df.method=="Top-10"]
        tmean=float(top10.NSE.mean()); tmed=float(top10.NSE.median())
        log(f"TOP10 METRIC SELF-CHECK: mean NSE={tmean:.6f}; median NSE={tmed:.6f}")
        if abs(tmean-0.769031)>0.002 or abs(tmed-0.812214)>0.002:
            raise RuntimeError("Top10 metric self-check deviates from frozen manuscript values")

        kr=load_canonical_kratzert(root,basins)
        if kr is not None:
            kr_status="PASS_CANONICAL"
            log(f"KRATZERT CANONICAL GATE: PASS; mean NSE={kr.NSE.mean():.6f}; median NSE={kr.NSE.median():.6f}")
        else:
            kr_status="NOT_RECOVERED"
            log("KRATZERT CANONICAL GATE: NOT RECOVERED (constituent vs Top10 analysis remains valid)")

        all_basin=basin_df[["method","basin"]+CORE].copy()
        if kr is not None: all_basin=pd.concat([all_basin,kr],ignore_index=True)
        all_basin.to_csv(out/"06_basin_primary_metrics_all_methods.csv",index=False)
        absum=absolute_summary(all_basin)
        absum.to_csv(out/"07_absolute_summary.csv",index=False)

        # Top10 versus every constituent: same members/seeds, ensemble is first method.
        topstats=[]
        for fp in fps:
            cid=fp_to_id[fp]
            z=paired_stats(all_basin,"Top-10",cid)
            z.insert(1,"constituent_id",cid)
            z.insert(2,"fingerprint",fp)
            topstats.append(z)
        topstats=pd.concat(topstats,ignore_index=True)
        topstats=global_bh_add(topstats)
        topstats.to_csv(out/"08_top10_vs_each_constituent_core_stats.csv",index=False)

        krstats=None
        if kr is not None:
            tmp=[]
            for fp in fps:
                cid=fp_to_id[fp]
                z=paired_stats(all_basin,cid,"Kratzert")
                z.insert(1,"constituent_id",cid)
                z.insert(2,"fingerprint",fp)
                tmp.append(z)
            krstats=pd.concat(tmp,ignore_index=True)
            krstats=global_bh_add(krstats)
            krstats.to_csv(out/"09_each_constituent_vs_kratzert_core_stats.csv",index=False)

        seed_regional(seed_df).to_csv(out/"10_seed_level_regional_summary.csv",index=False)

        # Descriptive constituent NSE table.
        ns=absum[(absum.metric=="NSE") & absum.method.str.startswith("CFG-")].copy()
        ns=ns.merge(ctab[["constituent_id","fingerprint","short_fingerprint"]],left_on="method",right_on="constituent_id",how="left")
        ns=ns.sort_values("method")
        ns.to_csv(out/"11_constituent_NSE_summary.csv",index=False)
        ens_nse=topstats[topstats.metric=="NSE"].copy().sort_values("constituent_id")
        kr_nse=krstats[krstats.metric=="NSE"].copy().sort_values("constituent_id") if krstats is not None else None

        summary={
            "status":"PASS",
            "design":"All ten validation-selected Top-10 constituent configurations evaluated individually across the same 10 final seeds; no test-based choice among constituents.",
            "constituent_ids_are_ranks":False,
            "n_constituents":10,
            "top10_mean_nse":tmean,"top10_median_nse":tmed,
            "constituent_across_basin_mean_nse_min":float(ns.across_basin_mean.min()),
            "constituent_across_basin_mean_nse_median":float(ns.across_basin_mean.median()),
            "constituent_across_basin_mean_nse_max":float(ns.across_basin_mean.max()),
            "constituent_across_basin_median_nse_min":float(ns.across_basin_median.min()),
            "constituent_across_basin_median_nse_median":float(ns.across_basin_median.median()),
            "constituent_across_basin_median_nse_max":float(ns.across_basin_median.max()),
            "n_constituents_top10_positive_median_paired_NSE":int((ens_nse.median_effect>0).sum()),
            "n_constituents_top10_winrate_over_50_NSE":int((ens_nse.win_rate>0.5).sum()),
            "kratzert_status":kr_status,
            "dynamic_input_count":len(inputs.get("dynamic_inputs") or []),
            "static_attribute_count":len(inputs.get("static_attributes") or []),
            "forcings":inputs.get("forcings")
        }
        if kr is not None:
            summary.update({
                "kratzert_mean_nse":float(kr.NSE.mean()),"kratzert_median_nse":float(kr.NSE.median()),
                "n_constituents_mean_nse_above_kratzert":int((ns.across_basin_mean>float(kr.NSE.mean())).sum()),
                "n_constituents_median_nse_above_kratzert":int((ns.across_basin_median>float(kr.NSE.median())).sum()),
                "n_constituents_positive_median_paired_NSE_vs_kratzert":int((kr_nse.median_effect>0).sum()),
                "n_constituents_winrate_over_50_NSE_vs_kratzert":int((kr_nse.win_rate>0.5).sum()),
            })
        (out/"RUN_SUMMARY.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")

        with (out/"MANUSCRIPT_READY.txt").open("w",encoding="utf-8") as f:
            f.write("CAMELS-US TOP-10 CONSTITUENT DECOMPOSITION — MANUSCRIPT READY\n")
            f.write("="*82+"\n\n")
            f.write("DESIGN\n")
            f.write("All ten validation-selected configurations that constitute global Top-10 are evaluated individually, each across the same 10 final random seeds. No constituent is chosen from test-period performance and no global Rank-1 identity is required. CFG-01...CFG-10 are arbitrary fingerprint-sorted identifiers, NOT validation ranks.\n\n")
            f.write("PRIMARY AGGREGATION\nMetric per basin x seed; arithmetic mean across the 10 seed-level metric values for each basin. The frozen Top-10 ensemble remains the pointwise median of the same ten configurations within each seed.\n\n")
            f.write(f"Top-10 ensemble: mean NSE={tmean:.6f}; median NSE={tmed:.6f}\n")
            f.write(f"Ten individual optimized constituents, across-basin mean NSE range={ns.across_basin_mean.min():.6f} to {ns.across_basin_mean.max():.6f}; median across configurations={ns.across_basin_mean.median():.6f}\n")
            f.write(f"Ten individual optimized constituents, across-basin median NSE range={ns.across_basin_median.min():.6f} to {ns.across_basin_median.max():.6f}; median across configurations={ns.across_basin_median.median():.6f}\n")
            f.write(f"Top-10 has positive median paired NSE effect versus {int((ens_nse.median_effect>0).sum())}/10 individual constituents; basin win rate >50% versus {int((ens_nse.win_rate>0.5).sum())}/10.\n")
            if kr is not None:
                f.write(f"Kratzert reference: mean NSE={kr.NSE.mean():.6f}; median NSE={kr.NSE.median():.6f}\n")
                f.write(f"Individual constituents with across-basin mean NSE above Kratzert: {int((ns.across_basin_mean>float(kr.NSE.mean())).sum())}/10\n")
                f.write(f"Individual constituents with across-basin median NSE above Kratzert: {int((ns.across_basin_median>float(kr.NSE.median())).sum())}/10\n")
                f.write(f"Individual constituents with positive median paired NSE effect vs Kratzert: {int((kr_nse.median_effect>0).sum())}/10\n")
                f.write(f"Individual constituents with basin win rate >50% vs Kratzert: {int((kr_nse.win_rate>0.5).sum())}/10\n")
            else:
                f.write("Kratzert canonical basin table was not recovered automatically; left-side comparison is omitted rather than guessed.\n")
            f.write("\nCONSTITUENT NSE ABSOLUTE SUMMARY\n")
            f.write(ns[["method","short_fingerprint","across_basin_mean","across_basin_median","q25","q75"]].to_string(index=False,float_format=lambda x:f"{x:.6f}")+"\n")
            f.write("\nTOP-10 VS EACH CONSTITUENT — NSE\n")
            f.write(ens_nse[["constituent_id","win_rate","mean_effect","median_effect","ci95_lo","ci95_hi","wilcoxon_p","wilcoxon_fdr_p","wilcoxon_global_fdr_p"]].to_string(index=False,float_format=lambda x:f"{x:.8g}")+"\n")
            if kr_nse is not None:
                f.write("\nEACH CONSTITUENT VS KRATZERT — NSE\n")
                f.write(kr_nse[["constituent_id","win_rate","mean_effect","median_effect","ci95_lo","ci95_hi","wilcoxon_p","wilcoxon_fdr_p","wilcoxon_global_fdr_p"]].to_string(index=False,float_format=lambda x:f"{x:.8g}")+"\n")
            f.write("\nINTERPRETATION RULE\n")
            f.write("This control separates two questions without identifying a test-selected single winner: (1) whether validation-selected optimized individual configurations already improve on the external regional reference, and (2) how much the fixed Top-10 median ensemble improves over its own optimized constituents. Do not call any CFG identifier Rank-1.\n")

        log("\n"+"="*92)
        log("FINAL CONSTITUENT DECOMPOSITION GATE: PASS")
        log("="*92)
        log(f"Main result: {out/'MANUSCRIPT_READY.txt'}")
        log(f"Top10-vs-constituent stats: {out/'08_top10_vs_each_constituent_core_stats.csv'}")
        if krstats is not None: log(f"Constituent-vs-Kratzert stats: {out/'09_each_constituent_vs_kratzert_core_stats.csv'}")
        log(f"Input audit: {out/'01_input_configuration_MANUSCRIPT.txt'}")
        return 0
    except Exception as e:
        fail=out/"FAILED.txt"
        fail.write_text(str(e)+"\n\n"+traceback.format_exc(),encoding="utf-8")
        log("\n"+"="*92); log("FINAL CONSTITUENT DECOMPOSITION GATE: STOPPED / NOT SAFE TO INTERPRET"); log("="*92)
        log(str(e)); log(traceback.format_exc())
        log("Stopped safely. No test-based constituent selection was made.")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
