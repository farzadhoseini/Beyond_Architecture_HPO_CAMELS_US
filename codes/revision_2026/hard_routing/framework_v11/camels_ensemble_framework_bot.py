
# -*- coding: utf-8 -*-
"""
CAMELS-US Ensemble Framework Bot - IHCantabria v10
LEGACY FORMAT + F4 XLSX CLUSTER-SLOT MAPPING

Main purpose
------------
1) Rebuild the old Top10 and old cluster-wise median ensembles from the All_* pickles
   using the exact legacy output structure:
       ensemble[basin][seed]["ensemble"] = xarray.DataArray
2) Compare rebuilt medians against the existing submitted-paper median pickles at
   basin + seed + timestep level. New mean/F4/Top18 results are only scientifically
   usable after this validation passes.
3) Save newly built ensemble pickles in the same legacy format, not compact format.
4) Save metrics in legacy-compatible DataFrame pickles/CSVs, including seed-level
   metrics and basin-level seed-mean metrics with SFmean_* columns.

Expected old all-config pickle format
-------------------------------------
All_Top10[seed][basin]["QObs(mm/d)_sim"][model_token] -> xarray.DataArray
All_Cluster_wise[seed][basin]["QObs(mm/d)_sim"][model_token] -> xarray.DataArray

Expected old ensemble pickle format
-----------------------------------
ensemble[basin][seed]["ensemble"] -> xarray.DataArray
"""
from __future__ import annotations

import argparse
import gc
import json
import logging
import math
import os
import pickle
import platform
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import xarray as xr
    XR_AVAILABLE = True
except Exception:
    xr = None
    XR_AVAILABLE = False

try:
    from scipy import signal as scipy_signal
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except Exception:
    scipy_signal = None
    scipy_stats = None
    SCIPY_AVAILABLE = False

LOGGER = logging.getLogger("camels_ensemble_v10")
SIM_KEY = "QObs(mm/d)_sim"
OBS_KEY = "QObs(mm/d)_obs"
SEED_VALUES = ["191889", "307443", "328237", "385445", "473461", "643969", "665980", "845563", "985957", "993061"]
DEFAULT_SEASONS = {"JFM": [1,2,3], "AMJ": [4,5,6], "JAS": [7,8,9], "OND": [10,11,12]}
LEGACY_METRICS = ["NSE", "KGE", "MSE", "RMSE", "Alpha-NSE", "Beta-KGE", "Beta-NSE", "Pearson-r", "FHV", "FMS", "FLV", "Peak-Timing", "Missed-Peaks", "Peak-MAPE", "MAPE"]

# -----------------------------------------------------------------------------
# Compatibility / IO
# -----------------------------------------------------------------------------
def install_pandas_pickle_compat() -> None:
    """Allow pandas-1.x pickles to load under pandas-2.x."""
    import types
    import pandas as _pd
    modules = [
        "pandas.core.indexes.numeric",
        "pandas.core.indexes.base",
        "pandas.core.indexes.datetimes",
        "pandas.core.indexes.timedeltas",
        "pandas.core.indexes.period",
    ]
    for name in modules:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    numeric = sys.modules["pandas.core.indexes.numeric"]
    for cls in ["Int64Index", "UInt64Index", "Float64Index"]:
        if not hasattr(numeric, cls):
            setattr(numeric, cls, _pd.Index)


def load_pickle(path: Path) -> Any:
    install_pandas_pickle_compat()
    LOGGER.info("Loading pickle: %s", path)
    t0=time.time()
    with Path(path).open("rb") as f:
        obj = pickle.load(f)
    LOGGER.info("Loaded %s in %.1f s", Path(path).name, time.time()-t0)
    return obj


def save_pickle(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    LOGGER.info("Saved pickle: %s", path)


def write_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


def safe_zfill_basin(x: Any) -> str:
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(8)


def file_info(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {"path": None, "exists": False}
    p=Path(path)
    return {"path": str(p), "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() else None, "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime)) if p.exists() else None}

# -----------------------------------------------------------------------------
# xarray / series extraction
# -----------------------------------------------------------------------------
def is_xarray_obj(x: Any) -> bool:
    return XR_AVAILABLE and (isinstance(x, xr.DataArray) or isinstance(x, xr.Dataset))


def to_dataarray(obj: Any, key_hint: Optional[str] = None) -> Any:
    """Return an xarray.DataArray preserving dims/coords whenever possible."""
    if isinstance(obj, Mapping):
        if "1D" in obj:
            return to_dataarray(obj["1D"], key_hint)
        if key_hint and key_hint in obj:
            return to_dataarray(obj[key_hint], key_hint)
        if "ensemble" in obj:
            return to_dataarray(obj["ensemble"], key_hint)
        for k in [SIM_KEY, OBS_KEY, "sim", "obs", "prediction", "target"]:
            if k in obj:
                return to_dataarray(obj[k], key_hint)
        # fallback: first parseable child
        last_err = None
        for v in obj.values():
            try:
                return to_dataarray(v, key_hint)
            except Exception as e:
                last_err = e
        raise ValueError(f"Could not parse mapping as timeseries. Last error: {last_err}")
    if XR_AVAILABLE and isinstance(obj, xr.Dataset):
        if key_hint and key_hint in obj.data_vars:
            return obj[key_hint]
        if SIM_KEY in obj.data_vars:
            return obj[SIM_KEY]
        if OBS_KEY in obj.data_vars:
            return obj[OBS_KEY]
        return obj[list(obj.data_vars)[0]]
    if XR_AVAILABLE and isinstance(obj, xr.DataArray):
        return obj
    if isinstance(obj, (pd.Series, pd.DataFrame, np.ndarray, list, tuple)):
        arr = np.asarray(obj.select_dtypes(include=[np.number]).iloc[:,0] if isinstance(obj,pd.DataFrame) else obj).squeeze()
        return xr.DataArray(arr, dims=["date"] if arr.ndim==1 else None, name=key_hint or SIM_KEY)
    raise ValueError(f"Unsupported timeseries object: {type(obj)}")


def da_values(da: Any) -> np.ndarray:
    if XR_AVAILABLE and isinstance(da, xr.DataArray):
        return np.asarray(da.values).squeeze().astype(np.float32).reshape(-1)
    return np.asarray(da).squeeze().astype(np.float32).reshape(-1)


def da_dates(da: Any) -> Optional[pd.DatetimeIndex]:
    if not (XR_AVAILABLE and isinstance(da, xr.DataArray)):
        return None
    for c in ["date", "datetime", "time", "Time"]:
        if c in da.coords:
            try:
                vals = pd.to_datetime(np.asarray(da.coords[c].values).squeeze())
                if len(vals) == da_values(da).shape[0]:
                    return pd.DatetimeIndex(vals)
            except Exception:
                pass
    if da.dims:
        d0=da.dims[0]
        if d0 in da.coords:
            try:
                vals=pd.to_datetime(np.asarray(da.coords[d0].values).squeeze())
                if len(vals)==da_values(da).shape[0]:
                    return pd.DatetimeIndex(vals)
            except Exception:
                pass
    return None


