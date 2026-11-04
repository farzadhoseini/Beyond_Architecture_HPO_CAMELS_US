# CAMELS F4-only v13 — metrics fix

This package only builds F4 cluster-local Top-3 own-cluster ensembles and compares them with previous validated SFmean outputs.

Fix relative to v12:
- Does not rebuild Top10 or F3 global ensembles.
- Fixes observation lookup: no boolean evaluation of xarray objects.
- Keeps legacy ensemble output format: `ensemble[basin][seed]["ensemble"] = xarray.DataArray`.
- Uses the XLSX cluster-slot map: 18 cluster slots, 17 unique source models.

Run:
```powershell
powershell -ExecutionPolicy Bypass -File ".\run_camels_f4_only_IHCantabria.ps1"
```

Expected key log lines:
- `Built F4 median ensemble ... members min=2 median=3.0 max=3`
- `Computing F4 seed-level metrics ...`
- `Done. F4-only results saved under ...`

Key outputs:
- `00_audit/F4_clusterlocal_median_members_COUNTS.csv`
- `02_metrics_legacy_format/F4_metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.csv`
- `03_comparisons/F4_framework_summary.csv`
- `03_comparisons/F4_paired_NSE_comparisons_vs_previous.csv`
