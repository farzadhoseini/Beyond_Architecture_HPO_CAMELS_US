# CAMELS-US 2026 manuscript revision — additive research layer

**Study:** Beyond Architecture: Optimization and Hydrologic Regime Reveal Performance Headroom in Deep-Learning Rainfall–Runoff Modelling.

**Published research data:** https://doi.org/10.5281/zenodo.23945464

This directory **adds** work performed for the 2026 manuscript to the existing CAMELS-US benchmark. It does not change, delete, or supersede the original HPO notebooks, ensemble scripts, historical model outputs, input metadata or the previous figure pipeline.

## Components

- `top18_control/`: eight additional training configurations across ten final seeds, an 18-member sensitivity ensemble, Top-10 comparisons, preserved selection configs, and frozen aggregate results. The 4.18-GB raw archive resides in Zenodo V3, not GitHub.
- `constituent_controls/Top10/`: evaluation of all ten individual validation-selected Top-10 configurations. Constituent IDs are *not* inferred HPO rankings.
- `constituent_controls/HI17/`: 18 cluster-conditioned selection slots corresponding to 17 distinct scientific configurations. Pooled-ensemble vs member comparisons use seed-matched available realizations.
- `hard_routing/`: cluster-local routing and F4 controls, including code, local-run wrappers, preflight mapping and results.
- `figures_tables_v17/`: manuscript production scripts and frozen source inputs for 35 figures (17 main and 18 supplementary) and 34 tables (11 main and 23 supplementary).

## Scientific and technical boundaries

1. **HI17 seed availability:** The definitive frozen files `constituent_controls/HI17/frozen_results/02_constituent_seed_availability.csv` and `RUN_SUMMARY.json` show **15 configurations with 10 available final seeds, one with 8, and one with 7**. This corrects an outdated sentence in the first release of the HI17 README. No missing model realization is imputed; paired comparisons are seed matched.
2. **Top-18 scope:** The added archive documents **eight additional configurations × ten seeds**. The earlier Top-10 data remain in the existing Zenodo data files. The combined Top-18 comparison is not evidence of a separate 180-run retraining campaign.
3. **Publication labels versus internal keys:** `Hydrologically informed` and `Liu-LSTM` are used in the present manuscript where appropriate. Historical keys such as `Cluster-wise` or `HESS` are preserved internally when changing them would break source-to-result lineage.
4. **Frozen table provenance:** The V17 `build_tables_v17.py` builds 34 LaTeX table environments from the bundled canonical frozen manuscript. This is not the same as reconstructing every numerical value from the raw time series. See `figures_tables_v17/TABLE_AUDIT_V17.md` for the explicit FDR-rounding correction.
5. **Execution safety:** Several scripts contain absolute paths configured for the IH Windows workstation; adapt these before independent execution. The V17 full builder may delete/recreate its configured output directory. Never point it at irreplaceable results.
6. **Reproducibility claim:** Frozen scripts, selected configurations and analysis outputs are archived and traceable. Independent bitwise reproduction of the full experiment from scratch has not been established by this repository alone.

## Source preservation

The original code stays at the original top-level `codes/` paths. This directory is an explicit add-on so that comparisons against the initial benchmark remain possible. The published Zenodo V3 contains eight baseline data archives and two analysis archives: `CAMELS_US_Revision_2026_Analysis_Data_v3_additions.zip` and `CAMELS_US_Top18_Additional8_Raw_10Seed_v3.zip` (10 total).

See the root README for dataset access, citation and usage instructions.
