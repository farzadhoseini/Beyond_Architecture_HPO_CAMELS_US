from __future__ import annotations

"""
CAMELS-US F4-only builder: cluster-local top-3 own-cluster
-----------------------------------------------------------
Purpose:
  Build ONLY the F4 cluster-local ensembles from the legacy All_Cluster_wise
  pickle, using the explicit cluster-slot map in Clusters&Configs.xlsx, and
  compare the resulting F4 metrics against previously computed Top10 / old
  cluster-wise global results.

Key design fix vs v11:
  The F4 slot map is cluster -> three SOURCE configs, while the legacy
  All_Cluster_wise pickle stores seed-specific prediction tokens. Therefore
  this script first builds a SOURCE CONFIG -> PREDICTION TOKEN bridge. It tries,
  in order:
    1) explicit source-token-map CSV if supplied/found,
    2) local final run folders/config.yml by searching for source model strings,
    3) manifest_selected_seeded_configs.csv/config files,
    4) an auditable positional fallback only when unavoidable.

Legacy output format:
  ensemble[basin][seed]['ensemble'] = xarray.DataArray
"""

import argparse
import gc
import json
import logging
import math
import os
import pickle
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import xarray as xr
    XR_AVAILABLE = True
except Exception:
    XR_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE = True
except Exception:
    YAML_AVAILABLE = False

try:
    from scipy import signal as scipy_signal
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False

SIM_KEY = "QObs(mm/d)_sim"
OBS_KEY = "QObs(mm/d)_obs"
SEEDS_DEFAULT = ["191889", "307443", "328237", "385445", "473461", "643969", "665980", "845563", "985957", "993061"]

LOGGER = logging.getLogger("camels_f4_only")


def setup_logging(run_dir: Path) -> None:
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(run_dir / "logs" / "f4_only_bot.log", encoding="utf-8")
    fh.setFormatter(fmt)
    LOGGER.addHandler(sh)
    LOGGER.addHandler(fh)


def write_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


def load_pickle(path: Path) -> Any:
    LOGGER.info("Loading pickle: %s", path)
    t = time.time()
    # pandas 1.x pickle compatibility under pandas 2.x
    try:
        import pandas as pd  # noqa
        import types
        if "pandas.core.indexes.numeric" not in sys.modules:
            m = types.ModuleType("pandas.core.indexes.numeric")
            m.Int64Index = pd.Index
            m.UInt64Index = pd.Index
            m.Float64Index = pd.Index
            sys.modules["pandas.core.indexes.numeric"] = m
    except Exception:
        pass
    with Path(path).open("rb") as f:
        obj = pickle.load(f)
    LOGGER.info("Loaded %s in %.1f s", path.name, time.time() - t)
    return obj


