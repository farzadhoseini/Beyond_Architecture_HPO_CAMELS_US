CAMELS-US Top-10 Constituent Decomposition v1
==============================================

Purpose
-------
This is a reproducible alternative to the Global Rank-1 micro-control when the
archived global rank order is not explicitly recoverable.

It does NOT infer Rank-1 from test performance, pickle order, timestamps, cluster
ranks, or positional mapping. Instead, it evaluates all ten validation-selected
Top-10 scientific configurations individually across the same 10 final seeds and
compares them with the frozen Top-10 median ensemble. When the canonical Kratzert
basin table is available, each individual constituent is also compared with the
Kratzert reference.

This cleanly addresses:
  1) whether optimized validation-selected individual configurations already carry
     improvement relative to the established regional reference; and
  2) the incremental effect of ensembling the same optimized configurations.

Run
---
powershell -ExecutionPolicy Bypass -File ".\run_camels_top10_constituent_decomposition.ps1"

No model training is performed.

Safety gates
------------
- 531 basins
- 10 final seeds
- exactly 10 Top-10 member predictions per basin-seed
- rebuilt Top-10 median agrees with frozen ensemble within legacy float precision
- 100 final-run prediction tokens map to exactly 10 unique scientific configs
- each unique config maps to exactly 10 seeds and 5310 basin-seed series
- fixed input configuration audit
- Top-10 NSE self-check against frozen manuscript values
- canonical Kratzert sentinel if recovered

Important
---------
CFG-01 ... CFG-10 are fingerprint-sorted identifiers only. They are NOT validation ranks.
