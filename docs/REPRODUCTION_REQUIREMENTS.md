# Independent CAMELS-US experiment reproduction

This page specifies the assets and tests needed to reproduce the reported CAMELS-US
rainfall--runoff study from its original hyperparameter search, not only to redraw plots.

## Inputs and provenance

| Artifact | Status in GitHub | Action for reproducer |
|---|---|---|
| HPO notebook and search-space source | Present | Preserve notebook functions and record its hash |
| HPO base `configRegional_Fred.yml` | Not present | Recover the exact original YAML and verify source provenance |
| Original 2,000 HPO candidate YAMLs or validated candidate list | Not present | Recover; fingerprint with `tools/hpo_candidate_manifest.py` |
| Training/validation/test splits and six cluster ID lists | Reference basin IDs and attributes present; prepared workspace lists external | Recover fixed splits; run `tools/verify_hpo_inputs.py --strict` |
| Original CAMELS-US observations and forcing | External | Download under applicable data licenses, keep exact versions and as-of ranges |
| Historical training software version lock | Not present | Recover exact neuralhydrology/PyTorch environment from original logs if available |
| Final selected models, metrics and 2026 controls | Released on Zenodo | Verify archive file hashes and extracted paths |
| Additional Top-18 selected configurations | 80 YAMLs in GitHub | Validate exact eight configurations and ten seeds |
| HESS manuscript table source | 34 HESS table snippets in GitHub | Run `validate_v17.py` and `build_tables_v17.py` |
| HESS figure-name mapping | Present | Run HESS asset export after V17 builds complete |

## Execution stages

| Stage | Input | Expected output | Proof required |
|---|---|---|---|
| 0. Data preparation | CAMELS-US, fixed basin/cluster lists, base YAML | NeuralHydrology data workspace | 531 unique basin IDs, six disjoint clusters; temporal splits inspected |
| 1. HPO candidate generation | Original 2,000 YAMLs, not a newly sampled surrogate | Frozen candidate manifest | Count 2,000, SHA fingerprint verification |
| 2. HPO training | Exact candidates + software environment | Trained HPO runs | Successful checkpoints and complete run log |
| 3. Validation ranking | Validation predictions, epochs 20/25/30 | Ranked CSV and selected Top-10/cluster configs | Exactly same selected IDs and epochs as archive |
| 4. Final seeded training | Selected configs and study's ten seeds | Seeded model outputs | Train/test protocol and per-seed run identity checked |
| 5. Ensemble evaluation | Test predictions and basin IDs | Basin-level NSE/KGE/etc. | Numerical agreement with released metrics, no test leakage |
| 6. Additional controls | Top-18, constituent and hard-routing scripts/data | Sensitivity diagnostics | Full comparison against released control records |
| 7. Figures | Evaluation products and V17 plot modules | 35 PDF files | V17 gate and HESS filename map pass |
| 8. Tables | HESS manuscript table snapshot | 34 `.tex` snippets | All 34 table labels and full text hash checks pass |

## Required execution checks

The following local commands are read-only apart from specified new output files:

```bash
python tools/verify_hpo_inputs.py --repo . --work-root /path/to/CAMELS_US_WORK --strict
python tools/hpo_candidate_manifest.py --candidate-dir /path/to/original_2000_yamls --verify-manifest /path/to/known_manifest.json
python tools/capture_repro_environment.py --output /path/to/output/reproduction_environment.json
python codes/revision_2026/figures_tables_v17/validate_v17.py
```

The HPO notebook calls long-running training functions explicitly. Its `Run All` action
alone does not submit 2,000 runs. V17 PowerShell runners are Windows-oriented; the
Python table and source validation tools work under Windows and Linux.

## Interpretation of a successful check

A table-hash gate proves identity of published table text, not independently recomputed
measurements. A file-count gate proves that expected outputs exist, not that the values
match. A verified HPO candidate manifest guarantees identity with its *own reference
manifest*; the reference must itself be authenticated against the original study.
Bitwise GPU prediction identity is not guaranteed by fixed seeds alone. Compare model
metrics and scientific conclusions at manuscript rounding precision and disclose any
material deviation.