def save_pickle(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    LOGGER.info("Saved pickle: %s", path)


def safe_zfill_basin(x: Any) -> str:
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(8)


def normalize_model_token(s: Any) -> str:
    s = str(s).strip()
    s = s.replace("531_basins_Train_100RandomSearches_", "")
    s = s.replace("531_basins_RandomSearch_", "")
    s = re.sub(r"^(Top10|ClusterWise|Clusterwise|F4)_", "", s)
    s = re.sub(r"_epoch\d+_RS\d+$", "", s)
    s = re.sub(r"_RS\d+$", "", s)
    return s


def source_suffix(s: Any) -> str:
    s = normalize_model_token(s)
    m = re.findall(r"\d{4}_\d{6}", s)
    return m[-1] if m else s


def model_aliases(s: Any) -> set[str]:
    raw = str(s).strip()
    stem = Path(raw).stem
    aliases = {raw, stem, normalize_model_token(raw), normalize_model_token(stem), source_suffix(raw)}
    for m in re.findall(r"\d{4}_\d{6}", raw):
        aliases.add(m)
    return {a for a in aliases if a and str(a).lower() != "nan"}


def token_matches_source_model(model_token: Any, source_model: Any) -> bool:
    ta = model_aliases(model_token)
    sa = model_aliases(source_model)
    if ta & sa:
        return True
    traw = str(model_token)
    return any(src and src in traw for src in sa)


def detect_id_and_cluster_cols(df: pd.DataFrame) -> Tuple[str, str]:
    id_candidates = ["gauge_id", "basin", "Basin", "basin_id", "Gauge ID", "ID"]
    cl_candidates = ["cluster", "Cluster", "cluster_id", "cluster_raw", "Cluster_ID"]
    id_col = next((c for c in id_candidates if c in df.columns), df.columns[0])
    cl_col = next((c for c in cl_candidates if c in df.columns), None)
    if cl_col is None:
        cl_col = next((c for c in df.columns if "cluster" in str(c).lower()), None)
    if cl_col is None:
        raise ValueError(f"Could not detect cluster column in {df.columns.tolist()}")
    return id_col, cl_col


def load_cluster_map(path: Path) -> Dict[str, int]:
    df = pd.read_excel(path, dtype=str) if path.suffix.lower() in [".xlsx", ".xls"] else pd.read_csv(path, dtype=str)
    id_col, cl_col = detect_id_and_cluster_cols(df)
    out: Dict[str, int] = {}
    for _, r in df.iterrows():
        try:
            out[safe_zfill_basin(r[id_col])] = int(float(r[cl_col]))
        except Exception:
            pass
    LOGGER.info("Loaded cluster map for %d basins from %s", len(out), path)
    return out


def cluster_base(cluster_map: Mapping[str, int]) -> int:
    vals = sorted(set(int(v) for v in cluster_map.values()))
    return 0 if vals and min(vals) == 0 else 1


def normalize_cluster_id(x: Any, base: int) -> Optional[int]:
    try:
        v = int(float(str(x)))
    except Exception:
        return None
    if base == 1 and 0 <= v <= 5:
        return v + 1
    if base == 0 and 1 <= v <= 6:
        return v - 1
    return v


def read_excel_slot_map(xlsx: Path, base: int, out_dir: Path) -> Dict[int, List[str]]:
    xl = pd.ExcelFile(xlsx)
    sheet = "Cluster-wiseConfigs" if "Cluster-wiseConfigs" in xl.sheet_names else next((s for s in xl.sheet_names if "cluster" in s.lower() and "config" in s.lower()), xl.sheet_names[0])
    df = pd.read_excel(xlsx, sheet_name=sheet)
    model_col = next((c for c in ["Model", "source_model", "model", "config", "experiment_name"] if c in df.columns), None)
    if model_col is None:
        model_col = next((c for c in df.columns if "model" in str(c).lower() or "config" in str(c).lower()), None)
    cluster_col = next((c for c in ["cluster", "Cluster", "cluster_id"] if c in df.columns), None)
    if cluster_col is None:
        cluster_col = next((c for c in df.columns if "cluster" in str(c).lower()), None)
    if model_col is None or cluster_col is None:
        raise ValueError(f"Could not detect Model/cluster columns in {xlsx}: {df.columns.tolist()}")
    rank_col = next((c for c in ["selection_rank", "rank", "Rank", "slot_rank", "AvgMetrics", "Avg_metric_Rank"] if c in df.columns), None)
    w = df.copy()
    w["cluster_norm"] = [normalize_cluster_id(v, base) for v in w[cluster_col]]
    w["source_model"] = w[model_col].astype(str).map(normalize_model_token)
    w = w.dropna(subset=["cluster_norm", "source_model"])
    if rank_col and rank_col not in ["AvgMetrics"]:
        w = w.sort_values(["cluster_norm", rank_col])
    else:
        # Preserve sheet order within cluster; the xlsx already contains the top-three order.
        w["_row"] = np.arange(len(w))
        w = w.sort_values(["cluster_norm", "_row"])
    slot_map: Dict[int, List[str]] = {}
    rows = []
    for cl, sub in w.groupby("cluster_norm", sort=True):
        slots: List[str] = []
        for _, r in sub.iterrows():
            sm = str(r["source_model"])
            if sm not in slots:  # de-duplicate only within the same cluster
                slots.append(sm)
            if len(slots) >= 3:
                break
        slot_map[int(cl)] = slots
        for i, sm in enumerate(slots, 1):
            rows.append({"cluster": int(cl), "slot_rank": i, "source_model": sm, "source_suffix": source_suffix(sm)})
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_dir / "F4_cluster_slot_map_FINAL.csv", index=False)
    inv: Dict[str, List[int]] = {}
    for r in rows:
        inv.setdefault(r["source_model"], []).append(int(r["cluster"]))
    dup = [{"source_model": sm, "source_suffix": source_suffix(sm), "selected_clusters": "|".join(map(str, cls)), "n_clusters": len(set(cls))} for sm, cls in inv.items() if len(set(cls)) > 1]
    pd.DataFrame(dup).to_csv(out_dir / "F4_duplicate_source_models_across_clusters.csv", index=False)
    LOGGER.info("Loaded F4 cluster-slot map from %s sheet=%s: %s; total slots=%d unique source models=%d duplicate models=%d", xlsx, sheet, {k: len(v) for k, v in slot_map.items()}, len(rows), len(inv), len(dup))
    return slot_map


def get_sim_model_dict(basin_value: Any) -> Optional[Mapping[str, Any]]:
    if not isinstance(basin_value, Mapping):
        return None
    if SIM_KEY in basin_value and isinstance(basin_value[SIM_KEY], Mapping):
        cont = basin_value[SIM_KEY]
        if "1D" not in cont:
            return cont
    if "1D" in basin_value and isinstance(basin_value["1D"], Mapping):
        one = basin_value["1D"]
        if SIM_KEY in one and isinstance(one[SIM_KEY], Mapping) and "1D" not in one[SIM_KEY]:
            return one[SIM_KEY]
    return None


def iter_old_all_config_predictions(preds_all: Mapping[str, Any], basin_ids: Optional[set[str]] = None):
    for seed, basin_dict in preds_all.items():
        seed_s = str(seed)
        if not isinstance(basin_dict, Mapping):
            continue
        for basin, basin_value in basin_dict.items():
            bid = safe_zfill_basin(basin)
            if basin_ids is not None and bid not in basin_ids:
                continue
            model_dict = get_sim_model_dict(basin_value)
            if not isinstance(model_dict, Mapping):
                continue
            for model_token, pred_obj in model_dict.items():
                yield str(model_token), seed_s, bid, pred_obj


