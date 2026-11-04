# CAMELS-US 2026 release — verified provenance and preservation

**Current research title:** Beyond Architecture: Optimization and Hydrologic Regime Reveal Performance Headroom in Deep-Learning Rainfall–Runoff Modelling  
**Canonical GitHub URL:** https://github.com/farzadhoseini/Beyond_Architecture_HPO_CAMELS_US  
**Zenodo V3 DOI:** https://doi.org/10.5281/zenodo.23945464  
**Maintainer:** Farzad Hosseini

## Release state (4 November 2026)

The CAMELS-US additive 2026 revision was fast-forward integrated into the **existing** repository's `main` branch. The user-side Git log verified commit `4f28270a01e5ef798615f04496c6d5f9039b9cfc` on the live remote `main` before this final documentation follow-up. The repository rename and GitHub About update are administrative changes to the **same repository**, not the creation of a replacement repository. This document does not claim that the manuscript itself has been accepted or published.

A comparison of the prior and post-merge source snapshots (`Cluster-Wise-HPO-CAMELS-US-main(1).zip` and `(2).zip`) found **237 newly added files, zero deletions, and exactly one modification to an original file: the root README**. All other historical files were byte-for-byte unchanged. The 2026 research sources are stored separately at `codes/revision_2026/`.

## Preservation of original benchmark

The original HPO/random-search and ensemble code remains at the same paths:

- `codes/CAMELS_US_clean_HPO_repro_package/`
- `codes/Older_experiment_codes/`
- `codes/camels_final_figure_code_v11/`

Original cluster metadata, geographical inputs, historical figure sources and previous experiment notebooks remain unchanged. Historical file names and internal model identifiers have not been renamed to match the 2026 display labels.

## Additions in 2026

The new `codes/revision_2026/` layer contains (i) Top-18 sensitivity controls and selected run configurations, (ii) Top-10 and hydrologically informed constituent analyses, (iii) cluster-local hard-routing/F4 controls, and (iv) V17 figure and table pipelines with archived manifests and frozen analysis outputs.

The Zenodo V3 record retains **10 files from V2** and adds the following two archives, for **12 files in total**:

1. `CAMELS_US_Revision_2026_Analysis_Data_v3_additions.zip`
2. `CAMELS_US_Top18_Additional8_Raw_10Seed_v3.zip` — 8 additional configurations x 10 seeds, 80 final runs.

## Scientific boundaries and audit status

- The HI17 constituent inventory contains **15 configurations with 10 available final seeds, one with 8, and one with 7**. Missing seeds are not imputed; see the frozen availability inventory and seed-matched protocol.
- The V17 source bundle contains **35 figure manifest entries** (17 main, 18 supplementary) and **34 table manifest entries** (11 main, 23 supplementary). The 34 tables are **frozen LaTeX environments**; the repository does not claim every table is recalculated from raw predictions in a fresh environment.
- Local static validation of the post-merge source ZIP found 52 syntactically valid Python files, 8 structurally valid notebooks, and 80 parseable Top-18 YAML files. This is **not** independent end-to-end retraining or execution verification.
- Some original workstation absolute paths, file names containing `HESS`, and obsolete wording embedded in frozen experiment outputs are preserved for reproducibility and scientific traceability.
- **Important:** `codes/revision_2026/figures_tables_v17/canonical_manuscript/main_current.tex` and `supp_current.tex` are frozen V17 mapping snapshots; they still contain earlier title/terminology, and the main snapshot retains old code/data URLs. They must **not** be used as the final submission manuscript. Update and check the actual final manuscript separately; do not modify frozen snapshots without an explicit audited re-freeze.

For pre-submission data/code link checks and manuscript readiness, see [`SUBMISSION_RELEASE_CHECKLIST.md`](SUBMISSION_RELEASE_CHECKLIST.md).