def make_ensemble_da(stack: np.ndarray, ref_da: Any, agg: str, n_members: int) -> Any:
    if agg == "median":
        ens = np.nanmedian(stack, axis=0).astype(np.float32)
    elif agg == "mean":
        ens = np.nanmean(stack, axis=0).astype(np.float32)
    else:
        raise ValueError("agg must be median or mean")
    if XR_AVAILABLE and isinstance(ref_da, xr.DataArray):
        vals0 = da_values(ref_da)
        # preserve original shape when possible
        shaped = ens.reshape(np.asarray(ref_da.values).squeeze().shape)
        da = xr.DataArray(shaped, dims=ref_da.squeeze().dims, coords=ref_da.squeeze().coords, name=SIM_KEY, attrs=dict(ref_da.attrs) if ref_da.attrs else {})
    else:
        da = xr.DataArray(ens, dims=["date"], name=SIM_KEY)
    da.attrs.update({"ensemble_agg": agg, "n_members": int(n_members), "legacy_format": True})
    return da

# -----------------------------------------------------------------------------
# Legacy pickle readers/builders
# -----------------------------------------------------------------------------
def get_sim_model_dict(basin_value: Any) -> Optional[Mapping[str, Any]]:
    """Return dict model_token -> prediction for one All_*[seed][basin] item."""
    if not isinstance(basin_value, Mapping):
        return None
    # Old all-config format: basin_value[SIM_KEY][model_token]
    if SIM_KEY in basin_value and isinstance(basin_value[SIM_KEY], Mapping):
        cont = basin_value[SIM_KEY]
        if "1D" not in cont:   # model-token dict, not xarray frequency dict
            return cont
    # Also allow nested 1D -> sim -> model token, but do not stop at QObs key.
    if "1D" in basin_value and isinstance(basin_value["1D"], Mapping):
        one = basin_value["1D"]
        if SIM_KEY in one and isinstance(one[SIM_KEY], Mapping) and "1D" not in one[SIM_KEY]:
            return one[SIM_KEY]
    return None


def iter_old_all_config_predictions(preds_all: Mapping[str, Any], basin_ids: Optional[set[str]]=None):
    """Yield (model_token, seed, basin, pred_obj) from legacy All_* pickle."""
    seeds_seen=0; seed_basin_hits=0; leaves=0; yielded=0; tokens=set()
    for seed, basin_dict in preds_all.items():
        seed_s=str(seed)
        if not isinstance(basin_dict, Mapping):
            continue
        seeds_seen += 1
        for basin, basin_value in basin_dict.items():
            bid=safe_zfill_basin(basin)
            if basin_ids is not None and bid not in basin_ids:
                continue
            seed_basin_hits += 1
            model_dict = get_sim_model_dict(basin_value)
            if not isinstance(model_dict, Mapping):
                continue
            for model_token, pred_obj in model_dict.items():
                leaves += 1
                mt=str(model_token)
                tokens.add(mt)
                yield mt, seed_s, bid, pred_obj
                yielded += 1
    # generator logging happens via caller using inspect_old_all_config_structure


def inspect_old_all_config_structure(preds_all: Mapping[str, Any], basin_ids: Optional[set[str]], label: str, out_csv: Path) -> Dict[str, Any]:
    rows=[]; tokens=set(); counts=[]; seed_count=0; seed_basin_hits=0; leaves=0
    for seed, basin_dict in preds_all.items():
        if not isinstance(basin_dict, Mapping):
            continue
        seed_count += 1
        for basin, basin_value in basin_dict.items():
            bid=safe_zfill_basin(basin)
            if basin_ids is not None and bid not in basin_ids:
                continue
            model_dict=get_sim_model_dict(basin_value)
            n_models=len(model_dict) if isinstance(model_dict, Mapping) else 0
            seed_basin_hits += 1
            leaves += n_models
            counts.append(n_models)
            if isinstance(model_dict, Mapping):
                tokens.update(str(k) for k in model_dict.keys())
            rows.append({"label": label, "seed": str(seed), "basin": bid, "n_model_tokens": n_models, "model_tokens": "|".join(str(k) for k in model_dict.keys()) if isinstance(model_dict, Mapping) else ""})
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    summary={
        "label": label,
        "seeds": seed_count,
        "seed_basin_hits": seed_basin_hits,
        "leaves": leaves,
        "unique_model_tokens": len(tokens),
        "n_models_per_seed_basin_min": int(np.min(counts)) if counts else None,
        "n_models_per_seed_basin_median": float(np.median(counts)) if counts else None,
        "n_models_per_seed_basin_max": int(np.max(counts)) if counts else None,
        "sample_model_tokens": sorted(tokens)[:30],
    }
    LOGGER.info("Old-format structure %s: %s", label, summary)
    write_json(summary, out_csv.with_suffix('.summary.json'))
    return summary


def build_legacy_ensemble_from_all_configs(
    preds_all: Mapping[str, Any],
    basin_ids: set[str],
    agg: str,
    model_filter: Optional[Callable[[str, str, str], bool]] = None,
    expected_members: Optional[int] = None,
    label: str = "ensemble",
    audit_csv: Optional[Path] = None,
) -> Tuple[Dict[str, Dict[str, Dict[str, Any]]], pd.DataFrame]:
    """Build old-paper ensemble format: out[basin][seed]['ensemble'] = DataArray."""
    # First collect at basin-seed level; keep reference DataArray.
    buckets: Dict[Tuple[str,str], List[Tuple[str, Any]]] = {}
    records=[]
    for model_token, seed, basin, pred_obj in iter_old_all_config_predictions(preds_all, basin_ids):
        use = True if model_filter is None else bool(model_filter(model_token, seed, basin))
        records.append({"label": label, "seed": seed, "basin": basin, "model_token": model_token, "used": use})
        if not use:
            continue
        buckets.setdefault((basin, seed), []).append((model_token, pred_obj))
    if not buckets:
        raise RuntimeError(f"No predictions available to build {label} ({agg})")
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    counts=[]
    for (basin, seed), members in buckets.items():
        arrs=[]; ref=None
        for mt, po in members:
            da=to_dataarray(po, SIM_KEY)
            if ref is None:
                ref=da
            arrs.append(da_values(da))
        L=min(len(a) for a in arrs)
        stack=np.stack([a[:L] for a in arrs], axis=0)
        ens_da=make_ensemble_da(stack, ref, agg=agg, n_members=len(arrs))
        out.setdefault(basin, {})[str(seed)] = {"ensemble": ens_da}
        counts.append(len(arrs))
    rec_df=pd.DataFrame(records)
    if audit_csv is not None:
        audit_csv.parent.mkdir(parents=True, exist_ok=True)
        rec_df.to_csv(audit_csv, index=False)
    LOGGER.info("Built legacy %s %s ensemble for %d basins / %d basin-seed entries; members min=%d median=%.1f max=%d",
                label, agg, len(out), len(counts), int(np.min(counts)), float(np.median(counts)), int(np.max(counts)))
    if expected_members is not None:
        bad=[c for c in counts if c != expected_members]
        if bad:
            LOGGER.warning("%s %s expected %s members but found nonmatching counts in %d/%d basin-seed entries. min=%s median=%s max=%s",
                           label, agg, expected_members, len(bad), len(counts), np.min(counts), np.median(counts), np.max(counts))
    return out, rec_df


