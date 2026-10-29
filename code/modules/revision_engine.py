"""Emission accounting for the Shanghai / 22-county NYMA second revision.

This module does not contain plotting code. Empirical 2024 Shanghai grid
CO2 and eGRID2023 US electricity factors (2024 preceding-vintage proxies) are
separated from explicitly assumed 2025-2060 decarbonization scenarios.
Do not describe the scenario series as observed or independently forecast data.
No research experiment is run by importing this file.
"""
from pathlib import Path
import math
import electricity_wtp as EW
import pandas as pd

BASE_YEAR = 2024
BEV_KWH_PER_KM = 0.16
PHEV_ELECTRIC_FRACTION = 0.50
TTW_BASE_GCO2_PER_KM = 400.0 * 0.621371
TTW_ANNUAL_IMPROVEMENT = 0.005
# Gas coverage audit (GWP100 AR5). U.S. EPA 2025 Factors Hub Table 3,
# gasoline passenger cars MY2022; latest observation in that table.
# Apply as an explicit vehicle-fleet proxy to both cities (NOT measured Shanghai).
# Constant absolute gCO2e/km: no defensible future model-year mix available.
# CH4/N2O values are in g gas / vehicle-mile, not CO2e units.
GWP100_CH4, GWP100_N2O = 28.0, 265.0
EPA_CH4_G_PER_MILE_2022 = 0.0050
EPA_N2O_G_PER_MILE_2022 = 0.0014
TAILPIPE_NONCO2_GCO2E_GKM = (EPA_CH4_G_PER_MILE_2022*GWP100_CH4 + EPA_N2O_G_PER_MILE_2022*GWP100_N2O)/1.609344
# Shanghai public 2024 electricity direct factor is CO2-only. IPCC 2006
# Guidelines Vol. 2, Ch. 2, Table 2.2 gives power fuel CO2/CH4/N2O
# (kg/TJ NCV): other bituminous coal 94600/1/1.5, gas 56100/1/0.1.
# Allocation 90% coal / 10% gas by DIRECT CO2 is a study assumption
# inherited from electricity_wtp.py, not observed Shanghai grid fuel shares.
SH_COAL_DIRECT_SHARE = EW.SH_COAL_DIRECT_CO2_SHARE_ASSUMED
SH_COAL_NONCO2_RATIO = (1.0*GWP100_CH4+1.5*GWP100_N2O)/94600.0
SH_GAS_NONCO2_RATIO = (1.0*GWP100_CH4+0.1*GWP100_N2O)/56100.0
SH_GENERATION_NONCO2_OVER_CO2 = SH_COAL_DIRECT_SHARE*SH_COAL_NONCO2_RATIO+(1-SH_COAL_DIRECT_SHARE)*SH_GAS_NONCO2_RATIO
# Within-source, consistent fuel heating-value boundary. This eliminates the
# prior error of dividing NY gasoline HHV WTP by China's 67.9-g/MJ denominator.
# SH: 2013 Chinese fuel LCA Table 2 (NOT yet independently verified China-GREET
# Table S4); GWP100 AR5 28/265; 20.2 g CO2 + 0.05 g CH4 + 0.49 mg N2O per MJ.
SH_GASOLINE_COMBUSTION_GCO2_PER_MJ = 67.9
SH_GASOLINE_WTP_GCO2EQ_PER_MJ = 20.2 + 0.05*28.0 + 0.00049*265.0
# NY: NYSERDA report 25-02 Appendix D Table D-3, 2022, HHV, lb/MMBtu.
# Out-of-state upstream totals CO2/CH4/N2O: 40.43 / .27 / .00070;
# petroleum gasoline direct combustion CO2: 144.12 lb/MMBtu.
NY_GASOLINE_COMBUSTION_LB_CO2_PER_MMBTU = 144.12
NY_GASOLINE_WTP_LB_CO2EQ_PER_MMBTU = 40.43 + 0.27*28.0 + 0.00070*265.0
UPSTREAM_TTW_RATIO = {
    "SH": SH_GASOLINE_WTP_GCO2EQ_PER_MJ / SH_GASOLINE_COMBUSTION_GCO2_PER_MJ,
    "NYMA": NY_GASOLINE_WTP_LB_CO2EQ_PER_MMBTU / NY_GASOLINE_COMBUSTION_LB_CO2_PER_MMBTU,
}
# Boundaries: fossil-gasoline reference fuel; blending (ethanol), region-specific
# PHEV combustion efficiency and uncertain upstream electric fuel supply are
# limitations and need reporting rather than invented route factors.
MFG_REC_GCO2EQ_PER_KM = {"ICEV": 29.2, "BEV": 50.0, "PHEV": 39.6}
# Shanghai official 2024 consumer/public electricity direct-generation CO2 EF,
# published 2026-01-12 (Shanghai Ecology and Environment / Statistics Bureau).
# Includes net imported grid electricity; not a fuel-supply upstream LCA factor.
SH_GRID_AVG_2024 = 470.1
# 2024 East China OM (published 2026), project-baseline/non-actual marginal proxy;
# historical-period weighted proxy rather than metered incremental EV charging EF.
SH_GRID_MARGINAL_2024 = 778.2
SH_GRID_2050_ASSUMPTION = 20.0  # original study's 2050 scenario endpoint

