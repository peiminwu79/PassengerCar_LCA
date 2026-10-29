# Scope of shared code and reproducibility

**Included: essential author-written code**

1. `code/modules/` — vehicle-stock ingestion, policy simulations, emissions factors, electricity supply and population scenarios.
2. `code/run_all_numeric_experiments.py` — primary life-cycle results, principal policy scenarios, spatial results and key sensitivities.
3. `code/experiment_scripts/05_monte_carlo_vectorized_verified.py` — 10,000-draw Monte Carlo implementation with cross-check against the numerical model.
4. `code/experiment_scripts/12_original_SI_OFAT.py` — one-factor-at-a-time parameter sensitivity.
5. `code/experiment_scripts/09_population_and_fig4.py`, `15_export_fig4a_arcgis.py` — population and geographic result tables supporting manuscript Fig. 4a.
6. `code/experiment_scripts/13_wtw_stage_and_fuel_mix_audit.py` — WTW components and upstream energy assumptions.
7. `code/original_style_notebooks/Vehicle_stock_fig2.ipynb` — the original stock modelling and diagnostic reference (the raw NHGIS data must be acquired separately).
8. `supplementary_data/` — numerical values underlying manuscript and SI quantitative figures.

**Not included:** Other exploratory or publication-formatting notebooks, overlapping helper modules from those notebooks, historical versions, draft QA reports, generated PNG/SVG graphics, externally owned NHGIS raw data, MOVES or GREET software, GIS basemap layers and computer-specific application settings. No model equation, numerical scenario parameter or source-data workbook has been revised in creating this shareable subset.

**Scientific boundary:** The released inputs include derived vehicle stock forecasts. The core numerical results can therefore be reproduced from these *derived inputs*, but full end-to-end re-estimation of stocks from the restricted household/census source tables requires separately acquiring those sources. The published manuscript should not claim that the entire original data-to-figure pipeline is available without qualification.

**Source-data qualification:** Spreadsheet source data is not a substitute for code or for licensed original databases. When publishing as journal Supplementary Data files, use the journal's required filenames and link the permanent repository record in the Data Availability statement.
