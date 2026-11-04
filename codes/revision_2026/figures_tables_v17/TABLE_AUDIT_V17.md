# V17 table audit policy

The current manuscripts contain 34 tables: 11 main-text tables and 23 supplementary tables.

V17 intentionally freezes those 34 current LaTeX table environments without silently changing numerical results. This is the safest final-production policy because the tables draw on multiple distinct experiment archives, while the V17 change requested here is an asset-name/output-structure correction rather than a new scientific analysis.

Checks performed before freezing:

- all 34 table labels are unique;
- no current table contains the deprecated publication-facing label `Cluster-wise`;
- the main paired-reference table agrees with the bundled frozen paired-NSE benchmark values;
- the main NSE-threshold table agrees with the bundled 531-basin threshold data;
- the main hydrologic-cluster/aridity effect sizes agree with the bundled pre-Liu summaries to the displayed effect-size/CI precision;
- the HESS metric-context values used by the revision figures agree with the current main/supplementary tables at the displayed precision.

No numerical table change is applied automatically by V17. Any later scientific correction should be made explicitly in the canonical manuscript table and re-frozen, rather than being introduced as an invisible production-side rewrite.

## Explicit correction applied in V17

- `tab:hydro_selection_regimes`, Cluster 1, FDR-adjusted Wilcoxon P: **0.957 -> 0.960**.
- Reason: bundled canonical `clusterwise_vs_top10_by_cluster.csv` reports `wilcoxon_p_fdr_bh = 0.960420`; the table displays this class of value to three decimals.
- Scientific interpretation: unchanged (non-significant); effect size, win rate, and confidence interval are unchanged.