NY_COUNTIES = frozenset({"36061", "36047", "36081", "36005", "36085", "36059", "36103", "36119", "36087", "36079"})
NJ_COUNTIES = frozenset({"34017", "34003", "34031", "34013", "34039", "34027", "34037", "34023", "34035", "34019", "34025", "34029"})
NYMA_COUNTIES = NY_COUNTIES | NJ_COUNTIES
NYC_COUNTIES = frozenset({"36061", "36047", "36081", "36005", "36085"})
NYLI_COUNTIES = frozenset({"36059", "36103"})
NYUP_COUNTIES = frozenset({"36087", "36079"})

# Candidate mapping, pending official eGRID geography lookup.  Not an asserted
# physical delivery source for each individual EV charging station.
def nyma_subregion(region_id):
    text = str(region_id).strip().split(".")[0].zfill(5)
    county = text[:5]
    if county not in NYMA_COUNTIES:
        raise ValueError(f"County FIPS outside the 22-county NYMA: {region_id!r} => {county}")
    if county in NYC_COUNTIES or county == "36119":
        return "NYCW"
    if county in NYLI_COUNTIES:
        return "NYLI"
    if county in NYUP_COUNTIES:
        return "NYUP"
    return "RFCE"


def require_22_counties(ids):
    actual = {str(x).strip()[:5] for x in ids}
    missing = NYMA_COUNTIES - actual
    extra = actual - NYMA_COUNTIES
    if missing or extra:
        raise ValueError(f"NYMA county mismatch: missing={sorted(missing)} extra={sorted(extra)}")

# grid_factors.csv is populated with 2023-vintage EPA proxies for 2024 and
# explicit non-empirical 2025-2060 grid policy scenario trajectories.
GRID_FILE = Path(__file__).with_name("grid_factors.csv")
_GRID_CACHE = None

def grid_table():
    global _GRID_CACHE
    if _GRID_CACHE is not None:
        return _GRID_CACHE
    if not GRID_FILE.is_file():
        raise FileNotFoundError(f"Supply verified 2024–2060 grid inputs at {GRID_FILE}")
    df = pd.read_csv(GRID_FILE, dtype={"region":str})
    required = {"region", "year", "average_gco2eq_per_kwh", "marginal_gco2eq_per_kwh"}
    if not required.issubset(df.columns):
        raise ValueError(f"Required grid CSV columns: {sorted(required)}")
    if df.duplicated(["region", "year"]).any():
        raise ValueError("Duplicate region/year rows in grid_factors.csv")
    df["year"] = df["year"].astype(int)
    _GRID_CACHE = df.set_index(["region", "year"])
    return _GRID_CACHE