def old_ensemble_seed_series(ens_obj: Mapping[str, Any], basin: str, seed: str) -> Optional[Any]:
    bid=safe_zfill_basin(basin)
    if bid not in ens_obj:
        # try original unfilled string
        if str(basin) in ens_obj:
            bid=str(basin)
        else:
            return None
    seed_dict=ens_obj[bid]
    if not isinstance(seed_dict, Mapping):
        # compact {basin: da}; treat as seed-less
        return to_dataarray(seed_dict, SIM_KEY)
    if str(seed) not in seed_dict:
        return None
    return to_dataarray(seed_dict[str(seed)], SIM_KEY)


def legacy_ensemble_to_compact_prediction_map(ens_obj: Mapping[str, Any], seed_agg: str="mean") -> Dict[str, np.ndarray]:
    """For summary/temporal plots: aggregate old seed-level ensemble to one series per basin."""
    out={}
    for basin, seed_dict in ens_obj.items():
        bid=safe_zfill_basin(basin)
        if isinstance(seed_dict, Mapping) and any(str(k) in seed_dict for k in SEED_VALUES):
            arrs=[]
            for seed, pred_dict in seed_dict.items():
                try:
                    arrs.append(da_values(to_dataarray(pred_dict, SIM_KEY)))
                except Exception:
                    pass
            if arrs:
                L=min(len(a) for a in arrs)
                stack=np.stack([a[:L] for a in arrs], axis=0)
                out[bid]=(np.nanmean(stack,axis=0) if seed_agg=="mean" else np.nanmedian(stack,axis=0)).astype(np.float32)
        else:
            try:
                out[bid]=da_values(to_dataarray(seed_dict, SIM_KEY))
            except Exception:
                pass
    return out


