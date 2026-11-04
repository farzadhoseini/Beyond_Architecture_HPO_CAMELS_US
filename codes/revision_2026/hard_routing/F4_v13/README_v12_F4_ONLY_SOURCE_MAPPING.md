# CAMELS F4-only v12 — source-token mapping

This package builds **only** F4: `cluster-local top-3 own-cluster`.
It does not rebuild old Top10/cluster-wise global medians/means.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\run_camels_f4_only_IHCantabria.ps1"
```

Expected F4 logic:

- Read `Clusters&Configs.xlsx` sheet `Cluster-wiseConfigs`.
- Preserve 18 cluster-specific slots and 17 unique source models.
- Build a bridge from source models to the seed-specific prediction tokens stored in `All_Cluster_wise_Configs_CAMELSUS_test.p`.
- For each basin and seed, use only the three selected slots from the basin's own cluster.
- Save new F4 ensembles in the same legacy format:

```python
ensemble[basin][seed]["ensemble"] = xarray.DataArray
```

Key outputs:

```text
00_audit/F4_SOURCE_TO_PREDICTION_TOKEN_BRIDGE_FINAL.csv
00_audit/F4_clusterlocal_median_members_COUNTS.csv
00_audit/F4_clusterlocal_mean_members_COUNTS.csv
01_ensembles_legacy_format/ensemble_ClusterLocal_Top3OwnCluster_CAMELSUS_test_MEDIAN_LEGACY_FORMAT.p
01_ensembles_legacy_format/ensemble_ClusterLocal_Top3OwnCluster_CAMELSUS_test_MEAN_LEGACY_FORMAT.p
02_metrics_legacy_format/F4_metrics_all_test_period_SFmean_by_basin_LEGACY_FORMAT.csv
03_comparisons/F4_paired_NSE_comparisons_vs_previous.csv
03_comparisons/F4_framework_summary.csv
03_comparisons/F4_plus_previous_SFmean_by_basin.csv
```

Important audit rule:

Check `F4_clusterlocal_*_members_COUNTS.csv`. Ideally most basin-seed entries should have 3 members. If some seeds have missing prediction tokens inherited from the legacy export, affected entries may have 2 members. This is not invented; it is audited.