def inspect_structure(preds_all: Mapping[str, Any], basin_ids: set[str], out_dir: Path) -> pd.DataFrame:
    rows = []
    for seed, basin_dict in preds_all.items():
        if not isinstance(basin_dict, Mapping):
            continue
        for basin, basin_value in basin_dict.items():
            bid = safe_zfill_basin(basin)
            if bid not in basin_ids:
                continue
            md = get_sim_model_dict(basin_value)
            toks = list(md.keys()) if isinstance(md, Mapping) else []
            rows.append({"seed": str(seed), "basin": bid, "n_model_tokens": len(toks), "model_tokens": "|".join(map(str, toks))})
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "All_Clusterwise_structure_FOR_F4.csv", index=False)
    if not df.empty:
        all_toks = set()
        for s in df["model_tokens"].dropna():
            all_toks.update(str(s).split("|"))
        summ = {
            "seed_basin_entries": len(df),
            "unique_model_tokens": len(all_toks),
            "members_min": int(df["n_model_tokens"].min()),
            "members_median": float(df["n_model_tokens"].median()),
            "members_max": int(df["n_model_tokens"].max()),
            "sample_tokens": sorted(all_toks)[:50],
        }
        write_json(summ, out_dir / "All_Clusterwise_structure_FOR_F4.summary.json")
        LOGGER.info("All_Clusterwise F4 structure: %s", summ)
    return df


def to_dataarray(obj: Any, key_hint: Optional[str] = None) -> Any:
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
        for v in obj.values():
            try:
                return to_dataarray(v, key_hint)
            except Exception:
                continue
        raise ValueError("Could not parse mapping as time series")
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
        arr = np.asarray(obj.select_dtypes(include=[np.number]).iloc[:, 0] if isinstance(obj, pd.DataFrame) else obj).squeeze()
        return xr.DataArray(arr, dims=["date"] if arr.ndim == 1 else None, name=key_hint or SIM_KEY)
    raise ValueError(f"Unsupported time series object: {type(obj)}")


def da_values(da: Any) -> np.ndarray:
    if XR_AVAILABLE and isinstance(da, xr.DataArray):
        return np.asarray(da.values).squeeze().astype(np.float32).reshape(-1)
    return np.asarray(da).squeeze().astype(np.float32).reshape(-1)


def make_ensemble_da(stack: np.ndarray, ref_da: Any, agg: str, n_members: int) -> Any:
    if agg == "median":
        ens = np.nanmedian(stack, axis=0).astype(np.float32)
    elif agg == "mean":
        ens = np.nanmean(stack, axis=0).astype(np.float32)
    else:
        raise ValueError("agg must be median or mean")
    if XR_AVAILABLE and isinstance(ref_da, xr.DataArray):
        squeezed = ref_da.squeeze()
        try:
            shaped = ens.reshape(np.asarray(squeezed.values).shape)
            da = xr.DataArray(shaped, dims=squeezed.dims, coords=squeezed.coords, name=SIM_KEY, attrs=dict(ref_da.attrs) if ref_da.attrs else {})
        except Exception:
            da = xr.DataArray(ens, dims=["date"], name=SIM_KEY)
    else:
        da = xr.DataArray(ens, dims=["date"], name=SIM_KEY)
    da.attrs.update({"ensemble_agg": agg, "n_members": int(n_members), "legacy_format": True, "framework": "F4_clusterlocal_top3_owncluster"})
    return da


def find_file_recursive(roots: Sequence[Path], names: Sequence[str]) -> Optional[Path]:
    for root in roots:
        if root is None:
            continue
        root = Path(root)
        for name in names:
            candidates = [root / name, root / "Pickles" / name, root / "outputs" / "pickles" / name, root / "Revision_2026_Top18_4Framework" / "ensemble_framework_bot_runs" / name]
            for c in candidates:
                if c.exists():
                    return c
        if root.exists() and root.is_dir():
            for name in names:
                try:
                    hits = list(root.rglob(name))
                    if hits:
                        return sorted(hits, key=lambda p: (len(p.parts), str(p).lower()))[0]
                except Exception:
                    pass
    return None


def find_latest_previous_sfmean(work_root: Path) -> Optional[Path]:
    if not work_root.exists():
        return None
    hits = list(work_root.rglob("metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.csv"))
    if not hits:
        return None
    # Prefer files from runs not named f4_only and most recently modified.
    hits = sorted(hits, key=lambda p: p.stat().st_mtime, reverse=True)
    for h in hits:
        if "f4_only" not in str(h).lower():
            return h
    return hits[0]


