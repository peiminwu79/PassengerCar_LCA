# Passenger-car life-cycle emissions and electric-vehicle policy scenarios

Reproducibility files for the study *Sectoral electric-vehicle policies shape passenger-car life-cycle carbon emissions in megacities*, comparing Shanghai and the New York metropolitan area over 2024–2060. The analyses are scenario-based, not causal estimates of observed policies.

This public-share **core package** contains custom code for the main numerical life-cycle emissions analysis (harmonized well-to-wheel energy-use boundaries), scenario comparisons, 10,000-draw Monte Carlo uncertainty analyses, one-factor-at-a-time sensitivity testing, population scenarios, and ArcGIS attribute exports. It also includes the original vehicle-stock PCA/Poisson notebook as a separately documented data-dependent reference.

This is intentionally not an archive of every internal plotting, formatting, historical notebook or diagnostic file. The values underlying manuscript and supplementary quantitative figures are shared in `supplementary_data/`. Third-party software and restricted original datasets are **not** redistributed. See `DATA_ACCESS.md` and `CODE_SCOPE.md`.

## Setup

Python 3.11–3.13:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Reproduce principal numerical results

From the repository root:

```bash
python code/run_all_numeric_experiments.py \
  --sh code/original_inputs/Shanghai_district_vehicle_stock_2024_2060.csv \
  --ny code/original_inputs/NYMA_tract_vehicle_stock_2024_2060.csv \
  --out results

python code/experiment_scripts/05_monte_carlo_vectorized_verified.py \
  --sh code/original_inputs/Shanghai_district_vehicle_stock_2024_2060.csv \
  --ny code/original_inputs/NYMA_tract_vehicle_stock_2024_2060.csv \
  --out results --draws 10000

python code/experiment_scripts/12_original_SI_OFAT.py \
  --sh code/original_inputs/Shanghai_district_vehicle_stock_2024_2060.csv \
  --ny code/original_inputs/NYMA_tract_vehicle_stock_2024_2060.csv \
  --out results
```

To regenerate the year-specific spatial attributes for Fig. 4a, after the first command above:

```bash
python code/experiment_scripts/09_population_and_fig4.py \
  --sh code/original_inputs/Shanghai_district_vehicle_stock_2024_2060.csv \
  --ny code/original_inputs/NYMA_tract_vehicle_stock_2024_2060.csv \
  --spatial results/Manuscript_Fig4_spatial_annual_2024_2060.csv \
  --out results
python code/experiment_scripts/15_export_fig4a_arcgis.py
```

All outputs are created inside `results/` (ignored by Git). The model inputs and outputs retain a historical machine-variable abbreviation `NYMA` solely for compatibility; in the article the region is **New York metropolitan area**.

## Figure data and spatial mapping

The numerical figure source data workbooks (`Supplementary Data`) are available in `supplementary_data/`. The original manuscript and SI figures use Matplotlib/ArcGIS styling; publication-specific plotting notebooks are not part of this *core-code* archive. This does not alter the underlying computed results. Fig. 4a was finalized in ArcGIS, and its modeled attributes can be generated with the supplied scripts (see `CODE_SCOPE.md`). External basemaps, ArcGIS project elements and third-party software are not redistributed.

## Data scope and usage

The vehicle-stock CSVs contain *author-derived model trajectories*, not the restricted original IPUMS NHGIS extracts. Re-estimating the stock PCA/Poisson model requires that readers obtain the underlying ACS/NHGIS extracts from the original provider. Only release the derived inputs and source-data workbooks with all coauthors' approval and after reviewing the relevant source terms. See `DATA_ACCESS.md`.

This repository includes an MIT licence as a **proposal**, inherited from the earlier release candidate; the author team must approve this licence before public publication. Do not add, upload or infer any DOI or GitHub URL until one is actually registered.