def compare_legacy_ensembles(rebuilt: Mapping[str,Any], existing: Mapping[str,Any], framework_id: str, out_dir: Path, atol: float=1e-6) -> Dict[str,Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows=[]
    basins=sorted(set(safe_zfill_basin(b) for b in rebuilt.keys()) & set(safe_zfill_basin(b) for b in existing.keys()))
    for basin in basins:
        for seed in SEED_VALUES:
            try:
                a_da=old_ensemble_seed_series(rebuilt, basin, seed)
                b_da=old_ensemble_seed_series(existing, basin, seed)
                if a_da is None or b_da is None:
                    rows.append({"framework_id":framework_id,"basin":basin,"seed":seed,"status":"missing_seed","within_tolerance":False})
                    continue
                a=da_values(a_da).astype(np.float64); b=da_values(b_da).astype(np.float64)
                n=min(len(a),len(b)); diff=np.abs(a[:n]-b[:n]) if n else np.array([np.nan])
                rows.append({"framework_id":framework_id,"basin":basin,"seed":seed,"status":"ok","n_rebuilt":len(a),"n_existing":len(b),"n_compared":n,"max_abs_diff":float(np.nanmax(diff)),"mean_abs_diff":float(np.nanmean(diff)),"within_tolerance":bool(np.nanmax(diff)<=atol)})
            except Exception as e:
                rows.append({"framework_id":framework_id,"basin":basin,"seed":seed,"status":f"error:{type(e).__name__}:{e}","within_tolerance":False})
    df=pd.DataFrame(rows)
    df.to_csv(out_dir/f"{framework_id}_legacy_rebuilt_vs_existing_seed_timeseries.csv", index=False)
    ok=df[df["status"].eq("ok")].copy()
    summary={
        "framework_id":framework_id,
        "n_common_basins":len(basins),
        "n_seed_series_compared":int(len(ok)),
        "n_missing_or_error":int((~df["status"].eq("ok")).sum()),
        "all_within_tolerance":bool(len(ok)>0 and ok["within_tolerance"].all() and int((~df["status"].eq("ok")).sum())==0),
        "max_abs_diff_overall":float(ok["max_abs_diff"].max()) if len(ok) else np.nan,
        "mean_abs_diff_overall":float(ok["mean_abs_diff"].mean()) if len(ok) else np.nan,
        "tolerance":atol,
    }
    write_json(summary, out_dir/f"{framework_id}_legacy_rebuilt_vs_existing_summary.json")
    LOGGER.info("Legacy rebuilt-vs-existing validation %s: %s", framework_id, summary)
    return summary

# -----------------------------------------------------------------------------
# Cluster mapping
# -----------------------------------------------------------------------------
def detect_id_and_cluster_cols(df: pd.DataFrame) -> Tuple[str,str]:
    id_candidates=["gauge_id","basin_id","Gauge_ID","gage_id","gauge","basin","STAID","station_id"]
    cl_candidates=["cluster","Cluster","cluster_id","Cluster_ID","cluster_ID","kmeans_cluster","selected_cluster"]
    id_col=next((c for c in id_candidates if c in df.columns), df.columns[0])
    cl_col=next((c for c in cl_candidates if c in df.columns), None)
    if cl_col is None:
        cl_col=next((c for c in df.columns if "cluster" in c.lower()), None)
    if cl_col is None:
        raise ValueError(f"Could not detect cluster column in {df.columns.tolist()}")
    return id_col,cl_col


def load_cluster_map(path: Path) -> Dict[str,int]:
    df=pd.read_excel(path, dtype=str) if path.suffix.lower() in [".xlsx",".xls"] else pd.read_csv(path, dtype=str)
    id_col,cl_col=detect_id_and_cluster_cols(df)
    out={}
    for _,r in df.iterrows():
        try:
            out[safe_zfill_basin(r[id_col])]=int(float(r[cl_col]))
        except Exception:
            pass
    LOGGER.info("Loaded cluster map for %d basins from %s", len(out), path)
    return out


def cluster_base(cluster_map: Mapping[str,int]) -> int:
    vals=sorted(set(int(v) for v in cluster_map.values()))
    return 0 if vals and min(vals)==0 else 1


def normalize_cluster_id(x: Any, base: int) -> Optional[int]:
    try:
        v=int(float(str(x)))
    except Exception:
        return None
    if base==1 and 0 <= v <= 5:
        return v+1
    if base==0 and 1 <= v <= 6:
        return v-1
    return v


def find_file_recursive(roots: Sequence[Optional[Path]], names: Sequence[str]) -> Optional[Path]:
    seen=set(); candidates=[]
    for r in roots:
        if r is None:
            continue
        try:
            rp=Path(r).resolve()
        except Exception:
            rp=Path(r)
        key=str(rp).lower()
        if key in seen:
            continue
        seen.add(key); candidates.append(rp)
    for root in candidates:
        for name in names:
            for d in [root, root/"outputs", root/"outputs"/"evaluations", root/"Results", root/"Results"/"Tables", root/"Pickles", root/"misc", root/"configs", root/"configs"/"selected_final_configs", root/"configs"/"selected_final_configs"/"clusterwise"]:
                f=d/name
                if f.exists() and f.is_file():
                    return f
    for root in candidates:
        if not root.exists() or not root.is_dir():
            continue
        for name in names:
            try:
                hits=list(root.rglob(name))
                if hits:
                    return sorted(hits, key=lambda x: (len(x.parts), str(x).lower()))[0]
            except Exception as e:
                LOGGER.warning("Recursive search failed under %s for %s: %r", root, name, e)
    return None


def find_selected_clusterwise_csv(root_paths: Sequence[Optional[Path]]) -> Optional[Path]:
    return find_file_recursive(root_paths, ["selected_clusterwise_models.csv", "selected_clusterwise_configs.csv", "selected_cluster_wise_models.csv"])


def find_cluster_configs_xlsx(root_paths: Sequence[Optional[Path]]) -> Optional[Path]:
    return find_file_recursive(root_paths, ["Clusters&Configs.xlsx", "Clusters_and_Configs.xlsx", "ClusterwiseConfigs.xlsx", "Cluster-wiseConfigs.xlsx"])


def find_validation_results_csv(root_paths: Sequence[Optional[Path]]) -> Optional[Path]:
    return find_file_recursive(root_paths, ["Ver_results_2000RS_validation_epochs_20_25_30.csv", "validation_results.csv", "validation_metrics.csv"])


def normalize_model_token(s: Any) -> str:
    s=str(s).strip()
    s=s.replace("531_basins_Train_100RandomSearches_", "")
    s=re.sub(r"^(Top10|ClusterWise)_", "", s)
    s=re.sub(r"_epoch\d+_RS\d+$", "", s)
    return s


def model_aliases(s: Any) -> set[str]:
    raw=str(s).strip(); stem=Path(raw).stem; norm=normalize_model_token(raw); stem_norm=normalize_model_token(stem)
    aliases={raw, stem, norm, stem_norm}
    for m in re.findall(r"\d{4}_\d{6}", raw):
        aliases.add(m)
    return {a for a in aliases if a}


def token_matches_source_model(model_token: Any, source_model: Any) -> bool:
    token_aliases=model_aliases(model_token); source_aliases=model_aliases(source_model)
    if token_aliases & source_aliases:
        return True
    traw=str(model_token)
    return any(src and src in traw for src in source_aliases)


def detect_model_cluster_columns(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    model_candidates=["source_model","Model","model","model_id","config","config_id","model_token","selected_model","source_config","experiment_name"]
    cluster_candidates=["cluster","Cluster","selected_cluster","cluster_id","Cluster_ID","cluster_raw"]
    mcol=next((c for c in model_candidates if c in df.columns), None)
    if mcol is None:
        mcol=next((c for c in df.columns if any(x in c.lower() for x in ["model","config","experiment"]) and "file" not in c.lower()), None)
    ccol=next((c for c in cluster_candidates if c in df.columns), None)
    if ccol is None:
        ccol=next((c for c in df.columns if "cluster" in c.lower()), None)
    return mcol, ccol


def load_cluster_slot_map_from_xlsx(path: Optional[Path], base: int, out_dir: Optional[Path]=None) -> Dict[int, List[str]]:
    """Load explicit cluster -> top-3 selected source-model slots from the user's legacy xlsx.

    Preferred sheet: Cluster-wiseConfigs. This file is the authoritative selected slot map:
    6 clusters × 3 rows = 18 cluster-specific slots, but unique models can be 17 because
    one source model may be selected in two clusters. The duplicate is preserved.
    """
    if path is None or not Path(path).exists():
        return {}
    try:
        xl = pd.ExcelFile(path)
        sheet = "Cluster-wiseConfigs" if "Cluster-wiseConfigs" in xl.sheet_names else None
        if sheet is None:
            sheet = next((sh for sh in xl.sheet_names if "cluster" in sh.lower() and "config" in sh.lower()), None)
        if sheet is None:
            LOGGER.warning("No cluster-wise configs sheet found in %s; sheets=%s", path, xl.sheet_names)
            return {}
        df = pd.read_excel(path, sheet_name=sheet)
    except Exception as e:
        LOGGER.warning("Could not read F4 xlsx slot map from %s: %r", path, e)
        return {}
    mcol, ccol = detect_model_cluster_columns(df)
    if mcol is None or ccol is None:
        LOGGER.warning("Could not detect model/cluster columns in xlsx %s: %s", path, df.columns.tolist())
        return {}
    rank_col = next((c for c in ["selection_rank","rank","Rank","slot_rank","Avg_metric_Rank"] if c in df.columns), None)
    work = df.copy()
    work["_cluster_norm"] = [normalize_cluster_id(v, base) for v in work[ccol]]
    work["_source_model_norm"] = work[mcol].map(normalize_model_token)
    work = work.dropna(subset=["_cluster_norm", "_source_model_norm"])
    work = work[work["_source_model_norm"].astype(str).str.lower().ne("nan")]
    if rank_col:
        work = work.sort_values(["_cluster_norm", rank_col])
    else:
        work = work.sort_values(["_cluster_norm"])
    rows = []
    cluster_to_models: Dict[int, List[str]] = {}
    for cl, sub in work.groupby("_cluster_norm", sort=True):
        slots = []
        # Keep slots in sheet order/rank. De-duplicate only within the same cluster, not across clusters.
        for _, r in sub.iterrows():
            sm = str(r["_source_model_norm"])
            if sm not in slots:
                slots.append(sm)
            if len(slots) >= 3:
                break
        if slots:
            cluster_to_models[int(cl)] = slots
            for i, sm in enumerate(slots, 1):
                rows.append({
                    "cluster": int(cl),
                    "slot_rank": i,
                    "source_model": sm,
                    "source": str(path),
                    "source_sheet": sheet,
                })
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out_dir/"F4_cluster_slot_map_from_xlsx.csv", index=False)
        write_json({str(k): v for k, v in cluster_to_models.items()}, out_dir/"F4_cluster_slot_map_from_xlsx.json")
    inv = {}
    for cl, slots in cluster_to_models.items():
        for sm in slots:
            inv.setdefault(sm, []).append(cl)
    dup = {sm: cls for sm, cls in inv.items() if len(set(cls)) > 1}
    LOGGER.info("Loaded F4 cluster-slot map from xlsx %s sheet=%s: %s; total slots=%d unique source models=%d duplicate models=%d",
                path, sheet, {k: len(v) for k, v in cluster_to_models.items()}, sum(len(v) for v in cluster_to_models.values()), len(inv), len(dup))
    return cluster_to_models


def load_cluster_slot_map_from_csv(path: Optional[Path], base: int, out_dir: Optional[Path]=None) -> Dict[int, List[str]]:
    """Return cluster -> top-3 selected source-model slots.

    This intentionally keeps a cluster-slot representation instead of a unique model->cluster map.
    A selected source model can appear in the top-3 slots of more than one cluster.
    """
    if path is None or not Path(path).exists():
        LOGGER.warning("selected_clusterwise_models.csv unavailable; F4 cluster-local needs cluster slots.")
        return {}
    df=pd.read_csv(path)
    mcol, ccol=detect_model_cluster_columns(df)
    if mcol is None or ccol is None:
        LOGGER.warning("Could not detect model/cluster columns in %s: %s", path, df.columns.tolist())
        return {}
    rank_col=next((c for c in ["selection_rank","rank","Rank","cluster_rank"] if c in df.columns), None)
    work=df.copy()
    work["_cluster_norm"]=[normalize_cluster_id(v, base) for v in work[ccol]]
    work["_source_model_norm"]=work[mcol].map(normalize_model_token)
    work=work.dropna(subset=["_cluster_norm","_source_model_norm"])
    if rank_col:
        work=work.sort_values(["_cluster_norm", rank_col])
    rows=[]; cluster_to_models={}
    for cl, sub in work.groupby("_cluster_norm", sort=True):
        slots=[]
        for _, r in sub.iterrows():
            sm=str(r["_source_model_norm"])
            if sm not in slots:
                slots.append(sm)
            if len(slots)>=3:
                break
        cluster_to_models[int(cl)]=slots
        for i, sm in enumerate(slots,1):
            rows.append({"cluster": int(cl), "slot_rank": i, "source_model": sm, "source": str(path)})
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out_dir/"F4_cluster_slot_map_from_selected_csv.csv", index=False)
        write_json({str(k): v for k,v in cluster_to_models.items()}, out_dir/"F4_cluster_slot_map_from_selected_csv.json")
    LOGGER.info("Loaded F4 cluster-slot map from %s: %s", path, {k: len(v) for k,v in cluster_to_models.items()})
    return cluster_to_models