def read_yaml_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def yaml_load(path: Path) -> Mapping[str, Any]:
    if not YAML_AVAILABLE:
        return {}
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def scan_run_configs_for_source_token_map(root: Path, slot_map: Mapping[int, List[str]], out_dir: Path) -> pd.DataFrame:
    """Search local old run/config folders to bridge source configs to prediction tokens.

    The old GitHub code extracted seed and model name from each final run config.yml.
    In some local exports the prediction token is the run-folder timestamp, while the
    original source config may only appear inside config.yml or nearby manifest files.
    This function records every plausible source-token match it can find.
    """
    wanted_sources = []
    for models in slot_map.values():
        for sm in models:
            if sm not in wanted_sources:
                wanted_sources.append(sm)
    wanted_aliases = {sm: model_aliases(sm) for sm in wanted_sources}
    rows = []
    search_roots = [root, root / "Models", root / "runs", root / "configs", root / "Revision_2026_Top18_4Framework"]
    config_files = []
    for sr in search_roots:
        if sr.exists() and sr.is_dir():
            try:
                config_files.extend(list(sr.rglob("config.yml")))
                config_files.extend(list(sr.rglob("*.yml")))
            except Exception:
                pass
    # Limit duplicates
    config_files = sorted(set(config_files), key=lambda p: str(p).lower())
    for cfg_path in config_files:
        txt = read_yaml_text(cfg_path)
        cfg = yaml_load(cfg_path)
        exp = str(cfg.get("experiment_name", cfg_path.parent.name)) if isinstance(cfg, Mapping) else cfg_path.parent.name
        seed = str(cfg.get("seed", "")) if isinstance(cfg, Mapping) else ""
        run_token_candidates = set()
        run_token_candidates.add(normalize_model_token(cfg_path.parent.name))
        run_token_candidates.add(normalize_model_token(exp))
        for m in re.findall(r"\d{4}_\d{6}", str(cfg_path.parent) + " " + exp):
            run_token_candidates.add(m)
        # Find source strings in config text/path/experiment.
        hay = " ".join([str(cfg_path), txt, exp])
        for source_model, aliases in wanted_aliases.items():
            if any(a and a in hay for a in aliases):
                for token in run_token_candidates:
                    if re.match(r"^\d{4}_\d{6}$", token):
                        rows.append({
                            "source_model": source_model,
                            "source_suffix": source_suffix(source_model),
                            "seed": seed,
                            "prediction_token": token,
                            "config_path": str(cfg_path),
                            "experiment_name": exp,
                            "method": "config_text_or_path_match",
                        })
    df = pd.DataFrame(rows).drop_duplicates() if rows else pd.DataFrame(columns=["source_model","source_suffix","seed","prediction_token","config_path","experiment_name","method"])
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "F4_source_to_prediction_token_candidates_from_run_configs.csv", index=False)
    LOGGER.info("Scanned local configs for source-token bridge: %d candidate rows", len(df))
    return df


def load_explicit_source_token_map(path: Optional[Path], out_dir: Path) -> pd.DataFrame:
    if path is None or not Path(path).exists():
        return pd.DataFrame(columns=["source_model","seed","prediction_token","method"])
    p = Path(path)
    df = pd.read_excel(p) if p.suffix.lower() in [".xlsx", ".xls"] else pd.read_csv(p)
    cols = {c.lower(): c for c in df.columns}
    sm_col = next((cols[k] for k in cols if k in ["source_model", "model", "config", "experiment_name"]), None)
    tok_col = next((cols[k] for k in cols if k in ["prediction_token", "model_token", "token", "run_token"]), None)
    seed_col = next((cols[k] for k in cols if k == "seed"), None)
    if sm_col is None or tok_col is None:
        raise ValueError(f"Source-token map must have source_model/model and prediction_token/model_token columns: {df.columns.tolist()}")
    out = pd.DataFrame({
        "source_model": df[sm_col].astype(str).map(normalize_model_token),
        "source_suffix": df[sm_col].astype(str).map(source_suffix),
        "prediction_token": df[tok_col].astype(str).map(normalize_model_token),
        "seed": df[seed_col].astype(str) if seed_col else "",
        "method": "explicit_csv",
    })
    out.to_csv(out_dir / "F4_source_to_prediction_token_EXPLICIT.csv", index=False)
    return out


def build_available_tokens_by_seed(preds_all: Mapping[str, Any], basin_ids: set[str]) -> Dict[str, List[str]]:
    by_seed: Dict[str, List[str]] = {}
    for seed, basin_dict in preds_all.items():
        if not isinstance(basin_dict, Mapping):
            continue
        seed_s = str(seed)
        # Use the first basin with predictions. All basins have the same model-token set/order per seed in legacy export.
        for basin, basin_value in basin_dict.items():
            bid = safe_zfill_basin(basin)
            if bid not in basin_ids:
                continue
            md = get_sim_model_dict(basin_value)
            if isinstance(md, Mapping) and len(md) > 0:
                by_seed[seed_s] = [str(k) for k in md.keys()]
                break
    return by_seed


