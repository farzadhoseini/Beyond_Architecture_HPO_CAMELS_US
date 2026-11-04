# Submission-oriented code and data release checklist — CAMELS-US 2026

This is an audit aid; it does **not** change research results or submission files.

## Confirmed from the user-provided 2026-11-04 repository snapshot

- Existing GitHub `main` was advanced by fast-forward to `4f28270a01e5ef798615f04496c6d5f9039b9cfc` in the IH PowerShell log.
- A before/after ZIP comparison found 237 added files, zero deletions, and one original README change; all legacy scientific files were preserved byte-for-byte.
- Root README and `CITATION.cff` reference the intended repository name and Zenodo V3 DOI.
- Python and notebook structure, 80 Top-18 YAML files, relative Markdown links, and V17 asset manifests passed offline structural validation. This does not constitute an independent model rerun.

## Important distinction: frozen V17 sources versus the submitted manuscript

`codes/revision_2026/figures_tables_v17/canonical_manuscript/main_current.tex` and `supp_current.tex` are archived snapshots used to freeze figure and table mappings. They are **not the approved final Scientific Reports manuscript**.

The *archived snapshot* main LaTeX includes:

- Earlier paper title: `Systematic hyperparameter optimization changes the interpretation of deep-learning architecture benchmarks in hydrology`.
- Obsolete GitHub address: `https://github.com/farzadhoseini/Cluster-Wise-HPO-CAMELS-US`.
- Obsolete data DOI: `10.5281/zenodo.20421012`.
- Historical benchmark display label `HESS-LSTM`, later displayed as `Liu-LSTM` where scientifically appropriate.

The supplementary snapshot also uses the earlier manuscript title and historical display labels. These frozen sources should not be silently modified because the V17 mapping and SHA manifest refer to them. If a new V17 freeze is required, regenerate and validate the SHA/figure/table manifests explicitly.

## Required before the journal submission

1. **Verify final main manuscript and supplement**, not the frozen GitHub snapshots, have the agreed title and scientifically correct current benchmark names.
2. In the final main manuscript's **Code and Data Availability** statement, replace the obsolete GitHub address with `https://github.com/farzadhoseini/Beyond_Architecture_HPO_CAMELS_US` and the old data DOI with `https://doi.org/10.5281/zenodo.23945464`.
3. Ensure the final manuscript describes the 2026 Top-18 **additional eight configurations x 10 seeds**, and the old Top-10 archive is inherited, not replaced.
4. Check Zenodo V3 is **published and publicly resolvable** and presents exactly 12 files: 10 inherited plus the 2 additional 2026 archives.
5. Check the renamed GitHub repository uses the same repository identity/history, `main` has the final documentation commit, and About has the correct description, homepage DOI and topics.
6. Keep the original training/prediction packages and historical records intact; do not rewrite or republish the existing V2 Zenodo data.

Any scientific table or manuscript content change should be reviewed against the approved version, not made automatically by a repository metadata script.
