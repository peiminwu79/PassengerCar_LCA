"""Documented fuel-cycle (not power-plant construction) upstream proxy for EV electricity.

Grid direct factors are from Shanghai public power CO2 (2024) / US EPA eGRID2023
(2024 preceding-vintage proxy). They EXCLUDE fuel supply. Here we estimate the
additional WELL-TO-PLUG *fuel-cycle* GHG component, not the broader electricity
carbon footprint (which also includes infrastructure and plant manufacture).

Input limitations: Shanghai consumption grid's fuel mix is not published here;
its 2024 coal/gas direct-emission allocation is a *declared assumption* informed
by national coal production research, not measured Shanghai generation. NYMA
shares are EPA eGRID2023 subregion GENERATION resource mixes (not tracing the
actual electrons used at EV charging sites). Future resource shares and upstream
intensities are scenario proxies, NOT observations. GWP100 AR5 CH4=28/N2O=265.

The nuclear 2.7 gCO2e/kWh corresponds to uranium *fuel cycle* only (US GREET,
Ng et al 2025), NOT nuclear full LCA. Wind/solar/hydro have zero fuel supply,
but their capital equipment embodied emissions are outside this fuel-cycle-only
WTW scope. Do NOT add Chinese lifecycle electricity 0.5777kg/kWh to power EF.
"""
from __future__ import annotations
import math

# EPA eGRID 2023 Rev 2, Table 2; percent of generation (not purchased power).
# Order: coal, oil, natural gas, other fossil, nuclear. Balance = nonfuel energy.
US_MIX = {
    'NYCW': (0.000, 0.005, 0.982, 0.007, 0.000),
    'NYLI': (0.000, 0.015, 0.872, 0.048, 0.000),
    'NYUP': (0.000, 0.001, 0.255, 0.003, 0.323),
    'RFCE': (0.047, 0.001, 0.541, 0.007, 0.364),
}
# Approximate direct output combustion factor by plant fuel (g CO2/kWh).
# Used ONLY to allocate observed EPA eGRID total CO2 emissions by fuel;
# the region's actual CO2 intensity remains fixed by eGRID, NOT these values.
FUEL_DIRECT_ALLOCATION_GPKWH = {'coal': 1000., 'oil': 800., 'gas': 480., 'other_fossil': 900.}
GWP_CH4, GWP_N2O = 28.0, 265.0
# NYS DEC Statewide GHG Report 2024, Appendix A Table A1, 2022 imported
# fuel upstream, g CO2/CH4/N2O per MMBtu (HHV); 20-year totals NEVER used.
_NY_WTP_G_MMBTU={
    'gas': (12549., 337., 0.14),
    'coal': (3297., 460., 0.10),
    'oil': (13634., 117., 0.25),  # distillate, also proxy other fossil
}
# Matched HHV combustion for conventional coal, natural gas, distillate;
# kg CO2/MMBtu, EPA typical carbon emissions factors (approximate allocation).
_NY_TTW_KG_MMBTU={'gas':53.06, 'coal':95.52, 'oil':73.96}
US_UPSTREAM_TTW_RATIO = {
    f:(co2+ch4*GWP_CH4+n2o*GWP_N2O)/(1000*_NY_TTW_KG_MMBTU[f])
    for f,(co2,ch4,n2o) in _NY_WTP_G_MMBTU.items()
}
# China-specific coal mining/washing, fugitive, coal transport versus
# power-plant combustion (national coal-electricity chain; Zhang/Wu et al,
# Int J Low Carbon Technologies 2024, 2021 data), a country level proxy.
SH_COAL_UPSTREAM_TO_COMBUSTION=(52_830_240+387_265_868+51_249_781)/4_826_612_103
# IEA LNG supply 2025: ~11.5 g CO2e/MJ production/processing/transport,
# typical fuel use combustion 55 gCO2/MJ. GLOBAL NG SUPPLY proxy for Shanghai
# only; Shanghai gas imports, sourcing and actual mix not directly measured.
SH_GAS_UPSTREAM_TO_COMBUSTION=11.5/55.0
# This is a *combustion emission allocation*, NOT a verified Shanghai mix.
SH_COAL_DIRECT_CO2_SHARE_ASSUMED=0.90
# National 2024 nuclear power generation / total (NBS), Shanghai mix unknown.
SH_NUCLEAR_GENERATION_SHARE_PROXY=4508.5/100868.8
# US GREET nuclear uranium fuel supply only (Ng et al, J Industrial Ecology 2025)
NUCLEAR_UPSTREAM_FUEL_CYCLE_GPKWH=2.7