def build_source_token_bridge(
    preds_all: Mapping[str, Any],
    basin_ids: set[str],
    slot_map: Mapping[int, List[str]],
    root: Path,
    explicit_map: Optional[Path],
    out_dir: Path,
) -> pd.DataFrame:
    """Return rows: seed, source_model, prediction_token, cluster slots.

    First use exact/explicit/config-derived mapping. For unresolved seeds/sources, use an auditable legacy positional bridge:
    the old All_Clusterwise export has one ordered list of prediction tokens for each seed. The cluster-slot file has
    an ordered list of 18 slots / 17 unique sources. The positional fallback maps unique sources, preserving first
    occurrence and duplicate slots. If a seed has fewer tokens than unique sources, the script maps the common prefix
    and records the remaining source(s) as missing for that seed; local ensembles for affected cluster-slots then use
    the available subset rather than inventing predictions.
    """
    available = build_available_tokens_by_seed(preds_all, basin_ids)
    avail_rows = []
    for seed, toks in available.items():
        for i, tok in enumerate(toks, 1):
            avail_rows.append({"seed": seed, "token_order": i, "prediction_token": tok})
    pd.DataFrame(avail_rows).to_csv(out_dir / "F4_available_prediction_tokens_by_seed.csv", index=False)

    unique_sources: List[str] = []
    source_clusters: Dict[str, List[int]] = {}
    for cl in sorted(slot_map):
        for sm in slot_map[cl]:
            if sm not in unique_sources:
                unique_sources.append(sm)
            source_clusters.setdefault(sm, []).append(int(cl))

    explicit_df = load_explicit_source_token_map(explicit_map, out_dir) if explicit_map else pd.DataFrame()
    config_df = scan_run_configs_for_source_token_map(root, slot_map, out_dir)
    candidate_df = pd.concat([explicit_df, config_df], ignore_index=True) if not explicit_df.empty or not config_df.empty else pd.DataFrame(columns=["source_model","seed","prediction_token","method"])

    rows = []
    # Add explicit/config matches only if their tokens are actually present in each seed.
    for seed, toks in available.items():
        tok_set = set(toks)
        for sm in unique_sources:
            matched = []
            if not candidate_df.empty:
                sub = candidate_df[candidate_df["source_model"].map(normalize_model_token).eq(normalize_model_token(sm))].copy()
                # Prefer seed-specific rows, but allow seedless rows.
                sub_seed = sub[(sub.get("seed", "").astype(str).eq(str(seed))) | (sub.get("seed", "").astype(str).isin(["", "nan", "None"]))] if "seed" in sub.columns else sub
                for _, r in sub_seed.iterrows():
                    tok = normalize_model_token(r["prediction_token"])
                    if tok in tok_set:
                        matched.append((tok, r.get("method", "candidate")))
            if matched:
                tok, method = matched[0]
                rows.append({"seed": seed, "source_model": sm, "source_suffix": source_suffix(sm), "prediction_token": tok, "method": method, "selected_clusters": "|".join(map(str, sorted(set(source_clusters.get(sm, [])))))})

    mapped = pd.DataFrame(rows)
    mapped_keys = set(zip(mapped.get("seed", []), mapped.get("source_model", []))) if not mapped.empty else set()

    # Positional fallback for unresolved seeds/sources. This is audit-first and does not claim hidden certainty.
    fallback_rows = []
    for seed, toks in available.items():
        n = min(len(toks), len(unique_sources))
        for i in range(n):
            sm = unique_sources[i]
            if (seed, sm) in mapped_keys:
                continue
            fallback_rows.append({
                "seed": seed,
                "source_model": sm,
                "source_suffix": source_suffix(sm),
                "prediction_token": toks[i],
                "source_order": i + 1,
                "token_order": i + 1,
                "method": "legacy_position_fallback",
                "selected_clusters": "|".join(map(str, sorted(set(source_clusters.get(sm, [])))))
            })
        for j in range(n, len(unique_sources)):
            sm = unique_sources[j]
            fallback_rows.append({
                "seed": seed,
                "source_model": sm,
                "source_suffix": source_suffix(sm),
                "prediction_token": "",
                "source_order": j + 1,
                "token_order": "",
                "method": "missing_no_prediction_token_in_seed",
                "selected_clusters": "|".join(map(str, sorted(set(source_clusters.get(sm, [])))))
            })
    fallback_df = pd.DataFrame(fallback_rows)
    bridge = pd.concat([mapped, fallback_df], ignore_index=True) if not mapped.empty else fallback_df
    # Drop duplicate seed-source mappings, prefer non-fallback.
    if not bridge.empty:
        bridge["priority"] = bridge["method"].map(lambda x: 0 if str(x).startswith("explicit") or str(x).startswith("config") else 1 if str(x)=="legacy_position_fallback" else 2)
        bridge = bridge.sort_values(["seed", "source_model", "priority"]).drop_duplicates(["seed", "source_model"], keep="first")
        bridge = bridge.drop(columns=["priority"])
    bridge.to_csv(out_dir / "F4_SOURCE_TO_PREDICTION_TOKEN_BRIDGE_FINAL.csv", index=False)
    summ = {
        "n_rows": int(len(bridge)),
        "n_sources": int(len(unique_sources)),
        "n_seeds": int(len(available)),
        "n_mapped_nonempty": int((bridge["prediction_token"].astype(str) != "").sum()) if not bridge.empty else 0,
        "methods": bridge["method"].value_counts().to_dict() if not bridge.empty else {},
        "note": "Rows with legacy_position_fallback should be checked against local config manifests if available; they are used only to avoid re-running old global ensembles.",
    }
    write_json(summ, out_dir / "F4_SOURCE_TO_PREDICTION_TOKEN_BRIDGE_FINAL.summary.json")
    LOGGER.info("Built F4 source-token bridge: %s", summ)
    return bridge


