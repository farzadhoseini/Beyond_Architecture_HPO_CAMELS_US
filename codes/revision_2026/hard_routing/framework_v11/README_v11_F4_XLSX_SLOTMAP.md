# CAMELS Ensemble Framework Bot v11 — Legacy validation + F4 cluster-local from XLSX slot map

This version keeps the validated legacy-format pipeline and adds a reliable F4 cluster-local top-3 own-cluster ensemble using the explicit `Clusters&Configs.xlsx` file.

Key fixes:

- Keeps legacy ensemble output format:
  `ensemble[basin][seed]["ensemble"] = xarray.DataArray`
- Validates rebuilt Top10 and old cluster-wise medians against archived paper pickles.
- Loads F4 mapping from `Clusters&Configs.xlsx`, sheet `Cluster-wiseConfigs`.
- Preserves cluster slots, not unique model-to-cluster mapping:
  `cluster -> [top1, top2, top3]`.
- Allows duplicate source models across clusters; this is expected.
- Builds and evaluates:
  - F1 Top10 median / mean
  - F3 cluster-wise global median / mean
  - F4 cluster-local top-3 own-cluster median / mean

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\run_camels_ensemble_framework_bot_IHCantabria.ps1"
```

Check these after execution:

```text
00_audit\F4_cluster_slot_map_FINAL.csv
00_audit\F4_duplicate_source_models_across_clusters.csv
00_audit\F4_clusterlocal_median_members.csv
00_audit\F4_clusterlocal_mean_members.csv
05_rebuild_validation\legacy_rebuild_validation_summary.csv
04_compact_summaries\framework_summary_from_legacy_SFmean.csv
```

Expected F4 members per basin-seed: 3.
