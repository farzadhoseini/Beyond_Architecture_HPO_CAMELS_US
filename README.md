# Beyond Architecture: Optimization and Hydrologic Regime Reveal Performance Headroom in Deep-Learning Rainfall–Runoff Modelling

**Research code, configurations, evaluation workflows and reproducibility resources for 531 CAMELS-US catchments.**

**Maintainer:** Farzad Hosseini
**Code:** https://github.com/farzadhoseini/Beyond_Architecture_HPO_CAMELS_US
**Research datasets and model outputs:** https://doi.org/10.5281/zenodo.23945464

## Research scope

This project studies how regional LSTM hyperparameter optimization, ensemble selection, and hydrologic regime information influence rainfall–runoff modelling skill on a fixed sample of 531 CAMELS-US basins. The repository contains the regional random-search workflow, evaluation notebooks, selected configurations, additional ensemble-size experiments, hydrologic constituent and routing controls, and scripts for producing the figures and tables associated with the manuscript.

The principal search covers **2,000 regional LSTM configurations**. The main comparison uses validation-selected **Top-10** and **hydrologically informed** ensembles. The additional Top-18 analysis uses eight further configurations trained with ten seeds each; its archived run outputs are provided separately on Zenodo.

## What is in the repository?

| Path | Purpose |
|---|---|
| `codes/CAMELS_US_clean_HPO_repro_package/` | Regional HPO configuration generation, validation ranking, final-run selection, predictions and ensemble metrics |
| `codes/Older_experiment_codes/` | Original model-evaluation notebooks and time-series diagnostics |
| `codes/camels_final_figure_code_v11/` | Original plotting and catchment-level evaluation modules |
| `codes/revision_2026/top18_control/` | Additional eight-configuration training, seeded runs and Top-18 comparisons |
| `codes/revision_2026/constituent_controls/Top10/` | Individual-member evaluation for Top-10 |
| `codes/revision_2026/constituent_controls/HI17/` | Hydrologically informed constituent analysis |
| `codes/revision_2026/hard_routing/` | Hydrologic-cluster routing controls |
| `codes/revision_2026/figures_tables_v17/` | Final figure/table generation, source manifests, and HESS asset-name export |
| `misc/shapefiles/` | Mapping resources |
| `531_basin_list.txt`, `camels_531_master_attributes_clusters.csv`, `CAMELS_US_Clusters.xlsx` | Basin identifiers and hydrologic cluster information |

## Choose a reproducibility route

**Route A — reproduce analyses from archived outputs.** Download the released model predictions and analysis archives from Zenodo; use the original evaluation and `revision_2026` workflows. This avoids retraining the expensive regional HPO campaign. The bundled frozen inputs already support independent generation of the seven revision figures and extraction of the 34 manuscript table environments.

**Route B — rerun the research from HPO.** Begin with the official CAMELS-US observations and forcings, the original NeuralHydrology base configuration, basin/cluster lists and a compatible GPU-enabled Python environment. Run the 2,000-configuration search, select models using validation data, train the selected models with the specified seeds, generate test predictions, and then run the study-specific analyses. This is a much more demanding workflow and requires the input preparation described next.

The repository contains relevant code for both routes, but **it is not an independently tested, one-command end-to-end training distribution**. In particular, it does not bundle the original base YAML, a pinned training environment, or all large input/output archives. Some notebooks and local-run wrappers refer to workstation-specific directories; adapt those to your environment before running. These requirements matter when interpreting reproducibility.

## Route B: from HPO to the manuscript results

### 1. Obtain the data and configure the workspace

