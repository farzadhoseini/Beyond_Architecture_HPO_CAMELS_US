from pathlib import Path
import pandas as pd
import pickle
import json
import shutil
import os
import re

ROOT = Path(r"F:\Experiments\CAMELS_US\Clean_4_upload")
REV  = ROOT / "Revision_2026_Top18_4Framework"
RUNS = REV / "ensemble_framework_bot_runs"
OUT  = REV / "F4_CLUSTER_ROUTED_TOP3_PREFLIGHT_20260922"
OUT.mkdir(parents=True, exist_ok=True)

print("="*80)
print("CAMELS-US F4 / HI CLUSTER-ROUTED TOP3 — PREFLIGHT")
print("="*80)

# ------------------------------------------------------------
# 1. Core inputs
# ------------------------------------------------------------
core = {
    "cluster_map": ROOT / "camels_531_master_attributes_clusters.csv",
    "all_hi_predictions": ROOT / "Pickles" / "All_Cluster_wise_Configs_CAMELSUS_test.p",
    "hi_global_ensemble": ROOT / "Pickles" / "ensemble_Cluster_wise_CAMELSUS_test.p",
    "obs": ROOT / "Pickles" / "Obs_test.p",
    "current_canonical": REV / "Top18_vs_Top10_Final_Analysis" /
                         "CANONICAL_MEANSEED_REAGGREGATION" /
                         "01_basin_mean_across_10_seeds.csv",
}

rows = []
for k,p in core.items():
    rows.append({
        "item": k,
        "path": str(p),
        "exists": p.exists(),
        "size_MB": round(p.stat().st_size/1024**2, 3) if p.exists() else None
    })

pd.DataFrame(rows).to_csv(OUT/"00_core_input_inventory.csv", index=False)

print("\nCORE INPUTS")
for r in rows:
    print(f"{r['item']:25s} exists={r['exists']}  {r['path']}")

# ------------------------------------------------------------
# 2. Find all old F4 runs
# ------------------------------------------------------------
f4runs = sorted(
    [p for p in RUNS.glob("CAMELS_F4_ONLY_eval_*") if p.is_dir()],
    key=lambda p: p.stat().st_mtime,
)

print("\nOLD F4 RUNS:", len(f4runs))
for p in f4runs:
    print(" ", p)

run_inventory = []

for run in f4runs:
    for f in run.rglob("*"):
        if f.is_file():
            run_inventory.append({
                "run": run.name,
                "relative_path": str(f.relative_to(run)),
                "size_MB": round(f.stat().st_size/1024**2, 4)
            })

pd.DataFrame(run_inventory).to_csv(
    OUT/"01_old_F4_run_inventory.csv", index=False
)

# ------------------------------------------------------------
# 3. Find the newest old F4 run and audit its bridge/counts
# ------------------------------------------------------------
latest = f4runs[-1] if f4runs else None

summary = {
    "latest_old_f4_run": str(latest) if latest else None,
    "publishable_old_F4": False,
}