def nyma_grid_ci(year, region_id=None, kind="average"):
    if region_id is None:
        raise ValueError("NYMA grid EF must be indexed by a county/tract region_id; no single NYISO EF.")
    subregion = nyma_subregion(region_id)
    column = {"average":"average_gco2eq_per_kwh", "marginal":"marginal_gco2eq_per_kwh"}[kind]
    try:
        value = grid_table().loc[(subregion, int(year)), column]
    except KeyError as e:
        raise ValueError(f"Missing {kind} grid EF: subregion={subregion}, year={year}") from e
    if pd.isna(value) or not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"Invalid or unavailable {kind} grid EF at {subregion}/{year}: {value!r}")
    return float(value)


def sh_grid_ci(year, kind="average"):
    y = int(year)
    if kind == "average":
        if y <= BASE_YEAR:
            return SH_GRID_AVG_2024*(1+SH_GENERATION_NONCO2_OVER_CO2)
        if y >= 2050:
            return SH_GRID_2050_ASSUMPTION*(1+SH_GENERATION_NONCO2_OVER_CO2)
        return (SH_GRID_AVG_2024 + (SH_GRID_2050_ASSUMPTION-SH_GRID_AVG_2024)*(y-BASE_YEAR)/(2050-BASE_YEAR))*(1+SH_GENERATION_NONCO2_OVER_CO2)
    if kind == "marginal":
        # Sensitivity proxy: keeps the original relative decline, NOT a measured
        # marginal dispatch forecast. Distinguish it clearly in the SI.
        return sh_grid_ci(y, "average") * (SH_GRID_MARGINAL_2024/SH_GRID_AVG_2024)
    raise ValueError(kind)


def grid_ci(city, year, region_id=None, kind="average"):
    return sh_grid_ci(year,kind) if city == "SH" else nyma_grid_ci(year,region_id,kind)


def gasoline_combustion_co2_gkm(year):
    return TTW_BASE_GCO2_PER_KM * (1-TTW_ANNUAL_IMPROVEMENT)**(int(year)-BASE_YEAR)

def gasoline_ttw_gkm(year):
    return gasoline_combustion_co2_gkm(year)+TAILPIPE_NONCO2_GCO2E_GKM


def gasoline_wtp_gkm(city, year, upstream_scale=1.0):
    # The gasoline consumption used for WTP evolves with ICEV technology.
    # Source-matched WTP/TTW factor is dimensionless; prevents mixing US HHV
    # with China LHV-based fuel MJ. Declining fuel use follows ICEV efficiency.
    return gasoline_combustion_co2_gkm(year) * UPSTREAM_TTW_RATIO[city] * upstream_scale


def ef(city, powertrain, year, region_id=None, uf=PHEV_ELECTRIC_FRACTION,
       kind="average", include_mfg=True, upstream_scale=1.0):
    if not 0 <= uf <= 1:
        raise ValueError("PHEV utility factor must be in [0,1]")
    gasoline = gasoline_ttw_gkm(year) + gasoline_wtp_gkm(city,year,upstream_scale)
    reg = 'SH' if city=='SH' else nyma_subregion(region_id)
    direct_grid = grid_ci(city,year,region_id,kind)
    grid_wtw = direct_grid+EW.upstream_for_direct(reg,direct_grid,kind=kind)
    if powertrain == "ICEV":
        use = gasoline
    elif powertrain == "BEV":
        use = grid_wtw*BEV_KWH_PER_KM
    elif powertrain == "PHEV":
        use = (1-uf)*gasoline + uf*grid_wtw*BEV_KWH_PER_KM
    else:
        raise ValueError(powertrain)
    return use + (MFG_REC_GCO2EQ_PER_KM[powertrain] if include_mfg else 0.0)