def rebuild_cluster_slot_map_from_validation(validation_csv: Optional[Path], cluster_map: Mapping[str,int], base: int, out_dir: Optional[Path]=None) -> Dict[int, List[str]]:
    if validation_csv is None or not Path(validation_csv).exists():
        return {}
    df=pd.read_csv(validation_csv, dtype={"basin": str})
    if "Model" not in df.columns:
        LOGGER.warning("Cannot rebuild F4 slots from %s: no Model column", validation_csv)
        return {}
    basin_col=next((c for c in ["basin","gauge_id","basin_id"] if c in df.columns), None)
    if basin_col is None:
        LOGGER.warning("Cannot rebuild F4 slots from %s: no basin column", validation_csv)
        return {}
    metric_col=next((c for c in ["SFmean_NSE", "NSE", "NSE_mean", "SFmean_NSE_mean"] if c in df.columns), None)
    if metric_col is None:
        LOGGER.warning("Cannot rebuild F4 slots from %s: no NSE/SFmean_NSE metric column", validation_csv)
        return {}
    df[basin_col]=df[basin_col].map(safe_zfill_basin)
    df["_cluster_norm"]=df[basin_col].map(lambda b: normalize_cluster_id(cluster_map.get(b), base))
    rows=[]; cluster_to_models={}
    for cl, sub in df.dropna(subset=["_cluster_norm"]).groupby("_cluster_norm", sort=True):
        summ=sub.groupby("Model", dropna=False)[metric_col].mean().reset_index(name="score")
        summ["source_model"]=summ["Model"].map(normalize_model_token)
        summ=summ.sort_values("score", ascending=False).drop_duplicates("source_model", keep="first").head(3)
        slots=summ["source_model"].astype(str).tolist()
        cluster_to_models[int(cl)]=slots
        for i, (_, r) in enumerate(summ.iterrows(),1):
            rows.append({"cluster": int(cl), "slot_rank": i, "source_model": r["source_model"], "score": r["score"], "source": str(validation_csv)})
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out_dir/"F4_cluster_slot_map_REBUILT_from_validation.csv", index=False)
        write_json({str(k): v for k,v in cluster_to_models.items()}, out_dir/"F4_cluster_slot_map_REBUILT_from_validation.json")
    LOGGER.info("Rebuilt F4 cluster-slot map from validation CSV %s: %s", validation_csv, {k: len(v) for k,v in cluster_to_models.items()})
    return cluster_to_models


def load_f4_cluster_slot_map(selected_csv: Optional[Path], cluster_configs_xlsx: Optional[Path], validation_csv: Optional[Path], cluster_map: Mapping[str,int], base: int, out_dir: Path) -> Dict[int, List[str]]:
    # Priority: explicit selected CSV, then authoritative Clusters&Configs.xlsx, then full validation CSV fallback.
    slot_map=load_cluster_slot_map_from_csv(selected_csv, base, out_dir=out_dir) if selected_csv else {}
    if not slot_map:
        slot_map=load_cluster_slot_map_from_xlsx(cluster_configs_xlsx, base, out_dir=out_dir) if cluster_configs_xlsx else {}
    if not slot_map:
        slot_map=rebuild_cluster_slot_map_from_validation(validation_csv, cluster_map, base, out_dir=out_dir)
    rows=[]; inv={}
    for cl, models in slot_map.items():
        for rank, sm in enumerate(models, 1):
            rows.append({"cluster": cl, "slot_rank": rank, "source_model": sm})
            inv.setdefault(sm, []).append(cl)
    if rows:
        out_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out_dir/"F4_cluster_slot_map_FINAL.csv", index=False)
        dup_rows=[{"source_model": sm, "selected_clusters": "|".join(map(str, cls)), "n_clusters": len(set(cls))} for sm, cls in inv.items() if len(set(cls))>1]
        pd.DataFrame(dup_rows).to_csv(out_dir/"F4_duplicate_source_models_across_clusters.csv", index=False)
        LOGGER.info("F4 final cluster-slot map: %d slots, %d unique source models, duplicates across clusters=%d", len(rows), len(inv), len(dup_rows))
    return slot_map

# -----------------------------------------------------------------------------
# Metrics: legacy-compatible seed-level and basin SFmean
# -----------------------------------------------------------------------------
def _valid(o,s):
    L=min(len(o),len(s)); o=np.asarray(o[:L],float); s=np.asarray(s[:L],float); m=np.isfinite(o)&np.isfinite(s); return o[m],s[m]
def metric_nse(o,s):
    o,s=_valid(o,s); den=np.sum((o-np.mean(o))**2) if len(o) else np.nan; return float(1-np.sum((s-o)**2)/den) if len(o)>1 and den!=0 else np.nan
def metric_mse(o,s):
    o,s=_valid(o,s); return float(np.mean((s-o)**2)) if len(o) else np.nan
def metric_rmse(o,s):
    v=metric_mse(o,s); return float(np.sqrt(v)) if np.isfinite(v) else np.nan
def metric_pearson(o,s):
    o,s=_valid(o,s); return float(np.corrcoef(o,s)[0,1]) if len(o)>1 and np.std(o)!=0 and np.std(s)!=0 else np.nan
def metric_kge(o,s):
    o,s=_valid(o,s)
    if len(o)<2 or np.std(o)==0 or np.std(s)==0 or np.mean(o)==0: return np.nan
    r=metric_pearson(o,s); a=np.std(s)/np.std(o); b=np.mean(s)/np.mean(o); return float(1-np.sqrt((r-1)**2+(a-1)**2+(b-1)**2))
def metric_alpha(o,s):
    o,s=_valid(o,s); return float(np.std(s)/np.std(o)) if len(o)>1 and np.std(o)!=0 else np.nan
def metric_beta_nse(o,s):
    o,s=_valid(o,s); return float((np.mean(s)-np.mean(o))/np.std(o)) if len(o)>1 and np.std(o)!=0 else np.nan
def metric_beta_kge(o,s):
    o,s=_valid(o,s); return float(np.mean(s)/np.mean(o)) if len(o)>0 and np.mean(o)!=0 else np.nan
def _fdc(x): return np.sort(np.asarray(x,float))[::-1]
def metric_fhv(o,s,h=0.02):
    o,s=_valid(o,s)
    if len(o)<1: return np.nan
    o=_fdc(o); s=_fdc(s); n=max(1,int(round(h*len(o)))); den=np.sum(o[:n]); return float(np.sum(s[:n]-o[:n])/den*100) if den!=0 else np.nan
