"""WTW stage attribution and energy-supply composition stress tests. NO images.

Uses exactly the same previously calculated 22-county and 16-district policy
outputs. Does not alter the author's stock or PCA/Poisson regression model.
"""
import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'modules'))
import electricity_wtp as EW
import revision_engine as EF

STAGES=['ICEV_TTW_Mt','ICEV_WTP_Mt','PHEV_TTW_Mt','PHEV_WTP_Mt',
    'BEV_power_generation_Mt','BEV_electricity_fuel_WTP_Mt',
    'PHEV_power_generation_Mt','PHEV_electricity_fuel_WTP_Mt',
    'ICEV_manufacturing_recycling_Mt','BEV_manufacturing_recycling_Mt',
    'PHEV_manufacturing_recycling_Mt']

def main(root):
    root=Path(root)
    q=pd.read_csv(root/'Manuscript_Fig4_spatial_annual_2024_2060.csv',dtype={'county':str})
    for k in STAGES:
        assert k in q.columns,k
    q['recovered_Mt']=q[STAGES].sum(axis=1)
    assert np.allclose(q.recovered_Mt,q.total_ton,atol=1e-8,rtol=1e-9), (q.recovered_Mt-q.total_ton).abs().max()
    q.groupby(['city','year','policy'],as_index=False)[STAGES+['total_ton']].sum().to_csv(root/'SI_WTW_emission_stages_annual_by_powertrain.csv',index=False)
    q[['city','county','region_id','year','policy',*STAGES,'total_ton']].to_csv(root/'SI_WTW_emission_stages_spatial.csv',index=False)
    # Country-specific coal direct CO2 share in 2024 Shanghai electricity is
    # NOT OBSERVED: 70%, 90% reference, 100% are alternative assumptions.
    # Recovers exactly the EV electric-side difference without re-running the
    # unrelated gasoline, manufacturing or policy adoption sub-models.
    sh=q[q.city=='SH'].copy()
    direct=sh.grid_WTW_g_per_kWh-sh.grid_upstream_g_per_kWh
    baseline_frac=EW.SH_COAL_DIRECT_CO2_SHARE_ASSUMED
    oldr=baseline_frac*EW.SH_COAL_UPSTREAM_TO_COMBUSTION+(1-baseline_frac)*EW.SH_GAS_UPSTREAM_TO_COMBUSTION
    assert abs(oldr-EW.region_2024_decomposition('SH')['fossil_wtp_over_direct_ratio'])<1e-12
    tests=[]
    for coal_frac in (.70,.90,1.00):
        ratio=coal_frac*EW.SH_COAL_UPSTREAM_TO_COMBUSTION+(1-coal_frac)*EW.SH_GAS_UPSTREAM_TO_COMBUSTION
        direct_co2=direct.to_numpy()/(1+EF.SH_GENERATION_NONCO2_OVER_CO2)
        adjusted_nonco2_ratio=coal_frac*EF.SH_COAL_NONCO2_RATIO+(1-coal_frac)*EF.SH_GAS_NONCO2_RATIO
        adjusted_direct=direct_co2*(1+adjusted_nonco2_ratio)
        newup=adjusted_direct*ratio+EW.SH_NUCLEAR_GENERATION_SHARE_PROXY*EW.NUCLEAR_UPSTREAM_FUEL_CYCLE_GPKWH
        oldup=sh.grid_upstream_g_per_kWh.to_numpy()
        wtp_change=((newup-oldup)+(adjusted_direct-direct.to_numpy()))*sh.charging_kWh.to_numpy()/1e12
        a=sh[['city','year','policy','total_ton','charging_kWh']].copy()
        a['electricity_upstream_coal_direct_fraction_assumed']=coal_frac
        a['reference_sh_coal_direct_fraction']=baseline_frac
        a['electricity_wtp_adjustment_Mt']=wtp_change
        a['LCA_under_fuel_mix_proxy_Mt']=sh.total_ton.to_numpy()+wtp_change
        tests.append(a)
    t=pd.concat(tests,ignore_index=True)
    t=t.groupby(['city','year','policy','electricity_upstream_coal_direct_fraction_assumed',
        'reference_sh_coal_direct_fraction'],as_index=False)[['total_ton','electricity_wtp_adjustment_Mt','LCA_under_fuel_mix_proxy_Mt']].sum()
    t.to_csv(root/'SI_SH_electricity_fuel_upstream_coal_gas_proxy_sensitivity.csv',index=False)
    # Clear contrast of 2024 source-generation boundaries and WTW result.
    z=pd.read_csv(root/'SI_electricity_fuel_cycle_factors_by_grid_2024_2060.csv')
    z['fuel_WTP_pct_direct']=100*z.electricity_fuel_upstream_gco2e_kwh/z.grid_generation_direct_gco2e_kwh.replace(0,np.nan)
    z.to_csv(root/'SI_electricity_fuel_cycle_factors_by_grid_2024_2060.csv',index=False)
    pd.DataFrame([{
      'test':'emissions_exact_stage_balance_all_cities_policies_years',
      'max_abs_error_Mt':(q.recovered_Mt-q.total_ton).abs().max(),'status':'PASS'},
      {'test':'coal_share_reference_is_identical_to_WTW_main',
      'max_abs_error_Mt':float(t[t.electricity_upstream_coal_direct_fraction_assumed==baseline_frac].electricity_wtp_adjustment_Mt.abs().max()),
      'status':'PASS'}]).to_csv(root/'QA_WTW_mass_balance_and_fuel_proxy.csv',index=False)
    print('WTW stage attribution, 3 Shanghai upstream coal/gas proxy cases, mass-balance QA complete. No plots.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',required=True)
    a=p.parse_args();main(a.results)
