#!/usr/bin/env python3
"""
CAMELS-US hydrologically informed (HI) constituent decomposition — 10-seed protocol.

Purpose
-------
Evaluate each of the 17 UNIQUE regionally trained configurations represented by the
18 cluster-conditioned HI selection slots, using every archived final realization
available within the prespecified 10-seed protocol, and compare each constituent with
the frozen pooled hydrologically informed ensemble on the same seeds available for
that constituent.

Scientific safeguards
---------------------
- no training;
- no test-based constituent/member selection;
- the full prespecified final seed set is used;
- one historical constituent has fewer completed archived final realizations; it is
  evaluated on all of its available final seeds and its pooled-HI comparison is made
  on exactly the same seed subset (no imputation, no seed substitution);
- source-model identity is anchored to the previously verified source->prediction-token
  mapping and extended to the remaining final runs by scientific configuration
  fingerprint, ignoring run-specific seed/path metadata;
- the raw HI archive token set is checked independently for every basin and seed;
- the pooled HI median is independently rebuilt from the actually available selected
  members for each of the 10 seeds and checked against the frozen ensemble before
  scientific interpretation;
- metrics are calculated per basin x seed and then averaged across all available final
  seed-level values for that constituent; paired pooled-HI comparisons use the exact
  same seed subset as the constituent.

HI-CFG-01 ... HI-CFG-17 are arbitrary source-token-sorted identifiers. They are NOT
validation ranks and must never be described as ranks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import re
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

try:
    import yaml
except Exception as exc:
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc

try:
    from scipy.stats import wilcoxon, binomtest
except Exception as exc:
    raise SystemExit("SciPy is required: python -m pip install scipy") from exc

VERSION = "2.0.0-10seed-protocol-publication-gate"
ALL_SEEDS = [191889, 307443, 328237, 385445, 473461, 643969, 665980, 845563, 985957, 993061]
ANCHOR_SEEDS = [643969, 665980, 845563, 985957, 993061]
CORE = ["NSE", "KGE", "Pearson-r", "RMSE"]
BOOT_SEED = 20260826
N_BOOT = 10_000
MAX_REBUILD_TOL = 1.0e-5
MEAN_REBUILD_TOL = 1.0e-7
EXPECTED_HI10_MEAN_NSE = 0.775966
EXPECTED_HI10_MEDIAN_NSE = 0.815440
HERE = Path(__file__).resolve().parent
SELECTION_CSV = HERE / "frozen_selection_manifest.csv"
ANCHOR_MAPPING_CSV = HERE / "verified_mapping_anchor5.csv"
SIM_KEY = "QObs(mm/d)_sim"
TOKEN_RE = re.compile(r"(?<!\d)(\d{4}_\d{6})(?!\d)")

# Scientific identity fields; seed/path/date are deliberately excluded.
FINGERPRINT_FIELDS = [
    "model", "seq_length", "hidden_size", "initial_forget_bias", "output_dropout",
    "batch_size", "learning_rate", "target_noise_std", "loss", "epochs",
    "dynamic_inputs", "static_attributes", "forcings", "target_variables",
    "clip_targets_to_zero", "predict_last_n",
]


def log(msg: str = "") -> None:
    print(msg, flush=True)


def norm_basin(x: Any) -> str:
    s = str(x).strip()
    try:
        return f"{int(float(s)):08d}"
    except Exception:
        return s


def norm_seed(x: Any) -> str:
    try:
        return str(int(x))
    except Exception:
        return str(x).strip()


def find_key_by_norm(d: Mapping[Any, Any], target: Any, normalizer) -> Any:
    t = normalizer(target)
    for k in d.keys():
        if normalizer(k) == t:
            return k
    return None


def to_1d_array(x: Any) -> np.ndarray:
    if hasattr(x, "values"):
        x = x.values
    a = np.asarray(x, dtype=float).squeeze()
    if a.ndim != 1:
        raise ValueError(f"Expected 1D hydrograph, got {a.shape}")
    return a


def install_legacy_pickle_compat() -> None:
    import types
    module_name = "pandas.core.indexes.numeric"
    if module_name not in sys.modules:
        mod = types.ModuleType(module_name)
        for cls in ("NumericIndex", "Int64Index", "UInt64Index", "Float64Index"):
            setattr(mod, cls, pd.Index)
        sys.modules[module_name] = mod


def load_pickle(path: Path) -> Any:
    log(f"Loading pickle: {path}")
    install_legacy_pickle_compat()
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


def get_member_map(all_hi: Mapping, seed: int, basin: str) -> Mapping[str, Any]:
    sk = find_key_by_norm(all_hi, seed, norm_seed)
    if sk is None:
        raise KeyError(f"Seed missing from raw HI archive: {seed}")
    sd = all_hi[sk]
    bk = find_key_by_norm(sd, basin, norm_basin)
    if bk is None:
        raise KeyError(f"Basin missing from raw HI archive: seed={seed}, basin={basin}")
    obj = sd[bk]
    if isinstance(obj, Mapping) and SIM_KEY in obj and isinstance(obj[SIM_KEY], Mapping):
        return obj[SIM_KEY]
    if isinstance(obj, Mapping):
        candidate_maps = [v for v in obj.values() if isinstance(v, Mapping) and v]
        for v in candidate_maps:
            if any(re.fullmatch(r"\d{4}_\d{6}", str(k)) for k in v.keys()):
                return v
        if len(candidate_maps) == 1:
            return candidate_maps[0]
    raise KeyError(f"Cannot locate HI member map: seed={seed}, basin={basin}")


def get_obs(obs: Mapping, basin: str) -> Any:
    bk = find_key_by_norm(obs, basin, norm_basin)
    if bk is None:
        raise KeyError(f"Observation missing: {basin}")
    x = obs[bk]
    if isinstance(x, Mapping):
        for k, v in x.items():
            if "obs" in str(k).lower():
                return v
        if len(x) == 1:
            return next(iter(x.values()))
    return x


def get_ensemble_series(ens: Mapping, basin: str, seed: int) -> Any:
    bk = find_key_by_norm(ens, basin, norm_basin)
    if bk is not None and isinstance(ens[bk], Mapping):
        sk = find_key_by_norm(ens[bk], seed, norm_seed)
        if sk is not None:
            x = ens[bk][sk]
            if isinstance(x, Mapping):
                if "ensemble" in x:
                    return x["ensemble"]
                if len(x) == 1:
                    return next(iter(x.values()))
            return x
    sk = find_key_by_norm(ens, seed, norm_seed)
    if sk is not None and isinstance(ens[sk], Mapping):
        bk = find_key_by_norm(ens[sk], basin, norm_basin)
        if bk is not None:
            x = ens[sk][bk]
            if isinstance(x, Mapping):
                if "ensemble" in x:
                    return x["ensemble"]
                if len(x) == 1:
                    return next(iter(x.values()))
            return x
    raise KeyError(f"Ensemble missing: basin={basin}, seed={seed}")


def clean_pair(obs: Any, sim: Any) -> tuple[np.ndarray, np.ndarray]:
    o = to_1d_array(obs)
    s = to_1d_array(sim)
    n = min(o.size, s.size)
    o, s = o[:n], s[:n]
    m = np.isfinite(o) & np.isfinite(s)
    return o[m], s[m]


def calc_metrics(obs: Any, sim: Any) -> dict[str, float]:
    o, s = clean_pair(obs, sim)
    if o.size < 3:
        return {k: np.nan for k in CORE}
    den = np.sum((o - np.mean(o)) ** 2)
    nse = 1 - np.sum((s - o) ** 2) / den if den > 0 else np.nan
    rmse = float(np.sqrt(np.mean((s - o) ** 2)))
    so, ss = np.std(o, ddof=0), np.std(s, ddof=0)
    r = float(np.corrcoef(o, s)[0, 1]) if so > 0 and ss > 0 else np.nan
    mo, ms = np.mean(o), np.mean(s)
    alpha = ss / so if so > 0 else np.nan
    beta = ms / mo if mo != 0 else np.nan
    kge = (
        1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)
        if np.isfinite(r) and np.isfinite(alpha) and np.isfinite(beta)
        else np.nan
    )
    return {"NSE": float(nse), "KGE": float(kge), "Pearson-r": float(r), "RMSE": rmse}


def bh_fdr(pvals: list[float]) -> list[float]:
    p = np.asarray(pvals, float)
    out = np.full_like(p, np.nan)
    good = np.isfinite(p)
    idx = np.where(good)[0]
    if idx.size == 0:
        return out.tolist()
    order = idx[np.argsort(p[idx])]
    m = len(order)
    q = np.empty(m, float)
    prev = 1.0
    for j in range(m - 1, -1, -1):
        rank = j + 1
        val = min(prev, p[order[j]] * m / rank)
        q[j] = val
        prev = val
    for j, i in enumerate(order):
        out[i] = min(q[j], 1.0)
    return out.tolist()


def bootstrap_ci_median(x: np.ndarray) -> tuple[float, float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return np.nan, np.nan
    rng = np.random.default_rng(BOOT_SEED)
    meds = np.empty(N_BOOT, float)
    n = len(x)
    for i in range(N_BOOT):
        meds[i] = np.median(x[rng.integers(0, n, n)])
    lo, hi = np.percentile(meds, [2.5, 97.5])
    return float(lo), float(hi)


def paired_stats(basin_df: pd.DataFrame, first: str, ref: str) -> pd.DataFrame:
    rows, pvals = [], []
    for met in CORE:
        a = basin_df.loc[basin_df.method == first, ["basin", met]].rename(columns={met: "a"})
        b = basin_df.loc[basin_df.method == ref, ["basin", met]].rename(columns={met: "b"})
        z = a.merge(b, on="basin", how="inner").dropna()
        d = (z.b.to_numpy() - z.a.to_numpy()) if met == "RMSE" else (z.a.to_numpy() - z.b.to_numpy())
        nz = d[d != 0]
        try:
            wp = float(wilcoxon(nz, alternative="two-sided").pvalue) if len(nz) else 1.0
        except Exception:
            wp = np.nan
        pos, neg, ties = int(np.sum(d > 0)), int(np.sum(d < 0)), int(np.sum(d == 0))
        sp = float(binomtest(pos, n=pos + neg, p=0.5, alternative="two-sided").pvalue) if pos + neg else 1.0
        lo, hi = bootstrap_ci_median(d)
        rows.append({
            "comparison": f"{first} vs {ref}", "metric": met, "n": len(d),
            "wins": pos, "losses": neg, "ties": ties, "win_rate": pos / len(d),
            "mean_effect": float(np.mean(d)), "median_effect": float(np.median(d)),
            "ci95_lo": lo, "ci95_hi": hi, "wilcoxon_p": wp, "sign_p": sp,
        })
        pvals.append(wp)
    qs = bh_fdr(pvals)
    for row, q in zip(rows, qs):
        row["wilcoxon_fdr_p"] = q
    return pd.DataFrame(rows)


def add_global_fdr(df: pd.DataFrame) -> pd.DataFrame:
    z = df.copy()
    z["wilcoxon_global_fdr_p"] = bh_fdr(z["wilcoxon_p"].tolist())
    return z


def resolve_pickles_dir(root: Path, supplied: str) -> Path:
    required = {
        "All_Cluster_wise_Configs_CAMELSUS_test.p",
        "ensemble_Cluster_wise_CAMELSUS_test.p",
        "Obs_test.p",
    }
    if supplied.lower() != "auto":
        p = Path(supplied)
        if p.name.lower() == "pickles":
            pdir = p
        elif (p / "pickles").is_dir():
            pdir = p / "pickles"
        elif (p / "Pickles").is_dir():
            pdir = p / "Pickles"
        else:
            pdir = p
        missing = [x for x in required if not (pdir / x).exists()]
        if missing:
            raise FileNotFoundError(f"Supplied data directory lacks required pickles: {missing}; checked {pdir}")
        return pdir

    direct = [root / "Pickles", root / "pickles", root / "DATA_ZENODO" / "pickles"]
    try:
        for child in root.iterdir():
            if child.is_dir():
                direct.extend([child / "DATA_ZENODO" / "pickles", child / "pickles", child / "Pickles"])
    except Exception:
        pass
    seen = set()
    for pdir in direct:
        key = str(pdir).lower()
        if key in seen:
            continue
        seen.add(key)
        if all((pdir / x).exists() for x in required):
            log(f"Auto-detected HI pickle directory: {pdir}")
            return pdir

    hits = []
    for p in root.rglob("All_Cluster_wise_Configs_CAMELSUS_test.p"):
        pdir = p.parent
        if all((pdir / x).exists() for x in required):
            hits.append(pdir)
    uniq = []
    for p in hits:
        if p not in uniq:
            uniq.append(p)
    if len(uniq) == 1:
        log(f"Auto-detected HI pickle directory: {uniq[0]}")
        return uniq[0]
    if len(uniq) > 1:
        sigs = {}
        for pdir in uniq:
            sig = tuple((pdir / x).stat().st_size for x in sorted(required))
            sigs.setdefault(sig, []).append(pdir)
        if len(sigs) == 1:
            chosen = sorted(uniq, key=lambda p: (0 if p.name == "Pickles" and p.parent == root else 1, len(str(p))))[0]
            log(f"Multiple equivalent-size HI pickle copies found; using: {chosen}")
            return chosen
        raise RuntimeError("Multiple non-equivalent HI pickle directories found. Rerun with --data-dir PATH:\n" + "\n".join(map(str, uniq)))
    raise FileNotFoundError("Could not locate required HI pickles. Rerun with --data-dir pointing to DATA_ZENODO or its pickles folder.")


def load_design() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SELECTION_CSV.exists() or not ANCHOR_MAPPING_CSV.exists():
        raise FileNotFoundError("Package design files are missing")
    sel = pd.read_csv(SELECTION_CSV, dtype={"source_model": str})
    if len(sel) != 18 or sel.source_model.nunique() != 17:
        raise RuntimeError(f"Selection gate failed: expected 18 slots / 17 unique configs; got {len(sel)} / {sel.source_model.nunique()}")
    if sel.groupby("cluster").size().to_dict() != {1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3}:
        raise RuntimeError("Selection gate failed: expected exactly 3 slots per cluster")

    mp = pd.read_csv(ANCHOR_MAPPING_CSV, dtype={"source_model": str, "prediction_token": str})
    mp["seed"] = pd.to_numeric(mp["seed"], errors="raise").astype(int)
    if len(mp) != 85 or set(mp.seed.unique()) != set(ANCHOR_SEEDS):
        raise RuntimeError("Anchor mapping gate failed: expected 17 sources x 5 verified anchor seeds = 85 rows")
    expected_sources = set(sel.source_model.astype(str).unique())
    if set(mp.source_model.astype(str).unique()) != expected_sources:
        raise RuntimeError("Anchor mapping source set differs from the frozen 17 unique HI selections")
    for seed, g in mp.groupby("seed"):
        if len(g) != 17 or g.source_model.nunique() != 17 or g.prediction_token.nunique() != 17:
            raise RuntimeError(f"Anchor mapping uniqueness failed for seed {seed}")
    return sel, mp


def basins_from_obs(obs: Mapping) -> list[str]:
    basins = sorted({norm_basin(k) for k in obs.keys() if re.fullmatch(r"\d{8}", norm_basin(k))})
    if len(basins) != 531:
        raise RuntimeError(f"Basin gate failed: expected 531 observation basins, found {len(basins)}")
    return basins


def discover_seed_token_sets(all_hi: Mapping, basins: list[str], out: Path) -> dict[int, set[str]]:
    sets: dict[int, set[str]] = {}
    rows = []
    for seed in ALL_SEEDS:
        first = set(map(str, get_member_map(all_hi, seed, basins[0]).keys()))
        if len(first) not in (16, 17):
            raise RuntimeError(f"Unexpected HI member count for seed {seed}: {len(first)}; expected 16 or 17")
        for basin in basins:
            actual = set(map(str, get_member_map(all_hi, seed, basin).keys()))
            rows.append({"seed": seed, "basin": basin, "n_members": len(actual), "same_as_seed_reference": actual == first})
            if actual != first:
                raise RuntimeError(f"HI archive token set varies across basins for seed={seed}; first mismatch at basin={basin}")
        sets[seed] = first
    pd.DataFrame(rows).to_csv(out / "00_ARCHIVE_TOKEN_SET_CONSISTENCY_531x10.csv", index=False)
    counts = {s: len(t) for s, t in sets.items()}
    if sorted(counts.values()) != [16] * 5 + [17] * 5:
        raise RuntimeError(f"Unexpected 10-seed HI member-count pattern: {counts}; expected five 17-member and five 16-member seeds")
    if any(counts[s] != 17 for s in ANCHOR_SEEDS):
        raise RuntimeError(f"Verified anchor seeds are not all 17-member seeds: {counts}")
    log(f"ARCHIVE 10-SEED GATE: PASS; member counts by seed={counts}")
    return sets


def scan_configs(root: Path, prediction_tokens: set[str]) -> pd.DataFrame:
    search_roots = [root / "Models", root / "Revision_2026_Top18_4Framework"]
    rows = []
    seen = set()
    for sr in search_roots:
        if not sr.exists():
            continue
        for p in sr.rglob("config.y*ml"):
            tok = token_from_path_or_text(p)
            if tok not in prediction_tokens:
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                cfg = read_yaml(p)
                fp = config_fingerprint(cfg)
                seed = cfg.get("seed")
                try:
                    seed = int(seed)
                except Exception:
                    seed = None
                rows.append({
                    "prediction_token": tok,
                    "seed_in_config": seed,
                    "fingerprint": fp,
                    "config_path": str(p),
                    "core_json": json.dumps(config_core(cfg), sort_keys=True, ensure_ascii=False, default=str),
                })
            except Exception as exc:
                rows.append({"prediction_token": tok, "seed_in_config": None, "fingerprint": None, "config_path": str(p), "error": str(exc)})
    if not rows:
        raise RuntimeError("No final-run config.yml files could be mapped to HI prediction tokens")
    df = pd.DataFrame(rows)
    amb = df.dropna(subset=["fingerprint"]).groupby("prediction_token").fingerprint.nunique()
    bad = amb[amb > 1]
    if len(bad):
        raise RuntimeError(f"Ambiguous scientific config identity for prediction tokens: {bad.index.tolist()[:10]}")
    return df.sort_values("config_path").drop_duplicates(["prediction_token", "fingerprint"])


def build_full_mapping(root: Path, seed_token_sets: dict[int, set[str]], anchor: pd.DataFrame, selection: pd.DataFrame, out: Path) -> pd.DataFrame:
    all_tokens = set().union(*seed_token_sets.values())
    cfg = scan_configs(root, all_tokens)
    cfg.to_csv(out / "01_prediction_token_config_fingerprints.csv", index=False)

    fp_by_token = cfg.dropna(subset=["fingerprint"]).drop_duplicates("prediction_token").set_index("prediction_token")["fingerprint"].to_dict()
    path_by_token = cfg.drop_duplicates("prediction_token").set_index("prediction_token")["config_path"].to_dict()
    missing_cfg = sorted(all_tokens - set(fp_by_token))
    if missing_cfg:
        raise RuntimeError(f"CONFIG IDENTITY GATE failed: {len(missing_cfg)} HI tokens lack readable config fingerprints: {missing_cfg[:10]}")

    # Establish source scientific identity from the previously verified 85 anchor mappings.
    anchor2 = anchor.copy()
    anchor2["fingerprint"] = anchor2.prediction_token.map(fp_by_token)
    if anchor2.fingerprint.isna().any():
        miss = anchor2.loc[anchor2.fingerprint.isna(), "prediction_token"].tolist()
        raise RuntimeError(f"Anchor token fingerprints missing: {miss[:10]}")
    nfp = anchor2.groupby("source_model").fingerprint.nunique()
    if (nfp != 1).any():
        raise RuntimeError("A verified source_model maps to multiple scientific fingerprints across anchor seeds")
    source_fp = anchor2.groupby("source_model").fingerprint.first().to_dict()
    if len(set(source_fp.values())) != 17:
        raise RuntimeError("The 17 frozen HI sources do not map to 17 unique scientific fingerprints")
    fp_source = {fp: src for src, fp in source_fp.items()}
    if set(source_fp) != set(selection.source_model.astype(str).unique()):
        raise RuntimeError("Anchor fingerprint source set does not match frozen HI selection manifest")

    rows = []
    for seed in ALL_SEEDS:
        for tok in sorted(seed_token_sets[seed]):
            fp = fp_by_token[tok]
            src = fp_source.get(fp)
            if src is None:
                raise RuntimeError(f"HI token {tok} on seed {seed} has a scientific fingerprint not represented by the verified 17 source configurations")
            rows.append({
                "seed": seed,
                "source_model": src,
                "prediction_token": tok,
                "fingerprint": fp,
                "config_path": path_by_token.get(tok, ""),
            })
    full = pd.DataFrame(rows)

    # No seed may contain duplicate final realizations of the same selected scientific configuration.
    dup = full.groupby(["seed", "source_model"]).size()
    if (dup > 1).any():
        raise RuntimeError("At least one seed contains multiple prediction tokens for the same HI scientific configuration")

    expected_sources = set(selection.source_model.astype(str).unique())
    counts = full.groupby("source_model").seed.nunique().reindex(sorted(expected_sources), fill_value=0)
    expected_availability = [7, 8] + [10] * 15
    if sorted(counts.tolist()) != expected_availability:
        raise RuntimeError(
            f"Unexpected constituent availability pattern: {counts.to_dict()}; "
            f"expected frozen-archive pattern {expected_availability}"
        )
    if set(full.source_model.unique()) != expected_sources:
        raise RuntimeError("Full mapping does not cover exactly the 17 frozen HI source configurations")

    # Cross-check that all 85 previously verified mappings are reproduced exactly.
    chk = anchor.merge(full[["seed", "source_model", "prediction_token"]], on=["seed", "source_model"], how="left", suffixes=("_anchor", "_full"))
    if chk.prediction_token_full.isna().any() or not (chk.prediction_token_anchor == chk.prediction_token_full).all():
        raise RuntimeError("The 10-seed scientific-fingerprint mapping does not reproduce the previously verified anchor mappings exactly")

    full.to_csv(out / "02_verified_mapping_full_10seed_protocol.csv", index=False)
    pd.DataFrame([{"source_model": s, "n_available_final_seeds": int(n), "available_seeds": "|".join(map(str, sorted(full.loc[full.source_model == s, "seed"].unique())))} for s, n in counts.items()]).to_csv(out / "02_constituent_seed_availability.csv", index=False)
    log("FULL IDENTITY GATE: PASS (17 unique HI configurations; 15 have 10 archived final seeds, one has 8, and one has 7)")
    return full


def validate_archive_tokens(all_hi: Mapping, basins: list[str], mapping: pd.DataFrame, out: Path) -> None:
    expected = {int(seed): set(g.prediction_token.astype(str)) for seed, g in mapping.groupby("seed")}
    rows = []
    for seed in ALL_SEEDS:
        exp = expected[seed]
        for basin in basins:
            actual = set(map(str, get_member_map(all_hi, seed, basin).keys()))
            rows.append({
                "seed": seed, "basin": basin, "n_expected": len(exp), "n_actual": len(actual),
                "missing": "|".join(sorted(exp - actual)), "extra": "|".join(sorted(actual - exp)),
                "exact_set_match": actual == exp,
            })
    a = pd.DataFrame(rows)
    a.to_csv(out / "00_ARCHIVE_TOKEN_GATE_531x10.csv", index=False)
    if len(a) != 531 * 10 or not a.exact_set_match.all():
        raise RuntimeError("Raw HI archive token gate failed; see 00_ARCHIVE_TOKEN_GATE_531x10.csv")
    log("ARCHIVE TOKEN GATE: PASS (531 basins x 10 seeds; exact available-member token set per seed)")


def rebuild_hi_and_validate(all_hi: Mapping, published_hi: Mapping, basins: list[str], mapping: pd.DataFrame, out: Path) -> dict:
    expected = {int(seed): g.prediction_token.astype(str).tolist() for seed, g in mapping.groupby("seed")}
    rows = []
    diffs = []
    for seed in ALL_SEEDS:
        toks = expected[seed]
        for basin in basins:
            mm = get_member_map(all_hi, seed, basin)
            arrs = [to_1d_array(mm[t]) for t in toks]
            shapes = {a.shape for a in arrs}
            if len(arrs) not in (16, 17) or len(shapes) != 1:
                raise RuntimeError(f"HI rebuild member/shape gate failed basin={basin} seed={seed}")
            rebuilt = np.nanmedian(np.stack(arrs, axis=0), axis=0)
            frozen = to_1d_array(get_ensemble_series(published_hi, basin, seed))
            n = min(len(rebuilt), len(frozen))
            d = np.abs(rebuilt[:n] - frozen[:n])
            mx = float(np.nanmax(d)) if d.size else np.nan
            md = float(np.nanmean(d)) if d.size else np.nan
            rows.append({"seed": seed, "basin": basin, "n_members": len(toks), "max_abs_diff": mx, "mean_abs_diff": md})
            if d.size:
                diffs.append(d[np.isfinite(d)])
    gate = pd.DataFrame(rows)
    gate.to_csv(out / "00_HI_10SEED_REBUILD_GATE.csv", index=False)
    all_d = np.concatenate([d for d in diffs if len(d)]) if diffs else np.array([])
    overall_max = float(np.max(all_d)) if all_d.size else np.nan
    overall_mean = float(np.mean(all_d)) if all_d.size else np.nan
    log(f"HI 10-SEED REBUILD GATE: n={len(rows)}, max_abs_diff={overall_max:.9g}, mean_abs_diff={overall_mean:.9g}; tolerances max<={MAX_REBUILD_TOL:.1e}, mean<={MEAN_REBUILD_TOL:.1e}")
    if len(rows) != 531 * 10 or not np.isfinite(overall_max) or overall_max > MAX_REBUILD_TOL or overall_mean > MEAN_REBUILD_TOL:
        raise RuntimeError("Frozen pooled HI ensemble does not match the available-member pointwise median within float tolerance")
    log("HI 10-SEED REBUILD GATE: PASS")
    return {"n_basin_seed": len(rows), "max_abs_diff": overall_max, "mean_abs_diff": overall_mean}


def build_identity_table(selection: pd.DataFrame, mapping: pd.DataFrame, out: Path) -> pd.DataFrame:
    sources = sorted(selection.source_model.astype(str).unique())
    rows = []
    for i, src in enumerate(sources, 1):
        selg = selection[selection.source_model.astype(str) == src]
        mpg = mapping[mapping.source_model.astype(str) == src]
        rows.append({
            "constituent_id": f"HI-CFG-{i:02d}",
            "source_model": src,
            "selected_in_clusters": "|".join(map(str, sorted(selg.cluster.astype(int).tolist()))),
            "selection_slots": len(selg),
            "n_available_final_seeds": mpg.seed.nunique(),
            "available_seeds": "|".join(map(str, sorted(mpg.seed.unique()))),
            "n_prediction_tokens": mpg.prediction_token.nunique(),
            "seq_length": selg.iloc[0].get("seq_length"),
            "hidden_size": selg.iloc[0].get("hidden_size"),
            "batch_size": selg.iloc[0].get("batch_size"),
            "loss": selg.iloc[0].get("loss"),
            "output_dropout": selg.iloc[0].get("output_dropout"),
            "initial_forget_bias": selg.iloc[0].get("initial_forget_bias"),
            "target_noise_std": selg.iloc[0].get("target_noise_std"),
        })
    d = pd.DataFrame(rows)
    d.to_csv(out / "03_hi17_constituent_identity.csv", index=False)
    if len(d) != 17 or sorted(d.n_available_final_seeds.tolist()) != [7, 8] + [10] * 15:
        raise RuntimeError("HI constituent identity/seed-availability gate failed")
    return d


def evaluate(all_hi: Mapping, published_hi: Mapping, obs: Mapping, basins: list[str], mapping: pd.DataFrame, ids: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    token = {(int(r.seed), str(r.source_model)): str(r.prediction_token) for _, r in mapping.iterrows()}
    id_by_source = dict(zip(ids.source_model.astype(str), ids.constituent_id.astype(str)))
    rows = []
    member_gate = []

    # Frozen pooled HI across the complete 10-seed protocol.
    for basin in basins:
        o = get_obs(obs, basin)
        for seed in ALL_SEEDS:
            sim = get_ensemble_series(published_hi, basin, seed)
            rows.append({"method": "Pooled-HI", "basin": basin, "seed": seed, **calc_metrics(o, sim)})

    # Each unique selected scientific configuration in isolation, using every archived final seed available for it.
    for src in sorted(id_by_source):
        cid = id_by_source[src]
        sub = mapping[mapping.source_model.astype(str) == src].sort_values("seed")
        seeds = sub.seed.astype(int).tolist()
        n_series = 0
        toks = []
        for seed in seeds:
            tok = token[(seed, src)]
            toks.append(tok)
            for basin in basins:
                mm = get_member_map(all_hi, seed, basin)
                if tok not in mm:
                    raise RuntimeError(f"Missing constituent token {tok}: {cid}, seed={seed}, basin={basin}")
                sim = mm[tok]
                o = get_obs(obs, basin)
                rows.append({"method": cid, "basin": basin, "seed": seed, **calc_metrics(o, sim)})
                n_series += 1
        member_gate.append({
            "constituent_id": cid, "source_model": src,
            "n_available_final_seeds": len(seeds),
            "available_seeds": "|".join(map(str, seeds)),
            "n_prediction_tokens": len(set(toks)),
            "n_basin_seed_series": n_series,
            "tokens": "|".join(toks),
        })
        if n_series != 531 * len(seeds) or len(set(toks)) != len(seeds):
            raise RuntimeError(f"Constituent member gate failed for {cid}")

    mg = pd.DataFrame(member_gate)
    mg.to_csv(out / "03_constituent_member_gate.csv", index=False)
    if sorted(mg.n_available_final_seeds.tolist()) != [7, 8] + [10] * 15:
        raise RuntimeError("Constituent member gate has unexpected seed availability")
    log("CONSTITUENT MEMBER GATE: PASS (all archived final realizations used across the prespecified 10-seed protocol)")

    seed_df = pd.DataFrame(rows)
    seed_df.to_csv(out / "04_seed_level_metrics_pooledHI_and_17_constituents.csv", index=False)
    basin_df = seed_df.groupby(["method", "basin"], as_index=False)[CORE].mean()
    basin_df.to_csv(out / "05_basin_mean_across_available_final_seeds.csv", index=False)
    return seed_df, basin_df


def absolute_summary(basin_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, g in basin_df.groupby("method"):
        for met in CORE:
            x = g[met].dropna().to_numpy(float)
            rows.append({
                "method": method, "metric": met, "n": len(x),
                "across_basin_mean": float(np.mean(x)),
                "across_basin_median": float(np.median(x)),
                "q25": float(np.quantile(x, .25)), "q75": float(np.quantile(x, .75)),
                "min": float(np.min(x)), "max": float(np.max(x)),
            })
    return pd.DataFrame(rows)


def seed_regional(seed_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, seed), g in seed_df.groupby(["method", "seed"]):
        for met in CORE:
            x = g[met].dropna().to_numpy(float)
            rows.append({
                "method": method, "seed": int(seed), "metric": met, "n": len(x),
                "regional_mean": float(np.mean(x)), "regional_median": float(np.median(x)),
            })
    return pd.DataFrame(rows)


def matched_basin_pair(seed_df: pd.DataFrame, constituent_id: str) -> tuple[pd.DataFrame, list[int]]:
    seeds = sorted(seed_df.loc[seed_df.method == constituent_id, "seed"].astype(int).unique().tolist())
    if len(seeds) not in (7, 8, 10):
        raise RuntimeError(f"Unexpected available seed count for {constituent_id}: {len(seeds)}")
    z = seed_df[(seed_df.method.isin(["Pooled-HI", constituent_id])) & (seed_df.seed.isin(seeds))]
    counts = z.groupby(["method", "basin"]).seed.nunique()
    if counts.min() != len(seeds) or counts.max() != len(seeds):
        raise RuntimeError(f"Matched seed coverage is incomplete for {constituent_id}")
    basin = z.groupby(["method", "basin"], as_index=False)[CORE].mean()
    return basin, seeds


def normalize_basin_for_legacy(x: Any) -> str | None:
    s = str(x)
    m = re.search(r"(?<!\d)(\d{8})(?!\d)", s)
    if m:
        return m.group(1)
    if s.isdigit() and 6 <= len(s) <= 8:
        return s.zfill(8)
    return None


def normalize_seed_for_legacy(x: Any) -> int | None:
    try:
        v = int(str(x))
        return v if v in ALL_SEEDS else None
    except Exception:
        return None


def extract_baseline_metrics_pickle(path: Path, basins: list[str]) -> pd.DataFrame | None:
    try:
        obj = load_pickle(path)
    except Exception:
        return None
    basin_set = set(basins)
    rows = []
    method_aliases = ("benchmark", "kratzert", "reference")
    metric_alias = {"nse": "NSE", "kge": "KGE", "pearson-r": "Pearson-r", "pearson_r": "Pearson-r", "pearson": "Pearson-r", "r": "Pearson-r", "rmse": "RMSE"}

    def walk(x, path=()):
        if isinstance(x, dict):
            for k, v in x.items():
                yield from walk(v, path + (k,))
        elif isinstance(x, (list, tuple)):
            for i, v in enumerate(x):
                yield from walk(v, path + (i,))
        elif np.isscalar(x) and not isinstance(x, (str, bytes, bool)):
            yield path, x

    for path_parts, val in walk(obj):
        txt = "/".join(map(str, path_parts)).lower()
        if not any(a in txt for a in method_aliases):
            continue
        basin = seed = met = None
        for p in path_parts:
            if basin is None:
                b = normalize_basin_for_legacy(p)
                if b in basin_set:
                    basin = b
            if seed is None:
                seed = normalize_seed_for_legacy(p)
            lp = str(p).lower().strip()
            for a, m in metric_alias.items():
                if lp == a or a in lp:
                    met = m
        if basin and met:
            try:
                rows.append({"basin": basin, "seed": seed, "metric": met, "value": float(val)})
            except Exception:
                pass
    if not rows:
        return None
    d = pd.DataFrame(rows).drop_duplicates()
    records = defaultdict(dict)
    for (b, m), g in d.groupby(["basin", "metric"]):
        if g.seed.notna().sum() >= 10:
            vals = g.dropna(subset=["seed"]).drop_duplicates("seed").value.to_numpy(float)
            v = float(np.mean(vals))
        else:
            vals = g.value.to_numpy(float)
            if len(vals) != 1:
                continue
            v = float(vals[0])
        records[b][m] = v
    df = pd.DataFrame([{"method": "Kratzert", "basin": b, **vals} for b, vals in records.items()])
    if len(df) != 531 or "NSE" not in df:
        return None
    for m in CORE:
        if m not in df.columns:
            df[m] = np.nan
    return df[["method", "basin"] + CORE]


def load_canonical_kratzert(root: Path, basins: list[str]) -> pd.DataFrame | None:
    candidates = [
        root / "Revision_2026_Top18_4Framework" / "Top18_vs_Top10_Final_Analysis" / "CANONICAL_MEANSEED_REAGGREGATION" / "01_basin_mean_across_10_seeds.csv",
        root / "CANONICAL_MEANSEED_REAGGREGATION" / "01_basin_mean_across_10_seeds.csv",
    ]
    candidates.extend(list(root.glob("Revision_2026_Top18_4Framework/**/01_basin_mean_across_10_seeds.csv")))
    basin_set = set(basins)
    seen = set()
    for p in candidates:
        if str(p) in seen or not p.exists():
            continue
        seen.add(str(p))
        try:
            d = pd.read_csv(p)
        except Exception:
            continue
        need = {"basin", "method", "metric", "basin_seed_mean"}
        if not need.issubset(d.columns):
            continue
        k = d[d.method.astype(str).str.lower().isin(["benchmark", "kratzert", "kratzert reference", "reference"])].copy()
        if k.empty:
            continue
        k["basin"] = k.basin.map(norm_basin)
        k = k[k.basin.isin(basin_set)]
        piv = k.pivot_table(index="basin", columns="metric", values="basin_seed_mean", aggfunc="first").reset_index()
        piv = piv.rename(columns={"Pearson_r": "Pearson-r", "Pearson": "Pearson-r"})
        if len(piv) != 531 or "NSE" not in piv.columns:
            continue
        for m in CORE:
            if m not in piv.columns:
                piv[m] = np.nan
        piv.insert(0, "method", "Kratzert")
        mean, med = float(piv.NSE.mean()), float(piv.NSE.median())
        if abs(mean - 0.753311) <= 0.0015 and abs(med - 0.792028) <= 0.0015:
            return piv[["method", "basin"] + CORE]
    legacy = root / "Pickles" / "metrics_all_test_period.p"
    if legacy.exists():
        kr = extract_baseline_metrics_pickle(legacy, basins)
        if kr is not None:
            mean, med = float(kr.NSE.mean()), float(kr.NSE.median())
            if abs(mean - 0.753311) <= 0.003 and abs(med - 0.792028) <= 0.003:
                return kr
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"F:\Experiments\CAMELS_US\Clean_4_upload")
    ap.add_argument("--data-dir", default="auto", help="DATA_ZENODO, pickles folder, or auto")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.out) if args.out else root / "Revision_2026_Top18_4Framework" / "HI17_CONSTITUENT_DECOMPOSITION_10SEED_FINAL"
    out.mkdir(parents=True, exist_ok=True)

    log("=" * 100)
    log("CAMELS-US HI17 CONSTITUENT DECOMPOSITION — 10-SEED FRAMEWORK PROTOCOL")
    log("No training. No test-based constituent selection. All archived final realizations are used; constituent comparisons are seed-matched to each constituent.")
    log("=" * 100)
    log(f"ROOT: {root}")
    log(f"OUT : {out}")

    try:
        selection, anchor = load_design()
        log("DESIGN GATE: PASS (18 cluster-conditioned selection slots -> 17 unique source configurations)")

        pdir = resolve_pickles_dir(root, args.data_dir)
        all_hi = load_pickle(pdir / "All_Cluster_wise_Configs_CAMELSUS_test.p")
        published_hi = load_pickle(pdir / "ensemble_Cluster_wise_CAMELSUS_test.p")
        obs = load_pickle(pdir / "Obs_test.p")

        basins = basins_from_obs(obs)
        log(f"BASIN GATE: PASS ({len(basins)})")

        seed_token_sets = discover_seed_token_sets(all_hi, basins, out)
        mapping = build_full_mapping(root, seed_token_sets, anchor, selection, out)
        validate_archive_tokens(all_hi, basins, mapping, out)
        rebuild = rebuild_hi_and_validate(all_hi, published_hi, basins, mapping, out)
        ids = build_identity_table(selection, mapping, out)
        log("IDENTITY GATE: PASS (17 unique HI scientific configurations; one source occupies two selection slots)")

        seed_df, basin_df = evaluate(all_hi, published_hi, obs, basins, mapping, ids, out)
        absum = absolute_summary(basin_df)
        absum.to_csv(out / "06_absolute_summary.csv", index=False)

        hi_nse = absum[(absum.method == "Pooled-HI") & (absum.metric == "NSE")].iloc[0]
        hi_mean, hi_median = float(hi_nse.across_basin_mean), float(hi_nse.across_basin_median)
        log(f"POOLED HI 10-SEED METRIC SELF-CHECK: mean NSE={hi_mean:.6f}; median NSE={hi_median:.6f}")
        if abs(hi_mean - EXPECTED_HI10_MEAN_NSE) > 0.002 or abs(hi_median - EXPECTED_HI10_MEDIAN_NSE) > 0.002:
            raise RuntimeError("Pooled HI 10-seed metric self-check deviates from the canonical manuscript values")
        log("POOLED HI 10-SEED METRIC SELF-CHECK: PASS")

        # Pooled HI vs every constituent, with exact seed matching for that constituent.
        comp_rows = []
        for cid in ids.constituent_id:
            matched, seeds = matched_basin_pair(seed_df, cid)
            z = paired_stats(matched, "Pooled-HI", cid)
            z.insert(1, "constituent_id", cid)
            src = ids.loc[ids.constituent_id == cid, "source_model"].iloc[0]
            z.insert(2, "source_model", src)
            z.insert(3, "n_matched_final_seeds", len(seeds))
            z.insert(4, "matched_seeds", "|".join(map(str, seeds)))
            comp_rows.append(z)
        pooled_stats = add_global_fdr(pd.concat(comp_rows, ignore_index=True))
        pooled_stats.to_csv(out / "07_pooledHI_vs_each_constituent_core_stats.csv", index=False)

        # Canonical Kratzert context, based on each constituent's basin metric averaged over all its archived final realizations.
        kr = load_canonical_kratzert(root, basins)
        kr_stats = None
        all_basin = basin_df.copy()
        if kr is not None:
            all_basin = pd.concat([all_basin, kr], ignore_index=True)
            krows = []
            for cid in ids.constituent_id:
                z = paired_stats(all_basin, cid, "Kratzert")
                z.insert(1, "constituent_id", cid)
                src = ids.loc[ids.constituent_id == cid, "source_model"].iloc[0]
                nseed = int(ids.loc[ids.constituent_id == cid, "n_available_final_seeds"].iloc[0])
                z.insert(2, "source_model", src)
                z.insert(3, "n_constituent_final_seeds", nseed)
                krows.append(z)
            kr_stats = add_global_fdr(pd.concat(krows, ignore_index=True))
            kr_stats.to_csv(out / "08_each_constituent_vs_kratzert_context.csv", index=False)
            log(f"KRATZERT CONTEXT GATE: PASS; mean NSE={kr.NSE.mean():.6f}; median NSE={kr.NSE.median():.6f}")
        else:
            log("KRATZERT CONTEXT: canonical basin table not recovered automatically; pooled-HI-vs-constituent control remains complete.")

        seed_reg = seed_regional(seed_df)
        seed_reg.to_csv(out / "09_seed_level_regional_summary.csv", index=False)

        constituent_nse = absum[(absum.metric == "NSE") & absum.method.str.startswith("HI-CFG-")].copy().sort_values("method")
        constituent_nse = constituent_nse.merge(ids[["constituent_id", "source_model", "selected_in_clusters", "selection_slots", "n_available_final_seeds"]], left_on="method", right_on="constituent_id", how="left")
        constituent_nse.to_csv(out / "10_constituent_NSE_summary.csv", index=False)

        pnse = pooled_stats[pooled_stats.metric == "NSE"].copy().sort_values("constituent_id")
        pkge = pooled_stats[pooled_stats.metric == "KGE"].copy()
        ppr = pooled_stats[pooled_stats.metric == "Pearson-r"].copy()
        prmse = pooled_stats[pooled_stats.metric == "RMSE"].copy()

        # Seed-level descriptive dominance for every seed on which each constituent exists.
        nse_seed = seed_reg[seed_reg.metric == "NSE"]
        seed_checks = []
        for cid in ids.constituent_id:
            seeds = sorted(seed_df.loc[seed_df.method == cid, "seed"].astype(int).unique().tolist())
            for seed in seeds:
                hirow = nse_seed[(nse_seed.method == "Pooled-HI") & (nse_seed.seed == seed)].iloc[0]
                crow = nse_seed[(nse_seed.method == cid) & (nse_seed.seed == seed)].iloc[0]
                seed_checks.append({
                    "seed": seed, "constituent_id": cid,
                    "pooled_mean_NSE": hirow.regional_mean, "constituent_mean_NSE": crow.regional_mean,
                    "pooled_mean_better": hirow.regional_mean > crow.regional_mean,
                    "pooled_median_NSE": hirow.regional_median, "constituent_median_NSE": crow.regional_median,
                    "pooled_median_better": hirow.regional_median > crow.regional_median,
                })
        seed_checks = pd.DataFrame(seed_checks)
        seed_checks.to_csv(out / "11_seedwise_pooledHI_vs_constituents_NSE.csv", index=False)

        seed_avail = ids.n_available_final_seeds.value_counts().sort_index().to_dict()
        kr_status = "PASS_CANONICAL" if kr is not None else "NOT_RECOVERED"
        summary = {
            "status": "PASS",
            "version": VERSION,
            "design": "17 unique HI configurations represented by 18 cluster-conditioned selection slots, evaluated across the prespecified 10-seed final protocol using every archived final realization available for each constituent. Pooled-HI-vs-constituent comparisons are seed-matched to that constituent; no missing realization is imputed.",
            "prespecified_final_seeds": ALL_SEEDS,
            "n_selection_slots": 18,
            "n_unique_constituents": 17,
            "constituent_ids_are_validation_ranks": False,
            "constituent_seed_availability_counts": {str(k): int(v) for k, v in seed_avail.items()},
            "pooled_hi_10seed_mean_nse": hi_mean,
            "pooled_hi_10seed_median_nse": hi_median,
            "constituent_mean_nse_min": float(constituent_nse.across_basin_mean.min()),
            "constituent_mean_nse_median": float(constituent_nse.across_basin_mean.median()),
            "constituent_mean_nse_max": float(constituent_nse.across_basin_mean.max()),
            "constituent_median_nse_min": float(constituent_nse.across_basin_median.min()),
            "constituent_median_nse_median": float(constituent_nse.across_basin_median.median()),
            "constituent_median_nse_max": float(constituent_nse.across_basin_median.max()),
            "n_constituents_pooledHI_positive_median_paired_NSE": int((pnse.median_effect > 0).sum()),
            "n_constituents_pooledHI_winrate_over_50_NSE": int((pnse.win_rate > 0.5).sum()),
            "n_constituents_pooledHI_positive_median_paired_KGE": int((pkge.median_effect > 0).sum()),
            "n_constituents_pooledHI_positive_median_paired_Pearson": int((ppr.median_effect > 0).sum()),
            "n_constituents_pooledHI_positive_median_paired_RMSE": int((prmse.median_effect > 0).sum()),
            "n_seed_constituent_pairs": int(len(seed_checks)),
            "seed_constituent_pairs_pooled_mean_NSE_better": int(seed_checks.pooled_mean_better.sum()),
            "seed_constituent_pairs_pooled_median_NSE_better": int(seed_checks.pooled_median_better.sum()),
            "rebuild": rebuild,
            "kratzert_context_status": kr_status,
        }
        if kr is not None and kr_stats is not None:
            knse = kr_stats[kr_stats.metric == "NSE"]
            summary.update({
                "kratzert_mean_nse": float(kr.NSE.mean()),
                "kratzert_median_nse": float(kr.NSE.median()),
                "n_constituents_mean_nse_above_kratzert": int((constituent_nse.across_basin_mean > float(kr.NSE.mean())).sum()),
                "n_constituents_median_nse_above_kratzert": int((constituent_nse.across_basin_median > float(kr.NSE.median())).sum()),
                "n_constituents_positive_median_paired_NSE_vs_kratzert": int((knse.median_effect > 0).sum()),
                "n_constituents_winrate_over_50_NSE_vs_kratzert": int((knse.win_rate > 0.5).sum()),
            })
        (out / "RUN_SUMMARY.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

        with (out / "MANUSCRIPT_READY.txt").open("w", encoding="utf-8") as f:
            f.write("CAMELS-US HI17 CONSTITUENT DECOMPOSITION — 10-SEED PROTOCOL — MANUSCRIPT READY\n")
            f.write("=" * 94 + "\n\n")
            f.write("DESIGN\n")
            f.write("The hydrologically informed framework contains 18 cluster-conditioned selection slots and 17 unique regionally trained configurations. Constituent performance is evaluated using every archived final realization available within the prespecified 10-seed protocol; no missing realization is imputed or replaced. Pooled-HI-versus-constituent comparisons use exactly the same final-seed subset available for that constituent. HI-CFG-01...HI-CFG-17 are arbitrary source-token-sorted identifiers, NOT validation ranks.\n\n")
            f.write("PRIMARY AGGREGATION\n")
            f.write("Metrics are calculated per basin x seed and then averaged arithmetically across all archived final seeds available for that constituent. The frozen pooled HI ensemble is evaluated across all 10 final seeds. For each constituent-level paired comparison, pooled HI is re-aggregated over the identical seed subset used by that constituent. The raw available-member pointwise median is independently rebuilt for every basin and all 10 seeds and must match the frozen pooled ensemble before analysis proceeds.\n\n")
            f.write(f"Pooled HI 10-seed: mean NSE={hi_mean:.6f}; median NSE={hi_median:.6f}\n")
            f.write(f"17 individual HI constituents, across-basin mean NSE range={constituent_nse.across_basin_mean.min():.6f} to {constituent_nse.across_basin_mean.max():.6f}; median across constituents={constituent_nse.across_basin_mean.median():.6f}\n")
            f.write(f"17 individual HI constituents, across-basin median NSE range={constituent_nse.across_basin_median.min():.6f} to {constituent_nse.across_basin_median.max():.6f}; median across constituents={constituent_nse.across_basin_median.median():.6f}\n")
            f.write(f"Pooled HI has positive median paired NSE effect versus {int((pnse.median_effect > 0).sum())}/17 constituents; basin win rate >50% versus {int((pnse.win_rate > 0.5).sum())}/17.\n")
            f.write(f"Pooled HI positive median effects: KGE {int((pkge.median_effect > 0).sum())}/17; Pearson-r {int((ppr.median_effect > 0).sum())}/17; RMSE {int((prmse.median_effect > 0).sum())}/17.\n")
            f.write(f"Seed-level descriptive dominance: pooled HI regional mean NSE better in {int(seed_checks.pooled_mean_better.sum())}/{len(seed_checks)} available seed-constituent pairs; regional median NSE better in {int(seed_checks.pooled_median_better.sum())}/{len(seed_checks)}.\n\n")
            f.write("POOLED HI VS EACH CONSTITUENT — NSE\n")
            f.write(pnse[["constituent_id", "source_model", "n_matched_final_seeds", "win_rate", "mean_effect", "median_effect", "ci95_lo", "ci95_hi", "wilcoxon_p", "wilcoxon_fdr_p", "wilcoxon_global_fdr_p"]].to_string(index=False, float_format=lambda x: f"{x:.8g}") + "\n\n")
            if kr is not None and kr_stats is not None:
                knse = kr_stats[kr_stats.metric == "NSE"].copy().sort_values("constituent_id")
                f.write("KRATZERT CONTEXT\n")
                f.write(f"Kratzert reference: mean NSE={kr.NSE.mean():.6f}; median NSE={kr.NSE.median():.6f}\n")
                f.write(f"HI constituents with across-basin mean NSE above Kratzert: {int((constituent_nse.across_basin_mean > float(kr.NSE.mean())).sum())}/17\n")
                f.write(f"HI constituents with across-basin median NSE above Kratzert: {int((constituent_nse.across_basin_median > float(kr.NSE.median())).sum())}/17\n")
                f.write(f"HI constituents with positive median paired NSE effect vs Kratzert: {int((knse.median_effect > 0).sum())}/17\n")
                f.write(knse[["constituent_id", "source_model", "n_constituent_final_seeds", "win_rate", "mean_effect", "median_effect", "ci95_lo", "ci95_hi", "wilcoxon_global_fdr_p"]].to_string(index=False, float_format=lambda x: f"{x:.8g}") + "\n\n")
            else:
                f.write("KRATZERT CONTEXT\nCanonical Kratzert basin metrics were not recovered automatically; no external-reference claim was guessed.\n\n")
            f.write("INTERPRETATION BOUNDARY\n")
            f.write("This experiment evaluates pooled hydrologically informed aggregation against its own 17 unique selected constituents within the full prespecified 10-seed protocol, using all archived final realizations and exact seed matching within each pooled-versus-constituent comparison. It tests whether pooled performance is reproduced by individual selected configurations in isolation. It does NOT isolate HPO causally, and it does NOT turn the arbitrary HI-CFG identifiers into validation ranks.\n")

        log("\n" + "=" * 100)
        log("FINAL HI17 10-SEED CONSTITUENT DECOMPOSITION GATE: PASS")
        log("=" * 100)
        log(f"Main result: {out / 'MANUSCRIPT_READY.txt'}")
        log(f"Pooled-HI-vs-constituent stats: {out / '07_pooledHI_vs_each_constituent_core_stats.csv'}")
        if kr_stats is not None:
            log(f"Constituent-vs-Kratzert context: {out / '08_each_constituent_vs_kratzert_context.csv'}")
        log(f"Run summary: {out / 'RUN_SUMMARY.json'}")
        return 0

    except Exception as exc:
        fail = out / "FAILED.txt"
        fail.write_text(str(exc) + "\n\n" + traceback.format_exc(), encoding="utf-8")
        log("\n" + "=" * 100)
        log("FINAL HI17 10-SEED CONSTITUENT DECOMPOSITION GATE: STOPPED / NOT SAFE TO INTERPRET")
        log("=" * 100)
        log(str(exc))
        log(traceback.format_exc())
        log("Stopped safely. No imputation, test-based constituent selection, or scientific guess was made.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