if latest:
    bridge_candidates = list(latest.rglob("*SOURCE_TO_PREDICTION_TOKEN_BRIDGE*.csv"))
    count_candidates  = list(latest.rglob("*members_COUNTS*.csv"))
    metric_candidates = list(latest.rglob("*F4_metrics*SFmean*csv"))
    paired_candidates = list(latest.rglob("*F4_paired*NSE*.csv"))

    def copy_candidates(files, prefix):
        for i,f in enumerate(files):
            shutil.copy2(f, OUT/f"{prefix}_{i}_{f.name}")

    copy_candidates(bridge_candidates, "OLD_BRIDGE")
    copy_candidates(count_candidates,  "OLD_MEMBERCOUNTS")
    copy_candidates(metric_candidates, "OLD_METRICS")
    copy_candidates(paired_candidates, "OLD_PAIRED")

    print("\nLATEST OLD F4:", latest)

    if bridge_candidates:
        b = pd.read_csv(bridge_candidates[0])
        print("\nBRIDGE COLUMNS:", list(b.columns))
        print(b.head(20).to_string(index=False))

        # generic mapping-method audit
        method_col = next(
            (c for c in b.columns if "method" in c.lower()),
            None
        )

        if method_col:
            vc = b[method_col].fillna("NA").value_counts(dropna=False)
            print("\nBRIDGE METHODS")
            print(vc)
            vc.rename_axis("mapping_method").reset_index(name="count").to_csv(
                OUT/"02_bridge_mapping_method_counts.csv", index=False
            )

    if count_candidates:
        c = pd.read_csv(count_candidates[0])
        print("\nMEMBER COUNT COLUMNS:", list(c.columns))
        print(c.head(20).to_string(index=False))

        numeric = c.select_dtypes(include="number")

        possible_member_cols = [
            col for col in numeric.columns
            if "member" in col.lower() or "count" in col.lower() or col.lower()=="n"
        ]

        member_col = possible_member_cols[-1] if possible_member_cols else None

        if member_col:
            vals = pd.to_numeric(c[member_col], errors="coerce").dropna()

            if len(vals):
                member_stats = {
                    "column": member_col,
                    "n_rows": int(len(vals)),
                    "min": float(vals.min()),
                    "median": float(vals.median()),
                    "max": float(vals.max()),
                    "n_eq_3": int((vals==3).sum()),
                    "n_lt_3": int((vals<3).sum()),
                    "n_gt_3": int((vals>3).sum()),
                }

                pd.DataFrame([member_stats]).to_csv(
                    OUT/"03_old_F4_member_count_summary.csv", index=False
                )

                print("\nOLD F4 MEMBER COUNT SUMMARY")
                print(member_stats)

                summary["old_F4_member_count_summary"] = member_stats

                if (
                    member_stats["n_rows"] == 5310 and
                    member_stats["min"] == 3 and
                    member_stats["max"] == 3
                ):
                    summary["publishable_old_F4"] = True

# ------------------------------------------------------------
# 4. Locate Clusters&Configs.xlsx copies
# ------------------------------------------------------------
search_roots = [
    Path(r"F:\Experiments\CAMELS_US\New_experiments"),
    ROOT,
]

xlsx_hits = []

for sr in search_roots:
    if not sr.exists():
        continue

    try:
        for p in sr.rglob("Clusters&Configs.xlsx"):
            xlsx_hits.append(p)
    except Exception:
        pass

print("\nClusters&Configs.xlsx hits:", len(xlsx_hits))

xlsx_inventory = []

for i,p in enumerate(xlsx_hits):
    rec = {
        "path": str(p),
        "size_KB": round(p.stat().st_size/1024,2),
    }

    try:
        xl = pd.ExcelFile(p)
        rec["sheets"] = "|".join(xl.sheet_names)

        for sh in xl.sheet_names:
            if "cluster" in sh.lower() or "config" in sh.lower():
                try:
                    d = pd.read_excel(p, sheet_name=sh)
                    d.to_csv(
                        OUT/f"04_xlsx_{i}_{re.sub('[^A-Za-z0-9]+','_',sh)}.csv",
                        index=False
                    )
                except Exception:
                    pass
    except Exception as e:
        rec["error"] = repr(e)

    xlsx_inventory.append(rec)

pd.DataFrame(xlsx_inventory).to_csv(
    OUT/"04_cluster_config_xlsx_inventory.csv", index=False
)

# ------------------------------------------------------------
# 5. Search for manifests/configs around selected HI model area
# ------------------------------------------------------------
candidate_roots = [
    ROOT / "Models" / "Cluster_wise_Configs_OverFittingChecked_Tested",
    REV,
]

manifest_patterns = (
    "*.yml","*.yaml","*.json","*.csv","*.txt"
)

manifest_rows = []

