# Data access, provenance and redistribution

## Data released with this repository

- `code/original_inputs/Shanghai_district_vehicle_stock_2024_2060.csv`: author-derived district-level vehicle-stock trajectories.
- `code/original_inputs/NYMA_tract_vehicle_stock_2024_2060.csv`: author-derived vehicle-stock trajectories for 4,798 valid census tracts across 22 counties in the New York metropolitan area. **Author approval and third-party terms review are required before public release of this derived file.**
- `code/data_inputs/`: documented demographic, electricity and fuel-cycle calculation inputs. Each input's evidence status and source URL are listed in `code/documentation/NON_GENERATED_INPUTS_AND_EVIDENCE_REGISTER.csv` and `code/data_inputs/FACTOR_EVIDENCE_AUDIT.csv`.
- `supplementary_data/`: 21 per-figure Excel workbooks with numerical source data from the manuscript and SI, plus an index and crosswalk. Workbooks are copies of the previously verified data; values have not been regenerated or changed here.

## Original data not redistributed

**IPUMS NHGIS.** Complete raw extracts `nhgis0001_ds272_20245_tract.csv` and `nhgis0002_ds272_20245_tract.csv` are omitted. Readers can register at https://www.nhgis.org/ and request the ACS 2020–2024 five-year tract tables (including B08301, B25024, B25044) used in the model. NHGIS restricts unrestricted redistribution of raw extracts; see https://www.nhgis.org/ipums-nhgis-terms-use and https://www.nhgis.org/citation-and-use-nhgis-data. The spatial sample contains 4,914 candidate tracts, 116 excluded for zero feature denominators, leaving 4,798 valid tracts. Use the data version specified in the published article.

**Shanghai statistical sources.** The original stock-feature inputs reference *Shanghai Statistical Yearbook 2024* and the 2020 Population Census; the year-specific population denominator scenario refers to 2024 district observations in *Shanghai Statistical Yearbook 2025*. Official yearbooks can be accessed through https://tjj.sh.gov.cn/tjnj/ and the relevant numbered tables are identified in the Supplementary Information. Original yearbook publications are not republished here.

**Additional inputs.** Region-specific electricity factors are based on U.S. EPA eGRID (https://www.epa.gov/egrid), U.S. EIA Annual Energy Outlook (https://www.eia.gov/outlooks/aeo/), and New York metropolitan population forecasts supplied by NYMTC, NJTPA and DVRPC. MOVES and GREET are third-party modelling tools; this repository does not contain or license either proprietary executable or their complete databases. The roles of these resources are explained in the manuscript and SI.

## Independent reproduction

The public derived vehicle-stock files permit recalculation of the life-cycle and policy-scenario outputs, including uncertainty and sensitivity results. For independent re-estimation of the **earlier** PCA/Poisson stock model, supply the NHGIS extracts downloaded under your own registration to `code/original_inputs/`, then use `code/original_style_notebooks/Vehicle_stock_fig2.ipynb` with its setup cell (it depends on `figure_io.py` and `figure_style.py`). This package cannot independently reconstruct the restricted ACS input data.

The figure-number crosswalk in `supplementary_data/` refers to the reordered second-round Supplementary Information. Check against any later editorial re-numbering before submission.
