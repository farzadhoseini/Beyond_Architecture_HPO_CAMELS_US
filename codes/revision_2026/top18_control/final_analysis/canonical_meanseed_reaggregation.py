from pathlib import Path
import shutil
import sys
import numpy as np
import pandas as pd

try:
    from scipy.stats import wilcoxon, binomtest
except Exception as e:
    raise RuntimeError(
        "scipy is required. Run this script in the same Python environment "
        "used for the CAMELS analysis."
    ) from e


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(
    r"F:\Experiments\CAMELS_US\Clean_4_upload"
    r"\Revision_2026_Top18_4Framework"
    r"\Top18_vs_Top10_Final_Analysis"
)

TABLES = ROOT / "tables"
OUT = ROOT / "CANONICAL_MEANSEED_REAGGREGATION"
OUT.mkdir(parents=True, exist_ok=True)

LONG_CSV = TABLES / "overall_metrics_long.csv"
CLUSTER_CSV = TABLES / "basin_cluster_map_used.csv"

BOOT_SEED = 20260826
N_BOOT = 10000

PRIMARY_METHODS = ["Benchmark", "Top10", "Cluster-wise", "Top18"]
CORE_METRICS = ["NSE", "KGE", "Pearson-r", "RMSE"]

METHOD_PRETTY = {
    "Benchmark": "Kratzert reference",
    "Top10": "Top-10",
    "Cluster-wise": "Hydrologically informed",
    "Top18": "Top-18",
}

# Values currently reported in the primary manuscript.
# These are used ONLY as a consistency audit.
EXPECTED_PRIMARY_NSE = {
    "Benchmark": 0.7533,       # across-basin mean NSE
    "Top10": 0.7690,
    "Cluster-wise": 0.7760,
}

EXPECTED_PRIMARY_MEDIAN_NSE = {
    "Benchmark": 0.7920,
    "Top10": 0.8122,
    "Cluster-wise": 0.8154,
}


# ============================================================
# HELPERS
# ============================================================

def normalize_basin(x):
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(8)


def bh_adjust(pvals):
    pvals = np.asarray(pvals, dtype=float)
    n = len(pvals)

    order = np.argsort(pvals)
    ranked = pvals[order]

    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.minimum(adjusted, 1.0)

    out = np.empty(n, dtype=float)
    out[order] = adjusted
    return out


def direction_aware_effect(first, reference, metric):
    """
    Positive always means FIRST model is better.
    This matches the manuscript statistical convention.
    """
    first = np.asarray(first, dtype=float)
    reference = np.asarray(reference, dtype=float)

    if metric in ["NSE", "KGE", "Pearson-r", "R2"]:
        return first - reference

    if metric in ["RMSE", "MSE", "ubRMSE",
                  "MAPE", "Peak-MAPE", "Peak-Timing", "Missed-Peaks"]:
        return reference - first

    if metric in ["FHV", "FMS", "FLV", "Beta-NSE"]:
        return np.abs(reference) - np.abs(first)

    raise ValueError(f"Unknown metric direction: {metric}")


def bootstrap_median_ci(effects, seed=BOOT_SEED, n_boot=N_BOOT):
    x = np.asarray(effects, dtype=float)
    x = x[np.isfinite(x)]

    rng = np.random.default_rng(seed)
    n = len(x)

    boots = np.empty(n_boot, dtype=float)

    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boots[i] = np.median(x[idx])

    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