for cr in candidate_roots:
    if not cr.exists():
        continue

    for pat in manifest_patterns:
        try:
            for p in cr.rglob(pat):
                name = p.name.lower()
                pathlow = str(p).lower()

                if any(x in name or x in pathlow for x in [
                    "manifest","config","selected","seed","mapping","rank"
                ]):
                    manifest_rows.append({
                        "path": str(p),
                        "size_KB": round(p.stat().st_size/1024,2)
                    })
        except Exception:
            pass

pd.DataFrame(manifest_rows).drop_duplicates().to_csv(
    OUT/"05_candidate_manifest_inventory.csv", index=False
)

print("\nCandidate manifest/config files:", len(manifest_rows))

# ------------------------------------------------------------
# 6. Inspect All_Cluster_wise pickle structure read-only
# ------------------------------------------------------------
p = core["all_hi_predictions"]

if p.exists():
    print("\nLoading individual HI archive read-only:")
    print(p)

    with open(p, "rb") as fh:
        obj = pickle.load(fh)

    structure = {
        "type": str(type(obj)),
        "repr_head": repr(obj)[:5000]
    }

    (OUT/"06_all_clusterwise_pickle_structure.txt").write_text(
        json.dumps(structure, indent=2),
        encoding="utf-8"
    )

    print("Top-level type:", type(obj))
    if isinstance(obj, dict):
        print("Top-level keys sample:", list(obj.keys())[:20])
        print("Top-level key count:", len(obj))

# ------------------------------------------------------------
# 7. Locate old F4 bot code itself
# ------------------------------------------------------------
botroot = Path(r"F:\Experiments\CAMELS_US\New_experiments")

bot_hits = []

if botroot.exists():
    for p in botroot.rglob("*"):
        if not p.is_file():
            continue

        low = str(p).lower()

        if "f4" in low and p.suffix.lower() in {".py",".ps1",".xlsx",".csv",".json"}:
            bot_hits.append({
                "path": str(p),
                "size_KB": round(p.stat().st_size/1024,2)
            })

pd.DataFrame(bot_hits).to_csv(
    OUT/"07_old_F4_bot_inventory.csv", index=False
)

print("\nOld F4 bot-related files:", len(bot_hits))

# ------------------------------------------------------------
# 8. Final preflight decision
# ------------------------------------------------------------
summary["recommended_test"] = (
    "HI Cluster-Routed Top-3: for each basin use only the three "
    "regionally trained configurations selected from validation performance "
    "within that basin's fixed hydrologic cluster; pointwise median within "
    "each seed; metrics per seed; arithmetic mean of 10 seed-level metrics "
    "per basin."
)

summary["required_publishable_gate"] = (
    "531 basins x 10 seeds = 5310 basin-seed ensembles, exactly 3 "
    "cluster-associated prediction members available for every basin-seed; "
    "source-config -> final-run mapping must come from explicit manifest/config "
    "evidence, not positional fallback."
)

with open(OUT/"PRELIGHT_SUMMARY.json","w",encoding="utf-8") as f:
    json.dump(summary,f,indent=2)

print("\n" + "="*80)
print("PREFLIGHT DECISION")
print("="*80)

if summary["publishable_old_F4"]:
    print("OLD F4 MEMBER-COUNT GATE: PASS")
else:
    print("OLD F4 MEMBER-COUNT GATE: NOT CLEAN / REQUIRES EXACT RECONSTRUCTION")

print("""
Canonical experiment to run:
  basin -> fixed cluster
  fixed cluster -> validation-ranked Top3 regional configurations
  each seed -> pointwise median of ONLY those 3 predictions
  each basin -> compute metric per seed
  manuscript basin value -> arithmetic mean across the 10 seed metrics

This directly tests Reviewer #1 Comment 3.
""")

# ------------------------------------------------------------
# 9. ZIP
# ------------------------------------------------------------
zip_path = shutil.make_archive(str(OUT), "zip", root_dir=OUT)

print("OUTPUT FOLDER:")
print(OUT)
print("\nZIP:")
print(zip_path)
print("\nSend the ZIP + PowerShell output back to ChatGPT.")
