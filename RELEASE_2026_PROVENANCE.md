# 2026 CAMELS-US GitHub release: scientific provenance and preservation

**Target repository:** `farzadhoseini/Beyond_Architecture_HPO_CAMELS_US`  
**Data DOI (Zenodo V3):** https://doi.org/10.5281/zenodo.23945464  
**Staged initial branch:** `release/camels-2026-additive-v3`  
**Verified initial addition commit:** `5399fe872aeb7f78cee829ff93b6aa5255da6179`

## Preservation decision

The original experiments remain in `codes/CAMELS_US_clean_HPO_repro_package/`, `codes/Older_experiment_codes/` and `codes/camels_final_figure_code_v11/`, with original basin and cluster metadata untouched. All 2026 source, configurations, freeze summaries and supporting files belong under **`codes/revision_2026/`**. The original Git history remains intact; no destructive rewrite, force-push, or replacement repo is needed.

## Historical versus 2026 additions

The new layer contains Top-18 controls, Top-10 and hydrologically informed constituent decomposition, F4 cluster-local routing, and V17 figure/table production assets. The initial branch added 235 files and no deletions, with a single modification to the legacy root README. The final documentation patch corrects the README and CI/citation metadata, including one outdated HI17 seed-count statement.

## Data inventory (Zenodo version 3)

- 10 unchanged inherited V2 archive files.
- `CAMELS_US_Revision_2026_Analysis_Data_v3_additions.zip` (2026 revision artifacts).
- `CAMELS_US_Top18_Additional8_Raw_10Seed_v3.zip` (eight additional selected configurations × ten seeds; 80 raw-run outputs).

The complete 12-file draft was independently verified by the user-side upload script before publication. The stable version DOI is `10.5281/zenodo.23945464`.

## Quality checks and limitations

- The 2026 source collection originally staged **233 manifest-checked files** plus two documentation/provenance files, totaling **235 added files**. The present patch keeps that source collection bit-for-bit unchanged except for the specifically corrected **new** HI17 README, and adds publication-facing documentation. It does not change model predictions, checkpoints, or evaluation source code.
- 25 added `.py` files passed a local Python AST syntax parse; two `.ipynb` files parsed as valid Notebook JSON. This is a **static syntax check**, not an end-to-end execution test.
- Several experimental scripts and YAML files embed original IH Windows paths. These are preserved for traceability; portable execution requires path and dependency setup.
- V17 prepares 35 figure files and 34 LaTeX table environments. The tables are frozen from a canonical manuscript snapshot, **not** all recomputed from raw data.
- The archival HI17 constituent availability table shows 15 × 10 seeds, 1 × 8 seeds and 1 × 7 seeds. The earlier HI17 README said 16 × 10 and 1 × 5, which was inconsistent with the frozen result inventory. Its **documentation only** is corrected in this patch.
- Internal historical experiment identifiers are preserved, even where the current paper uses different display labels.

## Release gates

Before merging into `main`, run `CAMELS_GITHUB_2026_SAFE_RELEASE.ps1 -Mode Audit`; ensure the source manifest matches, the diff has no deletions and no old scientific files are changed, and no independent changes to `main` are silently lost. Update the repository name and GitHub About description separately using the owner's authenticated shell, and then review the merge. The script does **not** automatically merge into `main`.
