# CAMELS Ensemble Framework Bot IHCantabria v9 — LEGACY FORMAT VALIDATION

This version deliberately preserves the old Journal-of-Hydrology submission pickle formats.

## What changed vs v8

- Ensemble outputs are saved as `ensemble[basin][seed]["ensemble"] = xarray.DataArray`, not compact `{basin: array}`.
- Top10 and old cluster-wise medians are rebuilt from `All_*` and compared against the existing submitted-paper median pickles at basin/seed/timestep level.
- New mean ensemble pickles are saved in the same legacy format.
- Metrics are saved as pickle + CSV DataFrames in legacy-compatible forms:
  - `metrics_all_test_period_seed_level_LEGACY_FORMAT.p/csv`
  - `metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.p/csv`
- F4 cluster-local is skipped unless a model-token -> cluster mapping CSV is available.

## Run

```powershell
powershell -ExecutionPolicy Bypass -File ".un_camels_ensemble_framework_bot_IHCantabria.ps1"
```

First inspect:

```text
05_rebuild_validation\legacy_rebuild_validation_summary.csv
00_audit\All_Top10_structure.csv
00_audit\All_Clusterwise_structure.csv
02_metrics_legacy_format\metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.csv
```

Only trust mean/F4/Top18 after `all_within_tolerance = True` for Top10 and old cluster-wise median rebuilds.
