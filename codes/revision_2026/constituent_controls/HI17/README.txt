CAMELS-US HI17 Constituent Decomposition v2 — 10-seed protocol
===============================================================

Purpose
-------
Tests whether the pooled hydrologically informed (HI) ensemble gain is reproduced by
any of its 17 UNIQUE selected configurations in isolation, using the full prespecified
10-seed final protocol and every archived final realization available.

Design
------
- 18 cluster-conditioned selection slots, 17 unique scientific configurations.
- Full prespecified final seed set:
  191889, 307443, 328237, 385445, 473461, 643969, 665980, 845563, 985957, 993061.
- No training and no test-based constituent selection.
- No missing realization is imputed or replaced.
- Sixteen constituents have all 10 archived final realizations; one historical
  constituent has 5 archived final realizations.
- Constituent absolute metrics use every archived final realization available for that
  constituent.
- For pooled-HI versus a constituent, pooled HI is re-aggregated over exactly the same
  seed subset available for that constituent. Thus the main paired comparison remains
  seed-matched without discarding valid runs from the other 16 constituents.
- Source identity is anchored to the previously verified 5-seed mapping and extended
  to the remaining final runs using scientific config fingerprints (seed/path ignored).
- The raw available-member median is rebuilt independently for every basin and all 10
  seeds and checked against the frozen HI ensemble before metrics are interpreted.

Run
---
From PowerShell:

  cd "PATH\TO\CAMELS_HI17_Constituent_Decomposition_v2_10SEED"
  powershell -ExecutionPolicy Bypass -File ".\run_camels_hi17_constituent_decomposition_10seed.ps1"

Default project root:
  F:\Experiments\CAMELS_US\Clean_4_upload

Important interpretation boundary
---------------------------------
HI-CFG-01 ... HI-CFG-17 are arbitrary identifiers, not validation ranks.
This is a constituent-versus-pooling decomposition. It does not causally isolate HPO.