def build_f4_legacy_ensemble(
    preds_all: Mapping[str, Any],
    basin_ids: set[str],
    cluster_map: Mapping[str, int],
    base: int,
    slot_map: Mapping[int, List[str]],
    bridge: pd.DataFrame,
    agg: str,
    out_audit: Path,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    # cluster -> source_model list is slot_map. Bridge gives source_model -> token for each seed.
    token_by_seed_source: Dict[Tuple[str, str], str] = {}
    for _, r in bridge.iterrows():
        tok = str(r.get("prediction_token", ""))
        if tok and tok.lower() not in ["nan", "none"]:
            token_by_seed_source[(str(r["seed"]), str(r["source_model"]))] = tok

    buckets: Dict[Tuple[str, str], List[Tuple[str, str, Any]]] = {}
    records = []
    for seed, basin_dict in preds_all.items():
        seed_s = str(seed)
        if not isinstance(basin_dict, Mapping):
            continue
        for basin, basin_value in basin_dict.items():
            bid = safe_zfill_basin(basin)
            if bid not in basin_ids:
                continue
            cl = normalize_cluster_id(cluster_map.get(bid), base)
            allowed_sources = slot_map.get(int(cl), []) if cl is not None else []
            md = get_sim_model_dict(basin_value)
            if not isinstance(md, Mapping):
                continue
            available_tokens = set(str(k) for k in md.keys())
            for rank, source_model in enumerate(allowed_sources, 1):
                tok = token_by_seed_source.get((seed_s, source_model), "")
                used = False
                reason = ""
                pred_obj = None
                if tok and tok in md:
                    used = True
                    pred_obj = md[tok]
                    reason = "matched_by_bridge"
                elif tok:
                    reason = "bridge_token_not_in_basin_model_dict"
                else:
                    reason = "no_token_for_source_seed"
                records.append({
                    "seed": seed_s,
                    "basin": bid,
                    "basin_cluster": cl,
                    "slot_rank": rank,
                    "source_model": source_model,
                    "prediction_token": tok,
                    "used": used,
                    "reason": reason,
                    "available_n_tokens": len(available_tokens),
                })
                if used:
                    buckets.setdefault((bid, seed_s), []).append((source_model, tok, pred_obj))
    rec_df = pd.DataFrame(records)
    out_audit.parent.mkdir(parents=True, exist_ok=True)
    rec_df.to_csv(out_audit, index=False)
    if not buckets:
        raise RuntimeError(f"No F4 predictions available for agg={agg}. See {out_audit}")
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    count_rows = []
    for (basin, seed), members in buckets.items():
        arrs = []
        ref = None
        for src, tok, po in members:
            da = to_dataarray(po, SIM_KEY)
            if ref is None:
                ref = da
            arrs.append(da_values(da))
        L = min(len(a) for a in arrs)
        stack = np.stack([a[:L] for a in arrs], axis=0)
        ens_da = make_ensemble_da(stack, ref, agg=agg, n_members=len(arrs))
        out.setdefault(basin, {})[seed] = {"ensemble": ens_da}
        count_rows.append({"basin": basin, "seed": seed, "n_members": len(arrs), "members": "|".join([m[1] for m in members]), "sources": "|".join([m[0] for m in members])})
    counts = pd.DataFrame(count_rows)
    counts.to_csv(out_audit.with_name(out_audit.stem + "_COUNTS.csv"), index=False)
    LOGGER.info("Built F4 %s ensemble: basins=%d basin-seed=%d members min=%d median=%.1f max=%d", agg, len(out), len(count_rows), int(counts.n_members.min()), float(counts.n_members.median()), int(counts.n_members.max()))
    return out


def lookup_basin_value(mapping: Mapping[str, Any], basin: str) -> Any:
    """Lookup a basin without boolean-evaluating xarray/pandas objects.

    The v12 code used `dict.get(a) or dict.get(b)`, which can fail or silently
    skip observations because xarray objects do not have a safe truth value.
    This function tries the legacy key variants explicitly.
    """
    b = str(basin)
    candidates = []
    candidates.append(b)
    candidates.append(safe_zfill_basin(b))
    if b.isdigit():
        candidates.append(str(int(b)))
    # Keep order but remove duplicates.
    seen = set()
    for k in candidates:
        if k in seen:
            continue
        seen.add(k)
        if k in mapping:
            return mapping[k]
    raise KeyError(f"Basin {basin!r} not found; tried {candidates}")


def load_obs_series(obs_dict: Mapping[str, Any], basin: str) -> np.ndarray:
    obj = lookup_basin_value(obs_dict, basin)
    return da_values(to_dataarray(obj, OBS_KEY))


def _valid(o, s):
    L = min(len(o), len(s))
    o = np.asarray(o[:L], float); s = np.asarray(s[:L], float)
    m = np.isfinite(o) & np.isfinite(s)
    return o[m], s[m]


def metric_nse(o, s):
    o, s = _valid(o, s); den = np.sum((o - np.mean(o)) ** 2) if len(o) else np.nan
    return float(1 - np.sum((s - o) ** 2) / den) if len(o) > 1 and den != 0 else np.nan

def metric_mse(o, s):
    o, s = _valid(o, s); return float(np.mean((s - o) ** 2)) if len(o) else np.nan

def metric_rmse(o, s):
    v = metric_mse(o, s); return float(np.sqrt(v)) if np.isfinite(v) else np.nan

def metric_pearson(o, s):
    o, s = _valid(o, s); return float(np.corrcoef(o, s)[0, 1]) if len(o) > 1 and np.std(o) != 0 and np.std(s) != 0 else np.nan

def metric_kge(o, s):
    o, s = _valid(o, s)
    if len(o) < 2 or np.std(o) == 0 or np.std(s) == 0 or np.mean(o) == 0: return np.nan
    r = metric_pearson(o, s); a = np.std(s) / np.std(o); b = np.mean(s) / np.mean(o)
    return float(1 - np.sqrt((r - 1) ** 2 + (a - 1) ** 2 + (b - 1) ** 2))

def metric_peak_mape(o, s):
    o, s = _valid(o, s)
    if len(o) < 3 or not SCIPY_AVAILABLE: return np.nan
    peaks, _ = scipy_signal.find_peaks(o, distance=100, prominence=np.std(o))
    if len(peaks) == 0: return np.nan
    den = o[peaks]; mask = den != 0
    return float(np.mean(np.abs((s[peaks][mask] - den[mask]) / den[mask])) * 100) if np.any(mask) else np.nan

def metric_mape(o, s):
    o, s = _valid(o, s); mask = o != 0
    return float(np.mean(np.abs((s[mask] - o[mask]) / o[mask])) * 100) if np.any(mask) else np.nan


def compute_seed_metrics(ensembles: Mapping[str, Mapping[str, Any]], obs: Mapping[str, Any], framework_id: str) -> pd.DataFrame:
    rows = []
    for basin, seed_dict in ensembles.items():
        bid = safe_zfill_basin(basin)
        try:
            o = load_obs_series(obs, bid)
        except Exception:
            continue
        for seed, pred_dict in seed_dict.items():
            try:
                s = da_values(to_dataarray(pred_dict["ensemble"], SIM_KEY))
                rows.append({
                    "model": framework_id,
                    "basin": bid,
                    "seed": str(seed),
                    "NSE": metric_nse(o, s),
                    "KGE": metric_kge(o, s),
                    "MSE": metric_mse(o, s),
                    "RMSE": metric_rmse(o, s),
                    "Pearson-r": metric_pearson(o, s),
                    "Peak-MAPE": metric_peak_mape(o, s),
                    "MAPE": metric_mape(o, s),
                })
            except Exception as e:
                rows.append({"model": framework_id, "basin": bid, "seed": str(seed), "error": repr(e)})
    return pd.DataFrame(rows)


def sfmean_by_basin(seed_metrics: pd.DataFrame) -> pd.DataFrame:
    required = {"model", "basin"}
    if seed_metrics.empty:
        raise RuntimeError("F4 metric table is empty. Check obs lookup and F4 ensemble member audit files.")
    missing = required.difference(seed_metrics.columns)
    if missing:
        raise RuntimeError(f"F4 metric table is missing required columns {sorted(missing)}. Columns={seed_metrics.columns.tolist()} rows={len(seed_metrics)}")
    metric_cols = [c for c in ["NSE", "KGE", "MSE", "RMSE", "Pearson-r", "Peak-MAPE", "MAPE"] if c in seed_metrics.columns]
    if not metric_cols:
        raise RuntimeError(f"F4 metric table has no numeric metric columns. Columns={seed_metrics.columns.tolist()}")
    out = seed_metrics.groupby(["model", "basin"], as_index=False)[metric_cols].mean(numeric_only=True)
    return out.rename(columns={c: f"SFmean_{c}" for c in metric_cols})


def summarize_frameworks(sf: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    rows = []
    for model, sub in sf.groupby("model"):
        row = {"model": model, "n_basins": len(sub)}
        for c in [x for x in sub.columns if x.startswith("SFmean_")]:
            vals = pd.to_numeric(sub[c], errors="coerce")
            row[f"{c}_mean"] = float(vals.mean())
            row[f"{c}_median"] = float(vals.median())
            row[f"{c}_p25"] = float(vals.quantile(.25))
            row[f"{c}_p75"] = float(vals.quantile(.75))
        if "SFmean_NSE" in sub.columns:
            vals = pd.to_numeric(sub["SFmean_NSE"], errors="coerce")
            for thr in [0.5, 0.6, 0.7, 0.8, 0.9]:
                row[f"NSE_ge_{thr}"] = int((vals >= thr).sum())
            row["NSE_lt_0.5"] = int((vals < 0.5).sum())
        rows.append(row)
    summary = pd.DataFrame(rows)
    summary.to_csv(out_dir / "F4_framework_summary.csv", index=False)
    return summary


def compare_against_previous(f4_sf: pd.DataFrame, prev_sf_path: Optional[Path], out_dir: Path) -> None:
    if prev_sf_path is None or not Path(prev_sf_path).exists():
        LOGGER.warning("No previous SFmean file found for comparison")
        return
    prev = pd.read_csv(prev_sf_path)
    combined = pd.concat([prev, f4_sf], ignore_index=True, sort=False)
    combined.to_csv(out_dir / "F4_plus_previous_SFmean_by_basin.csv", index=False)
    summarize_frameworks(combined, out_dir)
    if "SFmean_NSE" not in combined.columns:
        return
    pivot = combined.pivot_table(index="basin", columns="model", values="SFmean_NSE", aggfunc="first")
    f4_models = [c for c in pivot.columns if str(c).startswith("F4_clusterlocal_top3_owncluster")]
    baselines = [c for c in pivot.columns if c not in f4_models]
    rows = []
    for f4 in f4_models:
        for base in baselines:
            sub = pivot[[f4, base]].dropna()
            if sub.empty:
                continue
            d = sub[f4] - sub[base]
            rows.append({
                "comparison": f"{f4} minus {base}",
                "n_basins": len(d),
                "mean_delta_NSE": float(d.mean()),
                "median_delta_NSE": float(d.median()),
                "share_improved": float((d > 0).mean()),
                "n_improved": int((d > 0).sum()),
                "n_worse": int((d < 0).sum()),
            })
    pd.DataFrame(rows).to_csv(out_dir / "F4_paired_NSE_comparisons_vs_previous.csv", index=False)
    LOGGER.info("Wrote F4 comparisons against previous SFmean: %s", prev_sf_path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="F4-only cluster-local Top3 own-cluster builder")
    p.add_argument("--root", type=Path, default=Path(r"F:\Experiments\CAMELS_US\Clean_4_upload"))
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--pickle-dir", type=Path, default=None)
    p.add_argument("--clusters", type=Path, default=None)
    p.add_argument("--cluster-configs-xlsx", type=Path, default=None)
    p.add_argument("--source-token-map", type=Path, default=None)
    p.add_argument("--previous-sfmean", type=Path, default=None)
    p.add_argument("--save-ensembles", action="store_true")
    p.add_argument("--strict-no-positional-fallback", action="store_true")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root
    pickle_dir = args.pickle_dir or (root / "Pickles")
    work_root = args.work_root or (root / "Revision_2026_Top18_4Framework" / "ensemble_framework_bot_runs")
    run_dir = work_root / f"CAMELS_F4_ONLY_eval_{time.strftime('%Y%m%d_%H%M%S')}_v13"
    dirs = {k: run_dir / k for k in ["00_audit", "01_ensembles_legacy_format", "02_metrics_legacy_format", "03_comparisons"]}
    for d in dirs.values(): d.mkdir(parents=True, exist_ok=True)
    setup_logging(run_dir)
    LOGGER.info("Starting F4-only v13 metrics fix")
    LOGGER.info("Run dir: %s", run_dir)

    clusters = args.clusters or find_file_recursive([root], ["camels_531_master_attributes_clusters.csv", "CAMELS_US_Clusters.xlsx"])
    xlsx = args.cluster_configs_xlsx or find_file_recursive([Path.cwd(), root], ["Clusters&Configs.xlsx", "Clusters_and_Configs.xlsx"])
    if clusters is None or not clusters.exists():
        raise FileNotFoundError("Cluster map file not found")
    if xlsx is None or not xlsx.exists():
        raise FileNotFoundError("Clusters&Configs.xlsx / slot map file not found")

    paths = {
        "Obs_test": pickle_dir / "Obs_test.p",
        "All_Clusterwise": pickle_dir / "All_Cluster_wise_Configs_CAMELSUS_test.p",
    }
    write_json({"root": str(root), "pickle_dir": str(pickle_dir), "clusters": str(clusters), "cluster_configs_xlsx": str(xlsx), "paths": {k: str(v) for k, v in paths.items()}}, dirs["00_audit"] / "input_manifest.json")

    cluster_map = load_cluster_map(clusters)
    base = cluster_base(cluster_map)
    slot_map = read_excel_slot_map(xlsx, base, dirs["00_audit"])
    basin_ids = set(cluster_map.keys())
    obs = load_pickle(paths["Obs_test"])
    all_cw = load_pickle(paths["All_Clusterwise"])
    inspect_structure(all_cw, basin_ids, dirs["00_audit"])

    bridge = build_source_token_bridge(all_cw, basin_ids, slot_map, root, args.source_token_map, dirs["00_audit"])
    if args.strict_no_positional_fallback and (bridge["method"].astype(str).str.contains("legacy_position_fallback|missing_no_prediction", regex=True).any()):
        raise RuntimeError("Strict mode: source-token bridge contains fallback/missing rows. See audit bridge CSV.")

    legacy_ensembles = {}
    for agg in ["median", "mean"]:
        f4 = build_f4_legacy_ensemble(
            all_cw, basin_ids, cluster_map, base, slot_map, bridge, agg,
            dirs["00_audit"] / f"F4_clusterlocal_{agg}_members.csv"
        )
        model_id = f"F4_clusterlocal_top3_owncluster_{agg}"
        legacy_ensembles[model_id] = f4
        if args.save_ensembles:
            save_pickle(f4, dirs["01_ensembles_legacy_format"] / f"ensemble_ClusterLocal_Top3OwnCluster_CAMELSUS_test_{agg.upper()}_LEGACY_FORMAT.p")

    metrics_frames = []
    for model_id, ens in legacy_ensembles.items():
        LOGGER.info("Computing F4 seed-level metrics for %s", model_id)
        metrics_frames.append(compute_seed_metrics(ens, obs, model_id))
    seed_metrics = pd.concat(metrics_frames, ignore_index=True)
    seed_metrics.to_csv(dirs["02_metrics_legacy_format"] / "F4_metrics_all_test_period_seed_level_LEGACY_FORMAT.csv", index=False)
    save_pickle(seed_metrics, dirs["02_metrics_legacy_format"] / "F4_metrics_all_test_period_seed_level_LEGACY_FORMAT.p")
    f4_sf = sfmean_by_basin(seed_metrics)
    f4_sf.to_csv(dirs["02_metrics_legacy_format"] / "F4_metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.csv", index=False)
    save_pickle(f4_sf, dirs["02_metrics_legacy_format"] / "F4_metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.p")
    summarize_frameworks(f4_sf, dirs["03_comparisons"])

    prev = args.previous_sfmean or find_latest_previous_sfmean(work_root)
    compare_against_previous(f4_sf, prev, dirs["03_comparisons"])

    LOGGER.info("Done. F4-only results saved under: %s", run_dir)
    print("\n=== CAMELS F4-only v13 finished ===")
    print(f"Run directory: {run_dir}")
    print("Key outputs:")
    print(f"  {dirs['00_audit'] / 'F4_SOURCE_TO_PREDICTION_TOKEN_BRIDGE_FINAL.csv'}")
    print(f"  {dirs['00_audit'] / 'F4_clusterlocal_median_members_COUNTS.csv'}")
    print(f"  {dirs['02_metrics_legacy_format'] / 'F4_metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.csv'}")
    print(f"  {dirs['03_comparisons'] / 'F4_paired_NSE_comparisons_vs_previous.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