def paired_stats(df_mean, first_method, ref_method, metric):
    a = (
        df_mean[
            (df_mean["method"] == first_method) &
            (df_mean["metric"] == metric)
        ][["basin", "basin_seed_mean"]]
        .rename(columns={"basin_seed_mean": "first"})
    )

    b = (
        df_mean[
            (df_mean["method"] == ref_method) &
            (df_mean["metric"] == metric)
        ][["basin", "basin_seed_mean"]]
        .rename(columns={"basin_seed_mean": "reference"})
    )

    m = a.merge(b, on="basin", how="inner")

    valid = np.isfinite(m["first"].to_numpy(float)) & \
            np.isfinite(m["reference"].to_numpy(float))

    m = m.loc[valid].copy()

    eff = direction_aware_effect(
        m["first"].to_numpy(float),
        m["reference"].to_numpy(float),
        metric,
    )

    m["effect"] = eff

    nonzero = eff[eff != 0]

    if len(nonzero):
        w = wilcoxon(nonzero, alternative="two-sided")
        wilcoxon_stat = float(w.statistic)
        wilcoxon_p = float(w.pvalue)
    else:
        wilcoxon_stat = np.nan
        wilcoxon_p = 1.0

    n_pos = int(np.sum(eff > 0))
    n_neg = int(np.sum(eff < 0))
    n_tie = int(np.sum(eff == 0))

    if n_pos + n_neg:
        sign_p = float(
            binomtest(
                n_pos,
                n_pos + n_neg,
                p=0.5,
                alternative="two-sided"
            ).pvalue
        )
    else:
        sign_p = 1.0

    ci_lo, ci_hi = bootstrap_median_ci(eff)

    return {
        "first_model": first_method,
        "reference_model": ref_method,
        "metric": metric,
        "n_basins": len(m),
        "wins": n_pos,
        "losses": n_neg,
        "ties": n_tie,
        "win_rate_pct": 100.0 * n_pos / len(m),
        "mean_effect": float(np.mean(eff)),
        "median_effect": float(np.median(eff)),
        "ci95_median_low": ci_lo,
        "ci95_median_high": ci_hi,
        "wilcoxon_stat": wilcoxon_stat,
        "wilcoxon_raw_p": wilcoxon_p,
        "sign_test_p": sign_p,
    }


# ============================================================
# LOAD
# ============================================================

print("=" * 78)
print("CAMELS-US CANONICAL MEAN-ACROSS-SEEDS REAGGREGATION")
print("=" * 78)
print()

if not LONG_CSV.is_file():
    raise FileNotFoundError(LONG_CSV)

if not CLUSTER_CSV.is_file():
    raise FileNotFoundError(CLUSTER_CSV)

df = pd.read_csv(LONG_CSV)
clusters = pd.read_csv(CLUSTER_CSV)

required = {"basin", "seed", "method", "metric", "value"}
missing = required - set(df.columns)

if missing:
    raise RuntimeError(f"Missing columns in overall_metrics_long.csv: {missing}")

clusters_required = {"basin", "cluster"}
missing_c = clusters_required - set(clusters.columns)

if missing_c:
    raise RuntimeError(f"Missing columns in basin_cluster_map_used.csv: {missing_c}")

df["basin"] = df["basin"].map(normalize_basin)
clusters["basin"] = clusters["basin"].map(normalize_basin)

df["value"] = pd.to_numeric(df["value"], errors="coerce")

print("Input rows :", len(df))
print("Methods    :", sorted(df["method"].dropna().unique()))
print("Metrics    :", len(df["metric"].dropna().unique()))
print("Basins     :", df["basin"].nunique())
print("Seeds      :", df["seed"].nunique())
print()


# ============================================================
# HARD VALIDATION
# ============================================================

missing_methods = [m for m in PRIMARY_METHODS if m not in set(df["method"])]

if missing_methods:
    raise RuntimeError(f"Missing required methods: {missing_methods}")

if df["basin"].nunique() != 531:
    raise RuntimeError(
        f"Expected 531 basins, found {df['basin'].nunique()}"
    )

if clusters["basin"].nunique() != 531:
    raise RuntimeError(
        f"Expected 531 basin-cluster assignments, found "
        f"{clusters['basin'].nunique()}"
    )


# Validate 10 finite seed metrics for all core comparisons
audit_rows = []

for method in PRIMARY_METHODS:
    for metric in CORE_METRICS:
        d = df[
            (df["method"] == method) &
            (df["metric"] == metric)
        ].copy()

        g = (
            d.groupby("basin")
            .agg(
                rows=("value", "size"),
                finite_values=("value", lambda x: np.isfinite(x).sum()),
                unique_seeds=("seed", "nunique"),
            )
            .reset_index()
        )

        audit_rows.append({
            "method": method,
            "metric": metric,
            "n_basins": len(g),
            "min_rows_per_basin": int(g["rows"].min()),
            "max_rows_per_basin": int(g["rows"].max()),
            "min_finite_per_basin": int(g["finite_values"].min()),
            "max_finite_per_basin": int(g["finite_values"].max()),
            "min_unique_seeds": int(g["unique_seeds"].min()),
            "max_unique_seeds": int(g["unique_seeds"].max()),
        })

        if len(g) != 531:
            raise RuntimeError(
                f"{method}/{metric}: expected 531 basins, got {len(g)}"
            )

        bad = g[
            (g["rows"] != 10) |
            (g["finite_values"] != 10) |
            (g["unique_seeds"] != 10)
        ]

        if len(bad):
            print(bad.head(20))
            raise RuntimeError(
                f"{method}/{metric}: not every basin has exactly "
                f"10 finite seed-level metrics."
            )