- Clone this repository.
- Obtain the original CAMELS-US forcing and discharge data in a format supported by [NeuralHydrology](https://neuralhydrology.readthedocs.io/).
- Download the published model, prediction and analysis artifacts from [Zenodo v3](https://doi.org/10.5281/zenodo.23945464). The release has **10 data files**: eight core files and two 2026 analysis archives. Obtain their exact archived contents before choosing which training stages to rerun.
- Supply `configRegional_Fred.yml`, the original NeuralHydrology base training configuration. **It is a required external input and is not present in the GitHub repository.** Check the downloaded archived configuration files or the research data source for an appropriate verified copy. Do not substitute an arbitrary YAML and expect identical experiments.
- Supply `531Basins.csv` and six validated cluster-split files `cluster_0.txt` through `cluster_5.txt`. The repository's basin list and cluster-attribute CSV can help verify their membership, but cluster identities and basin ordering must match the study's selection protocol.

The core HPO notebook expects this working directory:

```text
CAMELS_US_WORK/
  configs/configRegional_Fred.yml
  data/CAMELS_US/
  data/531Basins.csv
  data/camels_attributes_v2.0/attributes_cluster_splits/
    cluster_0.txt ... cluster_5.txt
  metrics.py
  runs/
    hpo_random_search/
    final_top10/
    final_clusterwise/
  outputs/
    evaluations/
    pickles/
```

The metrics module is at `codes/CAMELS_US_clean_HPO_repro_package/metrics.py`. Check that the base configuration's dataset paths, training/validation/test windows, basin list, input features, NeuralHydrology version and GPU settings match the published experimental protocol.

To inspect the necessary inputs without changing them:

```powershell
python .\tools\verify_hpo_inputs.py --work-root "D:\CAMELS_US_WORK" --repo "." --strict
```

The check must report `HPO_INPUTS_READY=TRUE` before you launch an HPO campaign. It only checks local input presence and basin-list length; it does not verify scientific equivalence of a substituted dataset or configuration.

### 2. Generate and train the 2,000 HPO configurations

Start Jupyter with its **working directory set to `CAMELS_US_WORK`** (the notebook sets `PROJECT_ROOT = Path.cwd()`). Open:

`codes/CAMELS_US_clean_HPO_repro_package/CAMELS_US_clean_HPO_randomsearch_ensemble_evaluation.ipynb`

Follow the notebook in order:

1. Confirm the user-configuration cell (HPO model paths, 531 basins, six clusters, and seed values).
2. Generate 2,000 YAMLs with `generate_random_search_configs(...)` and the specified search space. The consolidated notebook uses `RANDOM_STATE = 42`; its own note indicates that the exploratory search did not originally fix this seed, so repeating the search may yield different candidates from the archived selection.
3. Train the configurations with NeuralHydrology's `schedule_runs` through `run_neuralhydrology_schedule(...)` and GPU settings appropriate for the hardware.
4. Evaluate validation outputs at epochs **20, 25 and 30**, then extract `Ver_results_2000RS_validation_epochs_20_25_30.csv`.

**Execution note:** This notebook defines the functions, but its calls to launch long-running training and evaluation steps are example lines (commented out). Those steps must be invoked deliberately in the notebook, after verifying inputs. Simply selecting *Run All* does not train 2,000 models.

### 3. Select ensembles and evaluate the test period

Continue in the same notebook:

1. Rank the regional configurations on validation data, selecting **Top-10** and **three regionally trained configurations for each of six hydrologic clusters**.
2. Generate the final configuration/seed manifests for the ten predefined seed values.
3. Retrain the selected configurations on the regional training set with those seeds; evaluate on the fixed test period.
4. Extract `All_Top10_Configs_CAMELSUS_test.p`, `All_Cluster_wise_Configs_CAMELSUS_test.p`, and `Obs_test.p`.
5. Construct the two median ensembles, save their prediction pickles, and evaluate basin-wise test metrics.

The detailed file inventory and stage shortcuts are documented in [`codes/CAMELS_US_clean_HPO_repro_package/CAMELS_US_clean_HPO_data_checklist.md`](codes/CAMELS_US_clean_HPO_repro_package/CAMELS_US_clean_HPO_data_checklist.md). The evaluation notebooks under `codes/Older_experiment_codes/` contain additional seasonal, water-year and event-level metrics needed for the full study analysis.

### 4. Run the additional analyses and controls

| Analysis | Start here | Required context |
|---|---|---|
| Top-18 sensitivity | `codes/revision_2026/top18_control/notebooks/CAMELS_US_2026_Step1_v5_7_TRAIN_FIRST_SELECTED_EPOCH_3PARALLEL.ipynb` | Eight additional selected configurations × 10 seeds; processed configs in `top18_control/final_configs/` and run outputs in Zenodo |
| Top-18 evaluation | `codes/revision_2026/top18_control/notebooks/CAMELS_US_2026_Top18_vs_Top10_Final_Analysis_RunAll_FIXED2.ipynb` | Existing Top-10 and hydrologically informed predictions plus eight new configurations |
| Top-10 constituents | `codes/revision_2026/constituent_controls/Top10/` | Individual selected model outputs |
| Hydrologically informed constituents | `codes/revision_2026/constituent_controls/HI17/` | Member-to-prediction mapping and available seeds |
| Hard-routing controls | `codes/revision_2026/hard_routing/` | Regional prediction archives and cluster assignments |
| Spatial and seasonal diagnostics | `codes/Older_experiment_codes/`, `codes/camels_final_figure_code_v11/` | Test predictions, reference benchmarks and CAMELS attributes |

Inspect the notebook path configuration and the relevant README/source file before running each module. The additional control workflows are **separate study analyses**, not automatically invoked by the main HPO notebook. Some tests use external benchmark predictions; they must be sourced with the same basins, periods and evaluation protocol.

### 5. Produce manuscript figures and tables

The V17 builder at `codes/revision_2026/figures_tables_v17/` writes **35 PDF figures (17 main, 18 appendix)** and **34 LaTeX tables (11 main, 23 appendix)** using the prepared project data and study outputs:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File ".\codes\revision_2026\figures_tables_v17\run_CAMELS_v17_FINAL.ps1" `
  -ProjectRoot "D:\CAMELS_US_WORK"
```

**Important:** The V17 runner clears its designated `results/CAMELS_V17_BUILD` and `results/CAMELS_V17_FINAL` folders before rebuilding. Run it in a dedicated working copy, never over irreplaceable data.

The V17 figure names are internal production names. To obtain exactly the filename set referenced by the HESS manuscript, use the **non-destructive export**:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File ".\codes\revision_2026\figures_tables_v17\run_CAMELS_HESS_FINAL.ps1" `
  -ProjectRoot "D:\CAMELS_US_WORK"
```

This command uses the **already built** `results/CAMELS_V17_FINAL` folder, writes 35 renamed PDF copies to `results/CAMELS_HESS_FINAL/figures/`, copies the 34 tables to `results/CAMELS_HESS_FINAL/tables/`, and writes `HESS_ASSET_MANIFEST.json` with SHA-256 checksums. To run V17 first, explicitly add `-BuildV17`. The HESS export refuses a non-empty destination rather than replacing previously generated files.

The mapping between V17 output filenames and manuscript filenames is specified in [`HESS_FIGURE_MAP.json`](codes/revision_2026/figures_tables_v17/HESS_FIGURE_MAP.json), without changes to the plotting algorithms. The export copies table files exactly; the V17 table builder **extracts frozen manuscript table environments** and is not a numerical recomputation of every table from raw hydrological observations.

### 6. Validate scientific comparability

Before interpreting a reproduction as matching the published experiment, check:

- The same 531 basin IDs, clustering and train/validation/test windows.
- The HPO search parameters, selected configuration IDs, training epochs and seeds.
- The aggregation rules for Top-10, hydrologically informed and Top-18 predictions.
- The computation of NSE, KGE and the other metrics and any reference-benchmark alignment.
- The 35 figure filenames, 34 table labels, and the reported results against the manuscript and released archives.

Independent **full-GPU rerunning from HPO through all additional controls** has not been demonstrated by a fresh execution of this repository. The included scripts and released outputs provide a documented research workflow, but the steps above and their external dependencies must be satisfied to substantiate a complete reproduction.

## Using archived results instead of retraining

The release contains the following analysis archives:

- `CAMELS_US_Revision_2026_Analysis_Data_v3_additions.zip`: analysis inputs and outputs used in the revision figures, tables and model controls.
- `CAMELS_US_Top18_Additional8_Raw_10Seed_v3.zip`: raw additional eight-configuration results over ten seeds.

The project provides frozen small-data inputs under `codes/revision_2026/figures_tables_v17/revision_data/`. With a standard scientific Python environment, `revision_results_figures_v17.py` can generate the seven revision figures from those inputs, and `build_tables_v17.py` can extract the 34 LaTeX table environments. For the remaining core figures, the V17 builder also needs the corresponding complete prediction and evaluation inputs.

## Citation and license

Cite the research dataset as **Hosseini, F. (2026)**, *Beyond Architecture: Optimization and Hydrologic Regime Reveal Performance Headroom in Deep-Learning Rainfall–Runoff Modelling* [Dataset], Zenodo: https://doi.org/10.5281/zenodo.23945464. Please cite the associated research article for the scientific methods and findings when available.

Code is distributed under the repository's [Apache License 2.0](LICENSE). Third-party data and external software follow their respective licenses and terms.