def metric_fms(o,s,lower=0.2,upper=0.7):
    o,s=_valid(o,s)
    if len(o)<2: return np.nan
    o=_fdc(o); s=_fdc(s); o[o==0]=1e-6; s[s<=0]=1e-6; il=min(len(o)-1,int(round(lower*len(o)))); iu=min(len(o)-1,int(round(upper*len(o)))); den=np.log(o[il])-np.log(o[iu])+1e-6; return float(((np.log(s[il])-np.log(s[iu]))-(np.log(o[il])-np.log(o[iu])))/den*100)
def metric_flv(o,s,l=0.3):
    o,s=_valid(o,s)
    if len(o)<2: return np.nan
    o=_fdc(o); s=_fdc(s); o[o==0]=1e-6; s[s<=0]=1e-6; n=max(1,int(round(l*len(o)))); o=np.log(o[-n:]); s=np.log(s[-n:]); den=np.sum(o-o.min())+1e-6; return float(-1*(np.sum(s-s.min())-np.sum(o-o.min()))/den*100)
def metric_peak_mape(o,s):
    o,s=_valid(o,s)
    if len(o)<3 or not SCIPY_AVAILABLE: return np.nan
    peaks,_=scipy_signal.find_peaks(o,distance=100,prominence=np.std(o))
    if len(peaks)==0: return np.nan
    den=o[peaks]; mask=den!=0
    return float(np.mean(np.abs((s[peaks][mask]-den[mask])/den[mask]))*100) if np.any(mask) else np.nan
def metric_mape(o,s):
    o,s=_valid(o,s); mask=o!=0; return float(np.mean(np.abs((s[mask]-o[mask])/o[mask]))*100) if np.any(mask) else np.nan
def metric_missed(o,s,window=1,percentile=80):
    o,s=_valid(o,s)
    if len(o)<3 or not SCIPY_AVAILABLE: return np.nan
    po,_=scipy_signal.find_peaks(o,distance=30,height=np.percentile(o,percentile)); ps,_=scipy_signal.find_peaks(s,distance=30,height=np.percentile(s,percentile))
    if len(po)==0: return 0.0
    miss=0
    for idx in po:
        if idx-window<0 or idx+window>=len(o): continue
        if len(np.where(np.abs(ps-idx)<=window)[0])==0: miss+=1
    return float(miss/len(po))
def metric_timing(o,s,window=3):
    o,s=_valid(o,s)
    if len(o)<3 or not SCIPY_AVAILABLE: return np.nan
    peaks,_=scipy_signal.find_peaks(o,distance=100,prominence=np.std(o)); errs=[]
    for idx in peaks:
        if idx-window<0 or idx+window>=len(o): continue
        loc=s[idx-window:idx+window+1]; errs.append(abs(idx-window+int(np.nanargmax(loc))-idx))
    return float(np.mean(errs)) if errs else np.nan

def calculate_metrics_np(o,s,include_peak=True):
    out={"NSE":metric_nse(o,s),"KGE":metric_kge(o,s),"MSE":metric_mse(o,s),"RMSE":metric_rmse(o,s),"Alpha-NSE":metric_alpha(o,s),"Beta-KGE":metric_beta_kge(o,s),"Beta-NSE":metric_beta_nse(o,s),"Pearson-r":metric_pearson(o,s),"FHV":metric_fhv(o,s),"FMS":metric_fms(o,s),"FLV":metric_flv(o,s),"MAPE":metric_mape(o,s)}
    if include_peak: out.update({"Peak-Timing":metric_timing(o,s),"Missed-Peaks":metric_missed(o,s),"Peak-MAPE":metric_peak_mape(o,s)})
    else: out.update({"Peak-Timing":np.nan,"Missed-Peaks":np.nan,"Peak-MAPE":np.nan})
    return out


def load_obs_map(obs_obj: Mapping[str,Any]) -> Dict[str, Any]:
    out={}
    for b,v in obs_obj.items():
        out[safe_zfill_basin(b)]=to_dataarray(v, OBS_KEY)
    return out


def metrics_seed_level(ens_obj: Mapping[str,Any], obs_map: Mapping[str,Any], model_name: str, cluster_map: Mapping[str,int], include_peak=True) -> pd.DataFrame:
    rows=[]
    for basin, seed_dict in ens_obj.items():
        bid=safe_zfill_basin(basin)
        if bid not in obs_map: continue
        obs_vals=da_values(obs_map[bid])
        if not isinstance(seed_dict, Mapping):
            continue
        for seed, pred_dict in seed_dict.items():
            try:
                sim_vals=da_values(to_dataarray(pred_dict, SIM_KEY))
                vals=calculate_metrics_np(obs_vals, sim_vals, include_peak=include_peak)
            except Exception as e:
                LOGGER.warning("Metric failure model=%s basin=%s seed=%s: %r", model_name,bid,seed,e)
                vals={m:np.nan for m in LEGACY_METRICS}
            rows.append({"model":model_name,"basin":bid,"seed":str(seed),"cluster":cluster_map.get(bid,np.nan),**vals})
    return pd.DataFrame(rows)


def metrics_basin_sfmean(seed_metrics: pd.DataFrame) -> pd.DataFrame:
    metric_cols=[m for m in LEGACY_METRICS if m in seed_metrics.columns]
    if seed_metrics.empty: return pd.DataFrame()
    g=seed_metrics.groupby(["model","basin","cluster"], dropna=False)[metric_cols].mean().reset_index()
    rename={m:f"SFmean_{m}" for m in metric_cols}
    return g.rename(columns=rename)