audit_df = pd.DataFrame(audit_rows)
audit_df.to_csv(
    OUT / "00_seed_count_audit.csv",
    index=False
)

print("SEED COUNT AUDIT: PASS")
print("Every basin has exactly 10 finite seed metrics for all four core metrics.")
print()


# ============================================================
# CANONICAL AGGREGATION:
# MEAN OF THE 10 SEED-LEVEL METRICS PER BASIN
# ============================================================

basin_mean = (
    df.groupby(
        ["basin", "method", "metric"],
        as_index=False
    )
    .agg(
        basin_seed_mean=("value", "mean"),
        seed_sd=("value", "std"),
        n_seed_values=("value", "count"),
    )
)

basin_mean.to_csv(
    OUT / "01_basin_mean_across_10_seeds.csv",
    index=False
)

overall = (
    basin_mean.groupby(
        ["method", "metric"],
        as_index=False
    )["basin_seed_mean"]
    .agg(
        count="count",
        mean="mean",
        median="median",
        std="std",
        min="min",
        max="max",
    )
)

overall.to_csv(
    OUT / "02_overall_summary_meanseed.csv",
    index=False
)


# ============================================================
# PRIMARY MANUSCRIPT CONVENTION AUDIT
# ============================================================

print("=" * 78)
print("PRIMARY MANUSCRIPT CONVENTION AUDIT")
print("=" * 78)

audit_text = []

for method in ["Benchmark", "Top10", "Cluster-wise"]:
    row = overall[
        (overall["method"] == method) &
        (overall["metric"] == "NSE")
    ].iloc[0]

    current_mean = float(row["mean"])
    current_median = float(row["median"])

    exp_mean = EXPECTED_PRIMARY_NSE[method]
    exp_median = EXPECTED_PRIMARY_MEDIAN_NSE[method]

    print(
        f"{METHOD_PRETTY[method]:26s} | "
        f"mean NSE={current_mean:.6f} "
        f"(manuscript ~{exp_mean:.4f}) | "
        f"median NSE={current_median:.6f} "
        f"(manuscript ~{exp_median:.4f})"
    )

    audit_text.append(
        (
            method,
            current_mean,
            exp_mean,
            current_median,
            exp_median,
        )
    )

    if abs(current_mean - exp_mean) > 0.001:
        raise RuntimeError(
            f"Canonical mean-seed audit failed for {method} mean NSE."
        )

    if abs(current_median - exp_median) > 0.001:
        raise RuntimeError(
            f"Canonical mean-seed audit failed for {method} median NSE."
        )

print()
print("PRIMARY MANUSCRIPT AGGREGATION AUDIT: PASS")
print()


# ============================================================
# TOP18 vs TOP10 — FOUR CORE METRICS
# ============================================================

rows = []

for metric in CORE_METRICS:
    rows.append(
        paired_stats(
            basin_mean,
            "Top18",
            "Top10",
            metric
        )
    )

core = pd.DataFrame(rows)

core["wilcoxon_fdr_p"] = bh_adjust(
    core["wilcoxon_raw_p"].to_numpy(float)
)

core.to_csv(
    OUT / "03_S17_Top18_vs_Top10_core_meanseed.csv",
    index=False
)


# ============================================================
# CLUSTER SUMMARY USING THE SAME CANONICAL BASIN VALUES
# ============================================================

cluster_basin = basin_mean.merge(
    clusters[["basin", "cluster"]],
    on="basin",
    how="inner"
)

if cluster_basin["basin"].nunique() != 531:
    raise RuntimeError(
        "Cluster merge did not retain all 531 basins."
    )

