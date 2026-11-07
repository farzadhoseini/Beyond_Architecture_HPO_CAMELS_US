# Beyond Architecture: Optimization and Hydrologic Regime Reveal Performance Headroom in Deep-Learning Rainfall–Runoff Modelling

**Research code, experiment configurations, evaluation outputs, and reproducibility resources for 531 CAMELS-US basins.**

- **Maintainer:** Farzad Hosseini
- **Code:** https://github.com/farzadhoseini/Beyond_Architecture_HPO_CAMELS_US
- **Research data and model outputs:** https://doi.org/10.5281/zenodo.23945464

## Overview

This repository investigates the roles of hyperparameter optimization (HPO), ensemble construction, and hydrologic regime information in regional long short-term memory (LSTM) rainfall–runoff modelling. It includes the 2,000-configuration regional random-search workflow, selected ensembles, basin-level diagnostics, constituent and routing controls, sensitivity analyses, and figure/table production scripts.

The methods and results use a fixed sample of 531 CAMELS-US basins. Several comparison workflows use previously published external benchmark predictions under their stated protocols; the corresponding experimental assumptions are documented in the analysis sources.

## Repository contents

| Location | Contents |
|---|---|
| `codes/CAMELS_US_clean_HPO_repro_package/` | Regional HPO, evaluation metrics, configuration handling and ensemble utilities |
| `codes/Older_experiment_codes/` | Experimental notebooks and processing workflows supporting the regional benchmark |
| `codes/camels_final_figure_code_v11/` | Basin, cluster, seasonal and hydrograph visualizations |
| `codes/revision_2026/top18_control/` | Top-18 versus Top-10 sensitivity analysis, selected configurations and aggregate results |
| `codes/revision_2026/constituent_controls/Top10/` | Individual Top-10 configuration analyses |
| `codes/revision_2026/constituent_controls/HI17/` | Hydrologically informed constituent comparisons |
| `codes/revision_2026/hard_routing/` | Cluster-local routing and associated evaluation controls |
| `codes/revision_2026/figures_tables_v17/` | Scripts, manifests, fixed source tables and builders for manuscript figures/tables |
| `misc/shapefiles/` | Geospatial resources used by mapping workflows |
| Root-level CAMELS-US files | Basin identifiers, attributes, cluster assignments and diagnostic summaries |

For experiment-level details, start with [`codes/revision_2026/README_2026_REVISION.md`](codes/revision_2026/README_2026_REVISION.md).

## Data access

The dataset and model-output archives are available at [Zenodo v3](https://doi.org/10.5281/zenodo.23945464). The release has **10 files**, consisting of eight core research-data files and two additional analysis archives:

- `CAMELS_US_Revision_2026_Analysis_Data_v3_additions.zip` — analysis inputs, results, and figure/table support artifacts.
- `CAMELS_US_Top18_Additional8_Raw_10Seed_v3.zip` — outputs from eight additional selected configurations evaluated with ten random seeds each.

The Zenodo model and prediction archives are required for workflows that depend on precomputed outputs. To start from raw hydrological observations, obtain the official CAMELS-US dataset and meteorological forcing series with the relevant permissions and follow the data checklist at [`codes/CAMELS_US_clean_HPO_repro_package/CAMELS_US_clean_HPO_data_checklist.md`](codes/CAMELS_US_clean_HPO_repro_package/CAMELS_US_clean_HPO_data_checklist.md).

## Reproducing analyses

1. **Prepare the environment.** Use Python with the scientific packages imported by the scripts being executed. Training and evaluation workflows rely on their respective original dependencies, including the hydrological deep-learning stack, NumPy, pandas and scientific plotting libraries.
2. **Configure paths.** Some scripts and notebooks include workstation-specific absolute directories. Point their input and output locations to a local CAMELS-US working directory and downloaded Zenodo archives. Check a script's arguments and source-level instructions before executing it.
3. **Run the required stage.** Start with the regional HPO and ensemble code for model-building workflows, or use the corresponding `codes/revision_2026/` folder for analysis of available predictions and controls.
4. **Produce paper assets.** The V17 builder can produce the configured collection of 35 PDF figures and 34 LaTeX tables after the required data and intermediate results have been arranged in the expected project structure.

Example on Windows, in a PowerShell session with the required Python environment active:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File ".\codes\revision_2026\figures_tables_v17\run_CAMELS_v17_FINAL.ps1" `
  -ProjectRoot "D:\CAMELS_US_WORK"
```

`ProjectRoot` must contain the input data and expected working structure used by the asset scripts. The builder creates files in `results/CAMELS_V17_FINAL/` under that root and **may remove/recreate its designated build and final-output directories**. Use an isolated working directory, not the only copy of irreplaceable results.

The V17 table builder extracts 34 defined table environments from its bundled LaTeX reference inputs; it does not independently recompute every numerical result from raw observations. Running the entire training campaign from scratch requires the corresponding data, computational resources, and software environment.

## Citation and license

For the public dataset and model outputs, cite **Hosseini, F. (2026), Zenodo, DOI: [10.5281/zenodo.23945464](https://doi.org/10.5281/zenodo.23945464)**. For the associated scientific methods and conclusions, cite the article when a journal version becomes available.

The repository code is released under [Apache License 2.0](LICENSE). Third-party input datasets and other external resources remain subject to their own terms.