def framework_summary_from_sfmean(sf: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for model,g in sf.groupby("model"):
        row={"model":model,"n_basins":g["basin"].nunique()}
        for c in [c for c in sf.columns if c.startswith("SFmean_")]:
            vals=pd.to_numeric(g[c],errors="coerce")
            row[f"{c}_mean"]=float(vals.mean())
            row[f"{c}_median"]=float(vals.median())
            row[f"{c}_q25"]=float(vals.quantile(.25))
            row[f"{c}_q75"]=float(vals.quantile(.75))
        rows.append(row)
    return pd.DataFrame(rows)


def compare_metrics_to_old(new_sf: pd.DataFrame, old_metrics_path: Optional[Path], out_dir: Path) -> Dict[str,Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if old_metrics_path is None or not Path(old_metrics_path).exists():
        summ={"old_metrics_path":str(old_metrics_path) if old_metrics_path else None,"exists":False,"status":"not_compared"}
        write_json(summ,out_dir/"old_metrics_comparison_summary.json")
        return summ
    old=load_pickle(old_metrics_path)
    if not isinstance(old,pd.DataFrame):
        try: old=pd.DataFrame(old)
        except Exception:
            summ={"old_metrics_path":str(old_metrics_path),"exists":True,"status":"unreadable_non_dataframe","type":str(type(old))}
            write_json(summ,out_dir/"old_metrics_comparison_summary.json")
            return summ
    old.to_csv(out_dir/"old_metrics_loaded_preview.csv",index=False)
    # Generic comparison is intentionally conservative: write schemas and try common basin/model columns.
    schema={"old_metrics_path":str(old_metrics_path),"exists":True,"status":"loaded","old_shape":old.shape,"new_shape":new_sf.shape,"old_columns":old.columns.tolist(),"new_columns":new_sf.columns.tolist()}
    write_json(schema,out_dir/"old_metrics_comparison_summary.json")
    return schema

# -----------------------------------------------------------------------------
# Temporal and stats using compact maps
# -----------------------------------------------------------------------------
def compact_metric_df(model_name: str, compact: Mapping[str,np.ndarray], obs_map: Mapping[str,Any], cluster_map: Mapping[str,int], include_peak=True) -> pd.DataFrame:
    rows=[]
    for bid,sim in compact.items():
        if bid not in obs_map: continue
        vals=calculate_metrics_np(da_values(obs_map[bid]), sim, include_peak=include_peak)
        rows.append({"model":model_name,"basin":bid,"cluster":cluster_map.get(bid,np.nan),**vals})
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--work-root',type=Path,required=True)
    ap.add_argument('--pickle-dir',type=Path,required=True)
    ap.add_argument('--clusters',type=Path,required=True)
    ap.add_argument('--eval-dir',type=Path,default=None)
    ap.add_argument('--selected-clusterwise-csv',type=Path,default=None)
    ap.add_argument('--cluster-configs-xlsx',type=Path,default=None)
    ap.add_argument('--revision-root',type=Path,default=None)
    ap.add_argument('--top18-run-dir',type=Path,default=None)
    ap.add_argument('--include-top18',action='store_true')
    ap.add_argument('--save-ensembles',action='store_true')
    ap.add_argument('--skip-peak-metrics',action='store_true')
    ap.add_argument('--strict-rebuild-check',action='store_true')
    args=ap.parse_args()

    args.work_root.mkdir(parents=True, exist_ok=True)
    run_dir=args.work_root/f"CAMELS_ensemble_framework_eval_{time.strftime('%Y%m%d_%H%M%S')}_v11_f4_xlsx"
    dirs={k:run_dir/k for k in ['00_audit','01_ensembles_legacy_format','02_metrics_legacy_format','03_metrics_comparison','04_compact_summaries','05_rebuild_validation','logs']}
    for d in dirs.values(): d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s', handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(dirs['logs']/"bot_run.log",encoding='utf-8')])
    LOGGER.info("Starting v11 legacy-format validation bot with F4 XLSX slot map")
    LOGGER.info("Run dir: %s", run_dir)

    pickle_dir=args.pickle_dir
    eval_dir=args.eval_dir or (pickle_dir.parent/'evaluations')
    search_roots=[eval_dir, args.revision_root or pickle_dir.parent, pickle_dir.parent, pickle_dir.parent.parent, Path.cwd()]
    selected=args.selected_clusterwise_csv or find_selected_clusterwise_csv(search_roots)
    cluster_configs_xlsx=args.cluster_configs_xlsx or find_cluster_configs_xlsx(search_roots)
    validation_csv=find_validation_results_csv(search_roots)
    paths={
        'Obs_test': pickle_dir/'Obs_test.p',
        'All_Top10': pickle_dir/'All_Top10_Configs_CAMELSUS_test.p',
        'Existing_Top10_median': pickle_dir/'ensemble_Top10_CAMELSUS_test.p',
        'All_Clusterwise': pickle_dir/'All_Cluster_wise_Configs_CAMELSUS_test.p',
        'Existing_Clusterwise_median': pickle_dir/'ensemble_Cluster_wise_CAMELSUS_test.p',
        'All_Top18': pickle_dir/'All_Top18_Configs_CAMELSUS_test.p',
        'Existing_Top18_median': pickle_dir/'ensemble_Top18_CAMELSUS_test.p',
        'Old_metrics_all_test_period': pickle_dir/'metrics_all_test_period.p',
        'Old_metrics_by_water_year': pickle_dir/'metrics_by_water_year.p',
        'Old_metrics_by_year_season': pickle_dir/'metrics_by_year_season.p',
        'selected_clusterwise_csv': selected,
        'cluster_configs_xlsx': cluster_configs_xlsx,
        'validation_results_csv': validation_csv,
    }
    write_json({"created_at":time.strftime('%Y-%m-%d %H:%M:%S'),"python":sys.version,"platform":platform.platform(),"numpy":np.__version__,"pandas":pd.__version__,"xarray":XR_AVAILABLE,"scipy":SCIPY_AVAILABLE,"args":{k:str(v) for k,v in vars(args).items()},"paths":{k:file_info(v) for k,v in paths.items()}}, dirs['00_audit']/"input_manifest.json")

    cluster_map=load_cluster_map(args.clusters)
    basin_ids=set(cluster_map.keys())
    base=cluster_base(cluster_map)
    f4_cluster_slot_map=load_f4_cluster_slot_map(selected, cluster_configs_xlsx, validation_csv, cluster_map, base, dirs['00_audit'])
    if selected: LOGGER.info("Using selected clusterwise CSV: %s", selected)
    if cluster_configs_xlsx: LOGGER.info("Using cluster configs XLSX for F4 slots: %s", cluster_configs_xlsx)
    if validation_csv: LOGGER.info("Detected validation results CSV: %s", validation_csv)

    obs=load_obs_map(load_pickle(paths['Obs_test']))
    basin_ids=basin_ids & set(obs.keys())
    LOGGER.info("Evaluation basin intersection: %d", len(basin_ids))

    legacy_ensembles: Dict[str, Mapping[str,Any]] = {}
    validation=[]
    seed_metric_frames=[]
    compact_summary_frames=[]

    # Top10: existing median + rebuilt median + mean.
    existing_top10 = load_pickle(paths['Existing_Top10_median']) if paths['Existing_Top10_median'].exists() else None
    if existing_top10 is not None:
        legacy_ensembles['F1_Top10_regional_median_existing'] = existing_top10
    all_top10 = load_pickle(paths['All_Top10']) if paths['All_Top10'].exists() else None
    if all_top10 is not None:
        inspect_old_all_config_structure(all_top10, basin_ids, 'All_Top10', dirs['00_audit']/"All_Top10_structure.csv")
        rebuilt_top10_median, _ = build_legacy_ensemble_from_all_configs(all_top10, basin_ids, 'median', expected_members=10, label='F1_Top10_regional_median_rebuilt', audit_csv=dirs['00_audit']/"F1_Top10_median_rebuild_members.csv")
        legacy_ensembles['F1_Top10_regional_median_rebuilt'] = rebuilt_top10_median
        save_pickle(rebuilt_top10_median, dirs['01_ensembles_legacy_format']/"ensemble_Top10_CAMELSUS_test_REBUILT_MEDIAN_LEGACY_FORMAT.p")
        if existing_top10 is not None:
            validation.append(compare_legacy_ensembles(rebuilt_top10_median, existing_top10, 'F1_Top10_regional_median', dirs['05_rebuild_validation']))
        top10_mean,_=build_legacy_ensemble_from_all_configs(all_top10, basin_ids, 'mean', expected_members=10, label='F1_Top10_regional_mean', audit_csv=dirs['00_audit']/"F1_Top10_mean_members.csv")
        legacy_ensembles['F1_Top10_regional_mean'] = top10_mean
        save_pickle(top10_mean, dirs['01_ensembles_legacy_format']/"ensemble_Top10_CAMELSUS_test_MEAN_LEGACY_FORMAT.p")
        del all_top10; gc.collect()

    # Cluster-wise old: existing median + rebuilt median + mean + optional F4 local.
    existing_cw = load_pickle(paths['Existing_Clusterwise_median']) if paths['Existing_Clusterwise_median'].exists() else None
    if existing_cw is not None:
        legacy_ensembles['F3_clusterwise_global18_median_existing'] = existing_cw
    all_cw = load_pickle(paths['All_Clusterwise']) if paths['All_Clusterwise'].exists() else None
    if all_cw is not None:
        inspect_old_all_config_structure(all_cw, basin_ids, 'All_Clusterwise', dirs['00_audit']/"All_Clusterwise_structure.csv")
        rebuilt_cw_median,_=build_legacy_ensemble_from_all_configs(all_cw, basin_ids, 'median', expected_members=None, label='F3_clusterwise_global_median_rebuilt', audit_csv=dirs['00_audit']/"F3_clusterwise_median_rebuild_members.csv")
        legacy_ensembles['F3_clusterwise_global_median_rebuilt'] = rebuilt_cw_median
        save_pickle(rebuilt_cw_median, dirs['01_ensembles_legacy_format']/"ensemble_Cluster_wise_CAMELSUS_test_REBUILT_MEDIAN_LEGACY_FORMAT.p")
        if existing_cw is not None:
            validation.append(compare_legacy_ensembles(rebuilt_cw_median, existing_cw, 'F3_clusterwise_global_median_old', dirs['05_rebuild_validation']))
        cw_mean,_=build_legacy_ensemble_from_all_configs(all_cw, basin_ids, 'mean', expected_members=None, label='F3_clusterwise_global_mean', audit_csv=dirs['00_audit']/"F3_clusterwise_mean_members.csv")
        legacy_ensembles['F3_clusterwise_global_mean'] = cw_mean
        save_pickle(cw_mean, dirs['01_ensembles_legacy_format']/"ensemble_Cluster_wise_CAMELSUS_test_MEAN_LEGACY_FORMAT.p")
        # F4 cluster-local: use cluster -> top-3 selected slots, not unique model -> cluster.
        # A duplicated selected model can belong to two cluster top-3 lists; this is expected.
        if f4_cluster_slot_map:
            def filt(model_token, seed, basin):
                cl_b = normalize_cluster_id(cluster_map.get(safe_zfill_basin(basin)), base)
                if cl_b is None:
                    return False
                allowed = f4_cluster_slot_map.get(int(cl_b), [])
                return any(token_matches_source_model(model_token, src) for src in allowed)
            for agg in ['median','mean']:
                try:
                    f4,_=build_legacy_ensemble_from_all_configs(all_cw, basin_ids, agg, model_filter=filt, expected_members=3, label=f'F4_clusterlocal_top3_owncluster_{agg}', audit_csv=dirs['00_audit']/f"F4_clusterlocal_{agg}_members.csv")
                    legacy_ensembles[f'F4_clusterlocal_top3_owncluster_{agg}']=f4
                    save_pickle(f4, dirs['01_ensembles_legacy_format']/f"ensemble_ClusterLocal_Top3OwnCluster_CAMELSUS_test_{agg.upper()}_LEGACY_FORMAT.p")
                except Exception as e:
                    (dirs['00_audit']/f"F4_clusterlocal_{agg}_SKIPPED.txt").write_text(str(e),encoding='utf-8')
                    LOGGER.warning("F4 %s skipped: %s", agg, e)
        else:
            msg='F4 skipped: no cluster-slot map. Need selected_clusterwise_models.csv, Clusters&Configs.xlsx, or full validation results CSV.'
            (dirs['00_audit']/"F4_SKIPPED_NEEDS_CLUSTER_SLOT_MAP.txt").write_text(msg,encoding='utf-8')
            LOGGER.warning(msg)
        del all_cw; gc.collect()

    # Top18 held unless files complete and flag set.
    if args.include_top18 and paths['All_Top18'].exists():
        all_top18=load_pickle(paths['All_Top18'])
        inspect_old_all_config_structure(all_top18, basin_ids, 'All_Top18', dirs['00_audit']/"All_Top18_structure.csv")
        for agg in ['median','mean']:
            ens,_=build_legacy_ensemble_from_all_configs(all_top18, basin_ids, agg, expected_members=18, label=f'F2_Top18_regional_{agg}', audit_csv=dirs['00_audit']/f"F2_Top18_{agg}_members.csv")
            legacy_ensembles[f'F2_Top18_regional_{agg}']=ens
            save_pickle(ens, dirs['01_ensembles_legacy_format']/f"ensemble_Top18_CAMELSUS_test_{agg.upper()}_LEGACY_FORMAT.p")
        del all_top18; gc.collect()
    else:
        (dirs['00_audit']/"TOP18_HELD.txt").write_text('Top18 held until All_Top18_Configs_CAMELSUS_test.p is complete and --include-top18 is used.',encoding='utf-8')

    pd.DataFrame(validation).to_csv(dirs['05_rebuild_validation']/"legacy_rebuild_validation_summary.csv", index=False)
    write_json(validation, dirs['05_rebuild_validation']/"legacy_rebuild_validation_summary.json")
    if args.strict_rebuild_check:
        bad=[v for v in validation if not v.get('all_within_tolerance',False)]
        if bad:
            raise RuntimeError(f"Legacy rebuild validation failed: {bad}")

    # Metrics in legacy-compatible format.
    for model_name, ens in legacy_ensembles.items():
        LOGGER.info("Computing seed-level legacy metrics for %s", model_name)
        sm=metrics_seed_level(ens, obs, model_name, cluster_map, include_peak=not args.skip_peak_metrics)
        seed_metric_frames.append(sm)
    all_seed_metrics=pd.concat(seed_metric_frames, ignore_index=True) if seed_metric_frames else pd.DataFrame()
    all_sfmean=metrics_basin_sfmean(all_seed_metrics)
    save_pickle(all_seed_metrics, dirs['02_metrics_legacy_format']/"metrics_all_test_period_seed_level_LEGACY_FORMAT.p")
    all_seed_metrics.to_csv(dirs['02_metrics_legacy_format']/"metrics_all_test_period_seed_level_LEGACY_FORMAT.csv", index=False)
    save_pickle(all_sfmean, dirs['02_metrics_legacy_format']/"metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.p")
    all_sfmean.to_csv(dirs['02_metrics_legacy_format']/"metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.csv", index=False)
    summary=framework_summary_from_sfmean(all_sfmean)
    summary.to_csv(dirs['04_compact_summaries']/"framework_summary_from_legacy_SFmean.csv", index=False)
    save_pickle(summary, dirs['04_compact_summaries']/"framework_summary_from_legacy_SFmean.p")

    compare_metrics_to_old(all_sfmean, paths['Old_metrics_all_test_period'], dirs['03_metrics_comparison'])

    # final audit
    final={"run_dir":str(run_dir),"n_legacy_ensembles":len(legacy_ensembles),"validation":validation,"finished_at":time.strftime('%Y-%m-%d %H:%M:%S')}
    write_json(final, dirs['00_audit']/"final_audit.json")
    LOGGER.info("Done. Results saved under: %s", run_dir)
    print("\n=== CAMELS v9 legacy-format bot finished ===")
    print(f"Run directory: {run_dir}")
    print("Key validation:")
    print(f"  {dirs['05_rebuild_validation']/'legacy_rebuild_validation_summary.csv'}")
    print("Key legacy outputs:")
    print(f"  {dirs['01_ensembles_legacy_format']}")
    print(f"  {dirs['02_metrics_legacy_format']}")
    return 0

if __name__=='__main__':
    raise SystemExit(main())
