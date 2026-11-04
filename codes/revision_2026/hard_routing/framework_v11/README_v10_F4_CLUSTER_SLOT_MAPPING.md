# CAMELS Ensemble Framework Bot v10 — F4 Cluster-Slot Mapping

Keeps v9 legacy-format validation and adds the correct F4 construction.

Important correction:
- F4 uses `cluster -> top-3 selected source-model slots`.
- It does not use unique `model -> cluster`, because one source model can be selected in the top-3 of two clusters.
- Duplicate selected models across clusters are expected and audited.

The bot searches recursively for:
- `selected_clusterwise_models.csv`
- fallback: `Ver_results_2000RS_validation_epochs_20_25_30.csv` and rebuilds selected top-3 slots using the GitHub notebook logic.

Expected F4 outputs:
- `00_audit/F4_cluster_slot_map_FINAL.csv`
- `00_audit/F4_duplicate_source_models_across_clusters.csv`
- `00_audit/F4_clusterlocal_median_members.csv`
- `00_audit/F4_clusterlocal_mean_members.csv`
- `01_ensembles_legacy_format/ensemble_ClusterLocal_Top3OwnCluster_CAMELSUS_test_MEDIAN_LEGACY_FORMAT.p`
- `01_ensembles_legacy_format/ensemble_ClusterLocal_Top3OwnCluster_CAMELSUS_test_MEAN_LEGACY_FORMAT.p`
