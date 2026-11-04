from __future__ import annotations

"""CAMELS-US Scientific Reports revision: Results figure builder (v04, V16-integrated).

Purpose
-------
Regenerate only the *new* revision figures introduced after the rejected
preprint. Existing manuscript figures (fig04--fig30) are intentionally not
redrawn here; the revised LaTeX continues to reference their historical
filenames. This script reads the frozen post-Liu benchmark products and the
pre-Liu Cluster-wise-vs-Top-10 tables, then writes compact publication-ready
PDF + 300-dpi PNG files to the canonical revision code/output tree.

v03 display-label correction
----------------------------
The internal model key ``Cluster-wise`` is intentionally preserved for all
lookups and calculations. Only human-facing display labels are harmonized to
``Hydrologically informed``. In particular:
  * paired-reference figure labels use ``Hydrologically informed vs ...``;
  * HESS metric-tradeoff legend uses ``Hydrologically informed``.

V16 integration
---------------
The revision benchmark inputs required by these plots are shipped inside the
V16 figure-code package under ``revision_data``. No external benchmark source
tree is required. The canonical CAMELS project root is supplied by the master
V16 runner.
"""

from pathlib import Path
import argparse
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

JAVI = {
    "cluster": "#56ae6c",
    "top10": "#8960b3",
    "kratzert": "#b0923b",
    "accent": "#ba495b",
    "hess_lstm": "#111111",
    "crossformer": "#2f5597",
    "grey": "#7f7f7f",
}


def apply_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
        "font.family": "sans-serif",
        "font.sans-serif": ["Calibri", "Arial", "Liberation Sans", "DejaVu Sans"],
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9.5,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "axes.linewidth": 0.9,
        "lines.linewidth": 1.7,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def resolve_revision_inputs(revision_data_root: Path) -> tuple[Path, Path]:
    revision_data_root = revision_data_root.expanduser().resolve()
    frozen = revision_data_root / "frozen_v1"
    preliu = revision_data_root / "preliu_tables"
    required = [
        frozen / "RESULTS_SNAPSHOT.json",
        frozen / "frozen_data" / "threshold_coverage.csv",
        frozen / "frozen_data" / "hess_dashboard_basin_metrics.csv",
        frozen / "frozen_data" / "paired_basin_level.csv",
        frozen / "frozen_data" / "own_basin_seed_summary.csv",
        frozen / "manuscript_ready" / "tables" / "Table_M0_paired_NSE_vs_reference_benchmarks.csv",
        frozen / "manuscript_ready" / "tables" / "Table_M1_paired_effects_vs_HESS_LSTM.csv",
        frozen / "manuscript_ready" / "tables" / "Table_S1_absolute_metric_context.csv",
        preliu / "clusterwise_vs_top10_by_cluster.csv",
        preliu / "clusterwise_vs_top10_by_aridity_quartile.csv",
    ]
    missing = [p for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "V16 revision data bundle is incomplete. Missing:\n" +
            "\n".join(f"  - {p}" for p in missing)
        )
    return frozen, preliu


