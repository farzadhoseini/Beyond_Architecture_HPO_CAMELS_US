# Beyond Architecture: Optimization and Hydrologic Regime Reveal Performance Headroom in Deep-Learning Rainfall–Runoff Modelling

**Research code and reproducibility materials for the CAMELS-US study (2026).** This repository contains both the **original cluster-wise HPO benchmark implementation** and the **additive 2026 manuscript revision experiments**. The historical experiment code and outputs have **not** been replaced or removed.

**Maintainer:** Farzad Hosseini  
**Research data, model outputs, and additional experiments:** [Zenodo version 3 — DOI 10.5281/zenodo.23945464](https://doi.org/10.5281/zenodo.23945464)  
**Repository URL:** https://github.com/farzadhoseini/Beyond_Architecture_HPO_CAMELS_US

## Scientific scope

The research examines how the optimization and selection of regional LSTM models, hydrological-regime information, and ensemble design affect out-of-sample rainfall–runoff modelling across **531 CAMELS-US catchments**. The 2026 extensions include analysis of individual ensemble members, hydrologically informed selection, hard-routing controls, and a Top-18 sensitivity experiment relative to the pre-existing Top-10 ensemble.

The baseline workflow is retained to preserve the provenance of the original experiment. The 2026 work is **additive**, not a replacement training campaign.

## Repository organization

```text
codes/
  CAMELS_US_clean_HPO_repro_package/       Original HPO, evaluation, and ensemble code
  Older_experiment_codes/                Historical notebooks and experimental utilities
  camels_final_figure_code_v11/          Historical figure-building pipeline (v11)
  revision_2026/                         Additive experiments and manuscript revision
    constituent_controls/
      Top10/                             Individual Top-10 member comparisons
      HI17/                              Hydrologically informed member decomposition
    hard_routing/                        Cluster-local F4 hard-routing experiments
    top18_control/                       Top-18 vs Top-10, 8 additional configs x 10 seeds
    figures_tables_v17/                 Final paper figure/table production package
    README_2026_REVISION.md              Experiment guide and scientific caveats
531_basin_list.txt                       Catchment identifiers
camels_531_master_attributes_clusters.csv
CAMELS_US_Clusters.xlsx
bad_basins_clusterwise_nse_lt_0p5.csv
misc/shapefiles/                       Original geographic support files
LICENSE
CITATION.cff
RELEASE_2026_PROVENANCE.md
```

The folder `codes/revision_2026/` was added on a separate release branch, without modifying any pre-existing scientific code. Historical directory and file names remain as scientific provenance; labels embedded in the older experiments should not be silently changed.

## What was added in the 2026 revision?

| Component | Purpose | Source in this repository |
|---|---|---|
| Top-18 sensitivity | Check the marginal gain from an 18-member ensemble versus the existing Top-10 across 10 seeds | [`top18_control/`](codes/revision_2026/top18_control/) |
| Top-10 constituents | Compare each of 10 validation-selected configurations against the pooled ensemble | [`constituent_controls/Top10/`](codes/revision_2026/constituent_controls/Top10/) |
| Hydrologically informed constituents | Examine 17 unique selected configurations and the benefit of pooling, with seed-matched comparisons | [`constituent_controls/HI17/`](codes/revision_2026/constituent_controls/HI17/) |
| Hard routing | Evaluate cluster-local routing and associated member-count / performance checks | [`hard_routing/`](codes/revision_2026/hard_routing/) |
| Paper assets | Figure and table construction for 17 main + 18 supplementary figures and 11 main + 23 supplementary tables | [`figures_tables_v17/`](codes/revision_2026/figures_tables_v17/) |

**Important HI17 availability:** The archived constituent-level final runs are **not uniformly 10-seed**: 15 of the 17 configurations have 10 available seeds, one has 8, and one has 7. The relevant analysis uses seed-matched comparisons rather than imputing missing runs. The detailed inventory is at [`02_constituent_seed_availability.csv`](codes/revision_2026/constituent_controls/HI17/frozen_results/02_constituent_seed_availability.csv).

## Data and reproducibility

This GitHub repository is a **code and selected analysis-artifact repository**. The underlying model checkpoints and complete prediction archives are deposited on Zenodo, rather than duplicated into Git.

**Dataset DOI:** https://doi.org/10.5281/zenodo.23945464

The published Zenodo version-3 record includes **12 files**: 10 files retained intact from the preceding dataset version and these two additions:

1. `CAMELS_US_Revision_2026_Analysis_Data_v3_additions.zip` — the additional analysis resources and supporting experiment artifacts.
2. `CAMELS_US_Top18_Additional8_Raw_10Seed_v3.zip` — the archived raw outputs and supporting material for the **80 additional Top-18 runs** (eight added configurations across ten seeds). This is the *additional eight configurations*, not a replacement for the pre-existing Top-10 archive.

For the original benchmark workflow, first consult `codes/CAMELS_US_clean_HPO_repro_package/CAMELS_US_clean_HPO_data_checklist.md` and obtain the official CAMELS-US meteorological forcing, catchment attributes, and streamflow data under their applicable conditions.

For the 2026 controls, consult [`codes/revision_2026/README_2026_REVISION.md`](codes/revision_2026/README_2026_REVISION.md) and the README files in each subdirectory. Several scripts were originally written for the IH research workstation and contain machine-specific paths. **Configure those paths and dependencies for your own environment before running them.**

**Scientific provenance boundary:** The final V17 table builder extracts and freezes 34 LaTeX table environments from a canonical manuscript snapshot; it does **not** independently recompute every published table from raw training/prediction data. Figure and table scripts are provided with their inputs and audit manifests, but a fully automated, machine-independent end-to-end reproduction from training is not claimed. The V17 builder may clear its configured output directory; run it only in a safe isolated working copy.

## License, attribution, and citation

Code in this repository is distributed under the repository's existing [Apache-2.0 license](LICENSE). External input datasets and third-party materials retain their respective licenses and attribution requirements.

If you use the underlying data or frozen benchmark results, cite the [Zenodo version-3 dataset](https://doi.org/10.5281/zenodo.23945464). When the associated manuscript is published, cite that paper as well. The previous Zenodo versions remain in the version history for provenance; older PDFs retained in the deposit are **historical records and not the current 2026 manuscript**.

For scope, provenance and documented experimental limitations, see [`RELEASE_2026_PROVENANCE.md`](RELEASE_2026_PROVENANCE.md).
