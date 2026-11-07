# CAMELS-US final paper asset builder — V17

V17 is locked to the two current the previous journal format LaTeX manuscripts bundled under `canonical_manuscript/`.
It does not renumber figures and does not invent publication filenames.

## Final deliverable
Running `run_CAMELS_v17_FINAL.ps1` creates only:

- `<ProjectRoot>/results/CAMELS_V17_FINAL/figures/` — exactly 35 PDF files, exactly matching every `\\includegraphics{...}` in the current main (17) and supplementary (18) manuscripts.
- `<ProjectRoot>/results/CAMELS_V17_FINAL/tables/` — exactly 34 standalone LaTeX table environments, one per current table label (11 main + 23 supplementary).

All intermediate core/revision outputs are staging artifacts and are deleted after a successful run unless `-KeepBuild` is supplied.

## Run
```powershell
powershell -ExecutionPolicy Bypass -File ".\run_CAMELS_v17_FINAL.ps1" `
  -ProjectRoot "F:\Experiments\CAMELS_US\Clean_4_upload"
```

## Table policy
The current 34 table environments are treated as the canonical frozen manuscript tables for V17. V17 does **not** silently recompute or alter their numerical content. One explicit reproducibility correction is applied and documented: in `tab:hydro_selection_regimes`, Cluster 1 FDR-adjusted Wilcoxon P is emitted as `0.960` rather than the current manuscript's `0.957`, because the bundled canonical summary gives `0.960420` at full precision. This is deliberate and non-substantive; otherwise: the current paper contains tables sourced from several distinct experimental archives (core HPO, multi-seed, HESS/Liu, Top-18, routing, constituent-decomposition, and protocol/configuration metadata). Any scientific numerical table change must be explicit and justified, then the canonical table source can be revised and re-frozen.

The HESS/Liu derived CSVs needed by the seven revision figures are still recomputed internally in staging as part of the revision builder, but they are not left in the final Overleaf `tables/` folder because the manuscript consumes the 34 LaTeX table environments, not those helper CSV files.