def save_dual(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    fig.savefig(out_dir / f"{stem}.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def figure_paired_nse(frozen: Path, out_dir: Path) -> None:
    df = pd.read_csv(frozen / "manuscript_ready" / "tables" / "Table_M0_paired_NSE_vs_reference_benchmarks.csv")
    df = df[df["10-seed aggregation"].eq("Mean")].copy()

    # Keep the canonical/internal data key separate from the manuscript label.
    order = [
        ("Kratzert ensemble", "Cluster-wise", "Hydrologically informed"),
        ("Kratzert ensemble", "Top-10", "Top-10"),
        ("HESS-LSTM (single published seed)", "Cluster-wise", "Hydrologically informed"),
        ("HESS-LSTM (single published seed)", "Top-10", "Top-10"),
    ]
    rows = []
    for ref, model_key, model_label in order:
        r = df[(df.Reference == ref) & (df.Model == model_key)].iloc[0]
        lo, hi = [float(x) for x in str(r["95% CI median ΔNSE"]).strip("[]").split(",")]
        rows.append((
            ref,
            model_key,
            model_label,
            float(r["Median paired ΔNSE"]),
            lo,
            hi,
            float(r["Win rate (%)"]),
        ))

    fig, ax = plt.subplots(figsize=(7.2, 3.25))
    y = np.arange(len(rows))[::-1]
    labels = []
    for yi, (ref, model_key, model_label, med, lo, hi, win) in zip(y, rows):
        color = JAVI["cluster"] if model_key == "Cluster-wise" else JAVI["top10"]
        ax.errorbar(med, yi, xerr=[[med-lo], [hi-med]], fmt="o", ms=5.5,
                    capsize=3, color=color, ecolor=color, markeredgecolor="black",
                    markeredgewidth=0.35)
        ax.text(hi + 0.0007, yi, f"{win:.1f}% wins", va="center", fontsize=7.6)
        ref_short = "Kratzert" if ref.startswith("Kratzert") else "Liu-LSTM"
        labels.append(f"{model_label} vs {ref_short}")
    ax.axvline(0, color="0.35", lw=0.9, ls="--")
    ax.set_yticks(y, labels)
    ax.set_xlabel("Median paired $\\Delta$NSE (95% bootstrap CI)")
    ax.set_title("Basin-paired NSE gains against the two external references")
    ax.grid(axis="x", color="0.88", lw=0.6)
    ax.grid(axis="y", visible=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save_dual(fig, out_dir, "fig_results_paired_nse_references")


def figure_threshold_coverage(frozen: Path, out_dir: Path) -> None:
    df = pd.read_csv(frozen / "frozen_data" / "threshold_coverage.csv")
    models = ["Kratzert", "HESS LSTM", "Top-10", "Cluster-wise"]
    labels = ["Kratzert", "Liu-LSTM", "Top-10", "Hydrologically informed"]
    colors = [JAVI["kratzert"], JAVI["hess_lstm"], JAVI["top10"], JAVI["cluster"]]
    thresholds = [0.5, 0.7, 0.8, 0.9]
    vals = {}
    for m in models:
        agg = "single_published_run" if m.startswith("HESS") else "mean_10_seeds"
        x = df[(df.model == m) & (df.metric == "NSE") & (df.seed_aggregation == agg)]
        vals[m] = [100 * float(x.loc[np.isclose(x.threshold, t), "share_meeting"].iloc[0]) for t in thresholds]

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    x0 = np.arange(len(thresholds))
    width = 0.18
    offsets = np.linspace(-1.5*width, 1.5*width, len(models))
    for off, m, lab, color in zip(offsets, models, labels, colors):
        bars = ax.bar(x0 + off, vals[m], width=width, label=lab, color=color,
                      edgecolor="0.2", linewidth=0.45)
        for b, v in zip(bars, vals[m]):
            ax.text(b.get_x()+b.get_width()/2, v+1.0, f"{v:.1f}", ha="center", va="bottom", fontsize=6.7, rotation=90)
    ax.set_xticks(x0, [f"NSE ≥ {t:.1f}" for t in thresholds])
    ax.set_ylabel("Basins meeting threshold (%)")
    ax.set_ylim(0, 104)
    ax.set_title("Practical NSE threshold coverage across 531 CAMELS-US basins")
    ax.legend(ncol=2, frameon=False, loc="upper right")
    ax.grid(axis="y", color="0.88", lw=0.6)
    ax.grid(axis="x", visible=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save_dual(fig, out_dir, "fig_results_threshold_coverage")


def figure_hydro_selection_regimes(preliu_dir: Path, out_dir: Path) -> None:
    c = pd.read_csv(preliu_dir / "clusterwise_vs_top10_by_cluster.csv")
    a = pd.read_csv(preliu_dir / "clusterwise_vs_top10_by_aridity_quartile.csv")
    c = c[(c.metric == "NSE") & (c.seed_aggregation == "mean_10_seeds")].copy()
    a = a[(a.metric == "NSE") & (a.seed_aggregation == "mean_10_seeds")].copy()

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.35), sharey=True)
    panels = [
        (axes[0], c, "cluster", [1,2,3,4,5,6], ["C1","C2","C3","C4","C5","C6"], "Hydrologic cluster"),
        (axes[1], a, "aridity_quartile", ["Q1 wettest","Q2","Q3","Q4 driest"], ["Q1\nwettest","Q2","Q3","Q4\ndriest"], "Aridity quartile"),
    ]
    for ax, df, key, order, ticklabels, xlabel in panels:
        xs=np.arange(len(order)); med=[]; lo=[]; hi=[]; win=[]
        for v in order:
            r=df[df[key].eq(v)].iloc[0]
            med.append(float(r.median_fair_delta)); lo.append(float(r.bootstrap95_median_lo)); hi.append(float(r.bootstrap95_median_hi)); win.append(100*float(r.win_rate))
        med=np.array(med); lo=np.array(lo); hi=np.array(hi)
        ax.errorbar(xs, med, yerr=[med-lo, hi-med], fmt="o", color=JAVI["cluster"],
                    ecolor=JAVI["cluster"], ms=5.2, capsize=3, markeredgecolor="black", markeredgewidth=0.35)
        ax.axhline(0, color="0.35", lw=0.9, ls="--")
        ax.set_xticks(xs, ticklabels)
        ax.set_xlabel(xlabel)
        ax.grid(axis="y", color="0.88", lw=0.6)
        ax.grid(axis="x", visible=False)
        for x, m, h, w in zip(xs, med, hi, win):
            dy = 0.002 if h >= 0 else -0.003
            ax.text(x, h+dy, f"{w:.0f}%", ha="center", va="bottom" if h>=0 else "top", fontsize=6.8)
        ax.spines[["top","right"]].set_visible(False)
    axes[0].set_ylabel("Median paired $\\Delta$NSE\n(hydrologically informed − Top-10)")
    axes[0].set_title("a  Cluster dependence", loc="left", fontweight="bold")
    axes[1].set_title("b  Aridity dependence", loc="left", fontweight="bold")
    fig.suptitle("Hydrologically informed post-HPO selection has regime-dependent value", y=1.01, fontsize=10.5, fontweight="bold")
    fig.tight_layout()
    save_dual(fig, out_dir, "fig_results_hydro_selection_regimes")


def figure_hess_tradeoff(frozen: Path, out_dir: Path) -> None:
    df = pd.read_csv(frozen / "manuscript_ready" / "tables" / "Table_M1_paired_effects_vs_HESS_LSTM.csv")
    df = df[df["10-seed aggregation"].eq("Mean") & df.Metric.isin(["NSE","R2","KGE"])].copy()
    metrics=["NSE","R2","KGE"]
    fig, ax = plt.subplots(figsize=(6.7, 3.15))

    # Internal key and human-facing legend text are deliberately separated.
    model_specs = [
        ("Top-10", "Top-10"),
        ("Cluster-wise", "Hydrologically informed"),
    ]
    for i, (model_key, legend_label) in enumerate(model_specs):
        sub=df[df.Model.eq(model_key)].set_index("Metric")
        y=np.arange(len(metrics)) + (i-0.5)*0.16
        med=[]; lo=[]; hi=[]
        for m in metrics:
            r=sub.loc[m]
            l,h=[float(x) for x in str(r["95% CI median gain"]).strip("[]").split(",")]
            med.append(float(r["Median paired gain"])); lo.append(l); hi.append(h)
        med=np.array(med);lo=np.array(lo);hi=np.array(hi)
        color=JAVI["top10"] if model_key=="Top-10" else JAVI["cluster"]
        ax.errorbar(med,y,xerr=[med-lo,hi-med],fmt="o",capsize=3,color=color,
                    label=legend_label,markeredgecolor="black",markeredgewidth=.35)
    ax.axvline(0,color="0.35",ls="--",lw=.9)
    ax.set_yticks(np.arange(len(metrics)),metrics)
    ax.set_xlabel("Median paired effect vs Liu-LSTM (95% bootstrap CI)")
    ax.set_title("Metric-dependent external benchmark effect")
    ax.legend(frameon=False,ncol=2)
    ax.grid(axis="x",color="0.88",lw=.6);ax.grid(axis="y",visible=False)
    ax.spines[["top","right"]].set_visible(False)
    fig.tight_layout()
    save_dual(fig,out_dir,"fig_results_hess_metric_tradeoff")


def figure_hess_architecture_context(frozen: Path, out_dir: Path) -> None:
    df=pd.read_csv(frozen / "frozen_data" / "hess_dashboard_basin_metrics.csv")
    h=df[df.metric.eq("NSE")].groupby("model").value.median().sort_values()
    # Own absolute context: mean across final 10 seeds, then across-basin median.
    absdf=pd.read_csv(frozen / "manuscript_ready" / "tables" / "Table_S1_absolute_metric_context.csv")
    own=absdf[(absdf.Metric.eq("NSE")) & (absdf.Aggregation.eq("mean_10_seeds"))].set_index("Model")["Across-basin median"]

    fig,ax=plt.subplots(figsize=(7.2,4.25))
    colors=[JAVI["hess_lstm"] if m=="LSTM" else (JAVI["crossformer"] if m=="Crossformer" else "0.72") for m in h.index]
    ax.barh(np.arange(len(h)),h.values,color=colors,edgecolor="0.25",linewidth=.4)
    ax.set_yticks(np.arange(len(h)),["Liu-LSTM" if m == "LSTM" else m for m in h.index])
    if "Top-10" in own: ax.axvline(float(own["Top-10"]),color=JAVI["top10"],lw=2,ls="--",label="Top-10 (mean of 10 seeds)")
    if "Cluster-wise" in own: ax.axvline(float(own["Cluster-wise"]),color=JAVI["cluster"],lw=2,ls="-",label="Hydrologically informed (mean of 10 seeds)")
    ax.set_xlabel("Across-basin median NSE")
    ax.set_title("Public HESS architecture context and optimized LSTM references")
    ax.legend(frameon=False,loc="lower right")
    ax.grid(axis="x",color="0.88",lw=.6);ax.grid(axis="y",visible=False)
    ax.spines[["top","right"]].set_visible(False)
    fig.tight_layout()
    save_dual(fig,out_dir,"fig_results_hess_architecture_context")


def figure_spatial_delta_hess(frozen: Path, out_dir: Path) -> None:
    df=pd.read_csv(frozen / "frozen_data" / "paired_basin_level.csv")
    x=df[(df.hess_model.eq("LSTM")) & (df.ours_model.eq("Cluster-wise")) &
         (df.metric.eq("NSE")) & (df.seed_aggregation.eq("mean_10_seeds"))].copy()
    cmap=LinearSegmentedColormap.from_list("javi_div",[JAVI["top10"],"#f7f7f7",JAVI["cluster"]])
    lim=max(abs(np.nanpercentile(x.delta_fair,[2,98])))
    norm=TwoSlopeNorm(vmin=-lim,vcenter=0,vmax=lim)
    fig,ax=plt.subplots(figsize=(7.2,3.9))
    sc=ax.scatter(x.gauge_lon,x.gauge_lat,c=x.delta_fair,cmap=cmap,norm=norm,s=14,
                  edgecolor="0.20",linewidth=.25)
    cb=fig.colorbar(sc,ax=ax,pad=.015,shrink=.88)
    cb.set_label("$\\Delta$NSE vs Liu-LSTM")
    ax.set_xlabel("Longitude");ax.set_ylabel("Latitude")
    ax.set_title("Spatial distribution of basin-paired NSE differences")
    ax.grid(color="0.90",lw=.5)
    ax.spines[["top","right"]].set_visible(False)
    fig.tight_layout()
    save_dual(fig,out_dir,"fig_results_spatial_delta_hess")


def write_threshold_transition_table(frozen: Path, table_dir: Path) -> None:
    own=pd.read_csv(frozen / "frozen_data" / "own_basin_seed_summary.csv")
    hess=pd.read_csv(frozen / "frozen_data" / "hess_dashboard_basin_metrics.csv")
    ours=(own[(own.metric.eq("NSE")) & own.model.isin(["Kratzert","Top-10","Cluster-wise"])]
          .pivot(index="basin",columns="model",values="seed_mean"))
    h=(hess[(hess.metric.eq("NSE")) & hess.model.eq("LSTM")]
       .set_index("basin").value.rename("HESS-LSTM"))
    d=ours.join(h,how="inner")
    rows=[]
    for ref in ["Kratzert","HESS-LSTM"]:
        for model in ["Top-10","Cluster-wise"]:
            for t in [0.5,0.7,0.8,0.9]:
                ref_weak=d[ref] < t; mod_weak=d[model] < t
                rows.append({
                    "reference":ref,"model":model,"threshold":t,"n":len(d),
                    "reference_below":int(ref_weak.sum()),"model_below":int(mod_weak.sum()),
                    "rescued":int((ref_weak & ~mod_weak).sum()),
                    "degraded":int((~ref_weak & mod_weak).sum()),
                    "retained_below":int((ref_weak & mod_weak).sum()),
                    "retained_above":int((~ref_weak & ~mod_weak).sum()),
                })
    table_dir.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(table_dir / "threshold_transitions_all_v01.csv",index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the seven V17 CAMELS-US revision figures.")
    parser.add_argument("--project-root", type=Path, required=True, help="CAMELS-US project root")
    parser.add_argument("--revision-data-root", type=Path,
                        default=Path(__file__).resolve().parent / "revision_data",
                        help="V16 bundled revision-data directory")
    parser.add_argument("--figure-outdir", default="results/Revision_figures",
                        help="Revision figure output folder relative to project root")
    parser.add_argument("--table-outdir", default="results/Revision_tables",
                        help="Revision table output folder relative to project root")
    args = parser.parse_args()

    apply_style()
    project_root = args.project_root.expanduser().resolve()
    frozen, preliu_dir = resolve_revision_inputs(args.revision_data_root)
    fig_dir = project_root / args.figure_outdir
    table_dir = project_root / args.table_outdir

    figure_paired_nse(frozen, fig_dir)
    figure_threshold_coverage(frozen, fig_dir)
    figure_hydro_selection_regimes(preliu_dir, fig_dir)
    figure_hess_tradeoff(frozen, fig_dir)
    figure_hess_architecture_context(frozen, fig_dir)
    figure_hess_cluster_metric_context(frozen, fig_dir, table_dir)
    figure_spatial_delta_hess(frozen, fig_dir)
    write_threshold_transition_table(frozen, table_dir)

    print(f"V17 bundled frozen source: {frozen}")
    print(f"V17 bundled pre-Liu tables: {preliu_dir}")
    print(f"Revision figures written to: {fig_dir}")
    print(f"Derived revision tables written to: {table_dir}")


def figure_hess_cluster_metric_context(frozen: Path, out_dir: Path, table_dir: Path) -> None:
    hess = pd.read_csv(frozen / "frozen_data" / "hess_dashboard_basin_metrics.csv")
    own = pd.read_csv(frozen / "frozen_data" / "own_basin_seed_summary.csv")
    pairs = pd.read_csv(frozen / "frozen_data" / "paired_basin_level.csv")

    clusters = pairs[["basin", "cluster"]].drop_duplicates()
    hess = hess.merge(clusters, on="basin", how="left")
    own = own.merge(clusters, on="basin", how="left")

    row_order = [
        "Cluster-wise", "Top-10", "Kratzert", "LSTM",
        "Crossformer", "Non-stationary Transformer", "Transformer",
        "Pyraformer", "Informer", "ETSformer", "Reformer",
        "DLinear", "iTransformer", "CARDformer",
    ]

    display = {
        "Cluster-wise": "Hydrologically informed",
        "LSTM": "Liu-LSTM",
    }

    tables = {}
    table_dir.mkdir(parents=True, exist_ok=True)

    for metric in ["NSE", "KGE"]:
        own_t = (
            own[(own.metric == metric) &
                own.model.isin(["Cluster-wise", "Top-10", "Kratzert"])]
            .pivot_table(index="model", columns="cluster",
                         values="seed_mean", aggfunc="median")
        )

        hess_t = (
            hess[hess.metric == metric]
            .pivot_table(index="model", columns="cluster",
                         values="value", aggfunc="median")
        )

        tab = pd.concat([own_t, hess_t]).reindex(row_order)
        tab.index = [display.get(x, x) for x in tab.index]
        tab.columns = [f"C{int(c)}" for c in tab.columns]

        tab.to_csv(
            table_dir / f"hess_cluster_median_{metric}_v01.csv"
        )
        tables[metric] = tab

    cmap = LinearSegmentedColormap.from_list(
        "javi_skill",
        [JAVI["top10"], "#f7f7f7", JAVI["cluster"]]
    )

    all_values = np.concatenate(
        [tables["NSE"].values.ravel(), tables["KGE"].values.ravel()]
    )
    vmin = min(-1.0, float(np.nanmin(all_values)))
    vmax = max(0.9, float(np.nanmax(all_values)))
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax)

    fig, axes = plt.subplots(
        1, 2, figsize=(10.2, 5.9), sharey=True
    )

    for ax, metric in zip(axes, ["NSE", "KGE"]):
        tab = tables[metric]
        vals = tab.values.astype(float)

        im = ax.imshow(
            vals, aspect="auto", cmap=cmap, norm=norm
        )

        ax.set_xticks(
            np.arange(6),
            [f"C{i}" for i in range(1, 7)]
        )
        ax.set_title(metric, fontweight="bold")
        ax.set_xlabel("Hydrologic cluster")

        for r in range(vals.shape[0]):
            for c in range(vals.shape[1]):
                value = vals[r, c]
                ax.text(
                    c, r, f"{value:.2f}",
                    ha="center", va="center",
                    fontsize=6.6,
                    color="white"
                    if (value > 0.74 or value < -0.35)
                    else "black",
                )

        # Separate our/Kratzert references, HESS-LSTM,
        # and the remaining HESS architectures.
        ax.axhline(2.5, color="black", lw=1.1)
        ax.axhline(3.5, color="0.4", lw=0.8, ls="--")

    labels = list(tables["NSE"].index)
    axes[0].set_yticks(
        np.arange(len(labels)), labels, fontsize=7.4
    )
    axes[1].tick_params(
        axis="y", left=False, labelleft=False
    )

    fig.suptitle(
        "Cluster-conditioned architecture performance is metric-dependent",
        fontweight="bold", y=0.985
    )

    fig.subplots_adjust(
        left=0.29, right=0.985,
        wspace=0.08, top=0.91, bottom=0.18
    )

    cax = fig.add_axes([0.36, 0.075, 0.48, 0.025])
    cb = fig.colorbar(
        im, cax=cax, orientation="horizontal"
    )
    cb.set_label(
        "Across-basin cluster median", fontsize=8
    )
    cb.ax.tick_params(labelsize=7)

    save_dual(
        fig, out_dir,
        "fig_supp_hess_cluster_metric_heatmap"
    )


if __name__ == "__main__":
    main()