cluster_summary = (
    cluster_basin[
        cluster_basin["metric"] == "NSE"
    ]
    .groupby(
        ["cluster", "method"],
        as_index=False
    )["basin_seed_mean"]
    .agg(
        n="count",
        median_NSE="median",
        mean_NSE="mean",
    )
)

cluster_summary.to_csv(
    OUT / "04_cluster_NSE_summary_meanseed.csv",
    index=False
)


# ============================================================
# S19 — CLUSTER CONTRASTS
# ============================================================

wide = (
    cluster_summary
    .pivot(
        index="cluster",
        columns="method",
        values="median_NSE"
    )
    .reset_index()
)

needed = {"Top10", "Top18", "Cluster-wise"}

if not needed.issubset(wide.columns):
    raise RuntimeError(
        f"Missing methods for S19: {needed - set(wide.columns)}"
    )

s19 = pd.DataFrame({
    "cluster": wide["cluster"],
    "Top10_median_NSE": wide["Top10"],
    "Top18_median_NSE": wide["Top18"],
    "Hydrologically_informed_median_NSE": wide["Cluster-wise"],
})

s19["delta_Top18_minus_Top10"] = (
    s19["Top18_median_NSE"] -
    s19["Top10_median_NSE"]
)

s19["delta_HI_minus_Top18"] = (
    s19["Hydrologically_informed_median_NSE"] -
    s19["Top18_median_NSE"]
)

s19.to_csv(
    OUT / "05_S19_cluster_contrasts_meanseed.csv",
    index=False
)


# ============================================================
# TOP18 vs HYDROLOGICALLY INFORMED — NSE
# useful for final wording / Discussion
# ============================================================

t18_hi = pd.DataFrame([
    paired_stats(
        basin_mean,
        "Cluster-wise",
        "Top18",
        "NSE"
    )
])

t18_hi.to_csv(
    OUT / "06_HI_vs_Top18_NSE_meanseed.csv",
    index=False
)


# ============================================================
# SEED-LEVEL REGIONAL MEDIANS
# S18 CHECK — THIS DOES NOT REQUIRE BASIN SEED AGGREGATION
# ============================================================

seed_core = df[
    (df["method"].isin(["Top10", "Top18"])) &
    (df["metric"].isin(["NSE", "KGE", "RMSE"]))
].copy()

seed_regional = (
    seed_core.groupby(
        ["seed", "method", "metric"],
        as_index=False
    )["value"]
    .median()
    .rename(columns={"value": "regional_median"})
)

seed_regional.to_csv(
    OUT / "07_seed_level_regional_medians.csv",
    index=False
)

seed_wide = (
    seed_regional
    .pivot_table(
        index=["seed", "metric"],
        columns="method",
        values="regional_median"
    )
    .reset_index()
)

seed_wide["Top18_minus_Top10"] = (
    seed_wide["Top18"] -
    seed_wide["Top10"]
)

seed_wide.to_csv(
    OUT / "08_S18_seed_level_Top18_vs_Top10.csv",
    index=False
)


# ============================================================
# MANUSCRIPT READY REPORT
# ============================================================

lines = []

lines.append("=" * 78)
lines.append("CAMELS-US CANONICAL MEAN-ACROSS-SEEDS RESULTS")
lines.append("=" * 78)
lines.append("")
lines.append(
    "Aggregation: compute each metric separately for each of 10 seeds, "
    "then take the arithmetic mean across seeds for each basin."
)
lines.append("")

lines.append("A) CANONICAL WHOLE-DOMAIN NSE CHECK")
lines.append("-" * 78)

for method in PRIMARY_METHODS:
    row = overall[
        (overall["method"] == method) &
        (overall["metric"] == "NSE")
    ]

    if len(row):
        row = row.iloc[0]
        lines.append(
            f"{METHOD_PRETTY[method]:28s} "
            f"mean={row['mean']:.6f}  "
            f"median={row['median']:.6f}"
        )

lines.append("")
lines.append("B) TOP-18 vs TOP-10 — MANUSCRIPT S17 / TABLE 11 VALUES")
lines.append("-" * 78)
lines.append(
    "Positive paired effect ALWAYS means Top-18 is better."
)
lines.append("")

