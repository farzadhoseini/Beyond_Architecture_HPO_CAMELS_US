# 2026 revision add-on (non-destructive)

This directory is an **additive** scientific revision layer for the existing CAMELS-US HPO repository. The original HPO notebooks, benchmark code, input lists, and legacy reproducibility scripts remain available and MUST NOT be removed.

**Paper:** Beyond Architecture: Optimization and Hydrologic Regime Reveal Performance Headroom in Deep-Learning Rainfall–Runoff Modelling.

The original Zenodo archive (version 2) remains the data foundation. Zenodo version 3 must IMPORT every unchanged v2 file and add the separate `CAMELS_US_Revision_2026_Analysis_Data_v3_additions.zip`. Do not replace original data with the much smaller revision archive.

Included: Top-18 size sensitivity, cluster-local hard routing, Top-10 and HI17 constituent decompositions, V17 35-figure/34-table code and its frozen Liu/HESS basin-metric inputs (with display labels corrected to Liu-LSTM).

**Limits and provenance:** The V17 table builder emits 34 frozen LaTeX tables from a bundled earlier canonical manuscript; not all 34 are independently recalculated from raw model outputs. The V17 full builder deletes/rebuilds its configured result directory, so do NOT execute it against a production directory without staging a safe copy. The earlier canonical manuscript inside V17 is historic builder input and is not the locked final text. `MANUSCRIPT_FREEZE_SHA256.json` gives the SHA-256 of the final submitted PDFs.

Some 17 HI constituents have only 7 or 8 available final realizations for individual constituent analysis. This is documented in the final matched-seed analysis; do not label these controls as uniformly 10-seed. Distinguish the full 10-seed pooled ensemble from seed-matched constituent comparisons.

**Validation release gate:** Verify the 35 final figures and 34 final tables, all selected HPO and final-seed manifests, the original v2 Zenodo file import, the delta archive checksum, and a clean GitHub add-only diff. Do not assert full raw-to-manuscript reproducibility until raw training/prediction archive dependencies are independently verified.