def policy_grid_ci(city, year, region_id, target_year=None, kind="average"):
    """Hypothetical accelerated grid-policy scenario, separate NY/NJ goals.

    For New York the counterfactual reference phase-out endpoint is 2040.
    NJ is an RFCE/PJM proxy with a 2050 modelling endpoint (not a claim that
    NJ follows NY CLCPA). A 5-year acceleration of NY to 2035 accelerates NJ
    by 5 years to 2045, not to NY's 2035. This is a SCENARIO ASSUMPTION.
    """
    y = int(year)
    target_year = int(target_year or (2045 if city == "SH" else 2035))
    start = grid_ci(city, BASE_YEAR, region_id, kind)
    if city == "SH":
        actual_target_year = target_year
        ref_end = SH_GRID_2050_ASSUMPTION*(1+SH_GENERATION_NONCO2_OVER_CO2)
        target = ref_end if kind == "average" else ref_end*(SH_GRID_MARGINAL_2024/SH_GRID_AVG_2024)
    else:
        subregion = nyma_subregion(region_id)
        if subregion == "RFCE":
            actual_target_year = 2050 + (target_year-2040)
            # 2050 endpoint in NJ central scenario (20 g CO2e/kWh average).
            target = grid_ci(city, 2060, region_id, kind)
        else:
            actual_target_year = target_year
            target = 0.0
    if actual_target_year <= BASE_YEAR:
        raise ValueError("Target year must exceed 2024")
    if y <= BASE_YEAR:
        return start
    if y >= actual_target_year:
        return target
    return start + (target-start)*(y-BASE_YEAR)/(actual_target_year-BASE_YEAR)


def revised_policy_emissions(policy, year, icev_ef, bev_ef, phev_ef, city, region_id,
                             uf=PHEV_ELECTRIC_FRACTION, kind="average"):
    """Limit V2G/battery/grid impacts to the ELECTRIC portion of PHEV use.

    Falls back to original policy.apply_emission for unrelated interventions,
    preserving user-defined policy response and plot data structures.
    """
    name = policy.__class__.__name__
    params = getattr(policy,"params",{}) or {}
    if name in {"V2GPolicy", "BatteryChargingPolicy"}:
        if name == "V2GPolicy" and city != "SH":
            return icev_ef,bev_ef,phev_ef
        if name == "V2GPolicy":
            reduction = params.get("reduction",0.15) if int(year)>=2028 else 0.0
        else:
            reduction = params.get("improvement",0.12)*min(1.0,max(0.0,(int(year)-2024)/11.0))
        direct=grid_ci(city,year,region_id,kind)
        reg='SH' if city=='SH' else nyma_subregion(region_id)
        elec_component=(direct+EW.upstream_for_direct(reg,direct,kind=kind))*BEV_KWH_PER_KM
        return icev_ef, bev_ef-reduction*elec_component, phev_ef-reduction*uf*elec_component
    if name == "GridDecarbPolicy":
        alt=policy_grid_ci(city,year,region_id,params.get("target_year"),kind)
        ref=grid_ci(city,year,region_id,kind)
        region = 'SH' if city=='SH' else nyma_subregion(region_id)
        alt_wtp=EW.upstream_for_direct(region,alt,kind=kind)
        ref_wtp=EW.upstream_for_direct(region,ref,kind=kind)
        delta = ((alt+alt_wtp)-(ref+ref_wtp))*BEV_KWH_PER_KM
        return icev_ef,bev_ef+delta,phev_ef+uf*delta
    return policy.apply_emission(year,icev_ef,bev_ef,phev_ef)


def relative_charge_service(demand_ratio, capacity_ratio=1.0, eps_a=-0.55, eps_s=-0.40):
    """Multiplicative capacity/pressure response; cannot imply negative service.

    Baseline normalized to 1. Result is fractional response and bounded SPI.
    """
    if demand_ratio<=0 or capacity_ratio<=0:
        raise ValueError("Demand and service capacity ratios must be positive")
    pressure=demand_ratio/capacity_ratio
    accessibility = pressure**eps_a
    coverage = pressure**eps_s
    spi=pressure/(1+pressure)
    return (accessibility-1)*100,(coverage-1)*100,spi