for _, r in core.iterrows():
    lines.append(
        f"{r['metric']:10s} | "
        f"wins={int(r['wins'])}/{int(r['n_basins'])} "
        f"({r['win_rate_pct']:.2f}%) | "
        f"mean effect={r['mean_effect']:+.6f} | "
        f"median effect={r['median_effect']:+.6f} | "
        f"95% CI=[{r['ci95_median_low']:+.6f}, "
        f"{r['ci95_median_high']:+.6f}] | "
        f"raw P={r['wilcoxon_raw_p']:.6g} | "
        f"FDR P={r['wilcoxon_fdr_p']:.6g} | "
        f"sign P={r['sign_test_p']:.6g}"
    )

lines.append("")
lines.append("C) S19 — CLUSTER MEDIAN NSE CONTRASTS")
lines.append("-" * 78)
lines.append(
    "delta Top18-Top10 > 0 favors Top-18; "
    "delta HI-Top18 > 0 favors hydrologically informed."
)
lines.append("")

for _, r in s19.iterrows():
    lines.append(
        f"C{int(r['cluster'])}: "
        f"Top10={r['Top10_median_NSE']:.6f}, "
        f"Top18={r['Top18_median_NSE']:.6f}, "
        f"HI={r['Hydrologically_informed_median_NSE']:.6f}, "
        f"d(Top18-Top10)={r['delta_Top18_minus_Top10']:+.6f}, "
        f"d(HI-Top18)={r['delta_HI_minus_Top18']:+.6f}"
    )

lines.append("")
lines.append("D) HYDROLOGICALLY INFORMED vs TOP-18 — WHOLE-DOMAIN NSE")
lines.append("-" * 78)

r = t18_hi.iloc[0]

lines.append(
    f"wins={int(r['wins'])}/{int(r['n_basins'])} "
    f"({r['win_rate_pct']:.2f}%), "
    f"mean effect={r['mean_effect']:+.6f}, "
    f"median effect={r['median_effect']:+.6f}, "
    f"95% CI=[{r['ci95_median_low']:+.6f}, "
    f"{r['ci95_median_high']:+.6f}], "
    f"Wilcoxon P={r['wilcoxon_raw_p']:.6g}, "
    f"sign P={r['sign_test_p']:.6g}"
)

lines.append("")
lines.append("E) S18 SEED-LEVEL CHECK")
lines.append("-" * 78)

for metric in ["NSE", "KGE", "RMSE"]:
    d = seed_wide[seed_wide["metric"] == metric]

    if metric in ["NSE", "KGE"]:
        n_better = int((d["Top18_minus_Top10"] > 0).sum())
    else:
        n_better = int((d["Top18_minus_Top10"] < 0).sum())

    lines.append(
        f"{metric}: Top-18 better in {n_better}/10 seed-level "
        f"regional medians."
    )

lines.append("")
lines.append("F) INTERPRETATION GATE")
lines.append("-" * 78)

nse_row = core[core["metric"] == "NSE"].iloc[0]
kge_row = core[core["metric"] == "KGE"].iloc[0]

lines.append(
    f"NSE: median paired effect={nse_row['median_effect']:+.6f}; "
    f"{nse_row['win_rate_pct']:.2f}% basins improved."
)

lines.append(
    f"KGE: median paired effect={kge_row['median_effect']:+.6f}; "
    f"{kge_row['win_rate_pct']:.2f}% basins improved."
)

lines.append("")
lines.append(
    "Use THESE values, not the previous median-across-seed "
    "Top-18 control values, for manuscript finalization."
)
lines.append("")

report = "\n".join(lines)

report_path = OUT / "MANUSCRIPT_READY.txt"
report_path.write_text(report, encoding="utf-8")

print()
print(report)


# ============================================================
# ZIP
# ============================================================

zip_base = ROOT / "CANONICAL_MEANSEED_REAGGREGATION"

zip_path = shutil.make_archive(
    str(zip_base),
    "zip",
    root_dir=OUT
)

print("=" * 78)
print("DONE")
print("=" * 78)
print("Results folder:")
print(OUT)
print()
print("ZIP:")
print(zip_path)
print()
print("Please send MANUSCRIPT_READY.txt or the ZIP back to ChatGPT.")