SOURCES={
 'egrid':'https://www.epa.gov/system/files/documents/2025-06/summary_tables_rev2.pdf',
 'fuel_combustion':'https://www.govinfo.gov/content/pkg/CFR-2025-title40-vol23/pdf/CFR-2025-title40-vol23-part98.pdf',
 'us_fuels':'https://dec.ny.gov/sites/default/files/2025-12/ghgemissionsreport2024.pdf',
 'china_coal':'https://academic.oup.com/ijlct/article/doi/10.1093/ijlct/ctae181/7762370',
 'china_ng':'https://www.iea.org/reports/assessing-emissions-from-lng-supply-and-abatement-options',
 'nuclear':'https://onlinelibrary.wiley.com/doi/10.1111/jiec.70008',
 'china_nuclear_share':'https://www.stats.gov.cn/english/PressRelease/202502/t20250228_1958822.html',
 'electric_footprint_crosscheck':'https://www.mee.gov.cn/xxgk2018/xxgk/xxgk01/202510/t20251024_1130734.html',
}

def region_2024_decomposition(region):
    """Fuel-wise 2024 upstream/direct ratio + additive nuclear fuel-cycle anchor.
    Direct electricity emission excludes uranium and renewables WTT.
    """
    if region=='SH':
        coal=SH_COAL_DIRECT_CO2_SHARE_ASSUMED
        gas=1.-coal
        ratio=coal*SH_COAL_UPSTREAM_TO_COMBUSTION+gas*SH_GAS_UPSTREAM_TO_COMBUSTION
        nuclear=SH_NUCLEAR_GENERATION_SHARE_PROXY*NUCLEAR_UPSTREAM_FUEL_CYCLE_GPKWH
        return dict(coal_direct_fraction=coal,gas_direct_fraction=gas,
            oil_direct_fraction=0.0, fossil_wtp_over_direct_ratio=ratio,
            nuclear_upstream_g_per_kwh=nuclear,assumption='national-China-coal/NaturalGas-proxy')
    if region not in US_MIX: raise ValueError(f'Unknown grid region {region!r}')
    coal,oil,gas,other,nuclear_share=US_MIX[region]
    shares={'coal':coal,'oil':oil+other,'gas':gas}
    energy={fuel:shares[fuel]*FUEL_DIRECT_ALLOCATION_GPKWH[fuel] for fuel in shares}
    denom=sum(energy.values())
    if denom<=0: raise ValueError('No fossil fuel in region resource mix')
    direct_shares={k:v/denom for k,v in energy.items()}
    ratio=sum(direct_shares[k]*US_UPSTREAM_TTW_RATIO[k] for k in shares)
    return dict(coal_direct_fraction=direct_shares['coal'],
      gas_direct_fraction=direct_shares['gas'],
      oil_direct_fraction=direct_shares['oil'],
      fossil_wtp_over_direct_ratio=ratio,
      nuclear_upstream_g_per_kwh=nuclear_share*NUCLEAR_UPSTREAM_FUEL_CYCLE_GPKWH,
      assumption='EPA-eGRID2023-fuelmix_NYSDEC-upstream')

def upstream_for_direct(region,direct_g_per_kwh,scale=1.0,kind='average'):
    """Fuel-cycle WTP, gCO2e/kWh, at final electricity output factor.

    The unobserved future fuel mix assumes fossil fuel types decline
    proportionally with fossil DIRECT intensity. Nuclear generation share is
    held constant (only its upstream fuel supply remains when fossil direct=0).
    Marginal/nonbaseload scenario proxies include only fossil fuel-cycle,
    as nuclear is not assumed to generate the incremental kWh.
    """
    val=float(direct_g_per_kwh)
    if not math.isfinite(val) or val<0 or scale<0:raise ValueError('Bad grid WTP parameters')
    d=region_2024_decomposition(region)
    nonfossil=0.0 if kind=='marginal' else d['nuclear_upstream_g_per_kwh']
    return float(scale)*(val*d['fossil_wtp_over_direct_ratio']+nonfossil)


def yearly_audit(regions,years,grid_fn):
    rows=[]
    for region in regions:
      d=region_2024_decomposition(region)
      for year in years:
        direct=grid_fn(region,year)
        add=upstream_for_direct(region,direct)
        rows.append({'region':region,'year':year,'grid_generation_direct_gco2e_kwh':direct,
        'electricity_fuel_upstream_gco2e_kwh':add,'electricity_WTW_gco2e_kwh':direct+add,
        'fossil_WTP_over_direct_ratio':d['fossil_wtp_over_direct_ratio'],
        'nuclear_fuel_upstream_anchor_g_kwh':d['nuclear_upstream_g_per_kwh'],
        'coal_direct_fraction_proxy':d['coal_direct_fraction'],
        'gas_direct_fraction_proxy':d['gas_direct_fraction'],
        'oil_direct_fraction_proxy':d['oil_direct_fraction'],
        'region_data_status':d['assumption']})
    return rows
