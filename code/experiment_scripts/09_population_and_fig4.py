"""Fig. 4a GIS data: independent district/county year-specific population, WTW numerators.
Does not render maps or modify any existing plotting style. All outputs from verified author stocks.
"""
from pathlib import Path
import sys,argparse
import numpy as np
import pandas as pd
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'modules'))
import population_scenarios as PS
import policy_model as PM

AREA_DIMS=('city','county','year')
TYPES=('ICEV','BEV','PHEV','total')

def calculate_percap(spatial,denominator):
    sums=spatial.groupby(['city','county','year','policy'],as_index=False)[[t+'_ton' for t in TYPES]].sum()
    joined=sums.merge(denominator,on=list(AREA_DIMS),how='left',validate='many_to_one',indicator=True)
    if not joined._merge.eq('both').all():raise ValueError('Missing population denominator')
    joined=joined.drop(columns='_merge')
    # Legacy *_ton column is ACTUALLY Mt CO2e; multiply by 10^9 for kg CO2e.
    for t in TYPES:
        joined[f'{t}_kgCO2eq_per_capita']=joined[t+'_ton']*1e9/joined.population
        if not np.allclose(joined[f'{t}_kgCO2eq_per_capita']*joined.population/1e9, joined[t+'_ton'],rtol=1e-12,atol=1e-12):
            raise AssertionError('Per capita does not invert to district total')
    return joined

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--sh',required=True);p.add_argument('--ny',required=True)
    p.add_argument('--spatial',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();out=Path(a.out);out.mkdir(exist_ok=True,parents=True)
    stock=PM.load_stocks(a.sh,a.ny)
    shset=set(stock.loc[stock.city.eq('SH'),'county'].unique())
    nyset=set(stock.loc[stock.city.eq('NYMA'),'county'].unique())
    if shset!=set(PS.official_sh().index) or nyset!=set(PS.project_ny().county.unique()):
        raise AssertionError('Population stock geography mismatch')
    pop=PS.population_for_all()
    pop.to_csv(out/'SI_population_denominators_2024_2060.csv',index=False)
    shpop=pop.query('city == "SH"').copy()
    shpop.to_csv(out/'SI_SH_population_projection_district_2024_2060.csv',index=False)
    diagnostics=shpop.groupby('year',as_index=False).agg(city_population=('population','sum'))
    diagnostics['scenario_description']='official 2024 / 2025–2060 projection, trend-shrinkage, Shanghai 2035 city planning ceiling scenario'
    diagnostics.to_csv(out/'QA_SH_city_population_trajectory.csv',index=False)
    spatial=pd.read_csv(a.spatial,dtype={'county':str});pc=calculate_percap(spatial,pop)
    pc.to_csv(out/'Manuscript_Fig4_county_district_percapita_2024_2060.csv',index=False)
    # Only 2030/2050 for ArcGIS, all applicable policies, all original GIS styling retained outside Python.
    pc[pc.year.isin([2030,2050])].to_csv(out/'Manuscript_Fig4a_ARCGIS_join_2030_2050.csv',index=False)
    # Population uncertainty scenarios at identical WTW emissions (avoid rerunning vehicle stock model).
    alternatives=[('City2050_24M_tau8',8,.03,25_000_000,24_000_000),
                  ('City2050_24p5M_tau8',8,.03,25_000_000,24_500_000),
                  ('City2050_25M_tau5',5,.03,25_000_000,25_000_000),
                  ('City2050_25M_tau12',12,.03,25_000_000,25_000_000),
                  ('City2050_25M_cap2pct',8,.02,25_000_000,25_000_000)]
    exposure=pc[(pc.city=='SH')&(pc.year.isin([2030,2050]))].copy()
    pieces=[]
    for name,tau,clip,city35,city50 in alternatives:
        p_alt=PS.project_sh([2030,2050],tau=tau,g_clip=clip,city_target_2035=city35,city_target_2050=city50,scenario=name)
        alt=exposure.drop(columns=[c for c in p_alt.columns if c in exposure.columns and c not in AREA_DIMS]).merge(
            p_alt,on=list(AREA_DIMS),validate='many_to_one',suffixes=('','_alt'))
        centre=exposure[list(AREA_DIMS)+['policy','population','total_kgCO2eq_per_capita']].rename(columns={'population':'central_population','total_kgCO2eq_per_capita':'central_total_kg_per_person'})
        alt=alt.merge(centre,on=list(AREA_DIMS)+['policy'],validate='many_to_one')
        alt['sensitivity_kg_per_person']=alt.total_ton*1e9/alt.population
        alt['change_vs_central_pct']=100*(alt.sensitivity_kg_per_person/alt.central_total_kg_per_person-1)
        pieces.append(alt[list(AREA_DIMS)+['policy','population_scenario','population','central_population','central_total_kg_per_person','sensitivity_kg_per_person','change_vs_central_pct']])
    pd.concat(pieces,ignore_index=True).to_csv(out/'SI_SH_population_Fig4a_sensitivity_2030_2050.csv',index=False)
    ref=spatial.groupby(['city','county','year','policy'],as_index=False)[['total_ton']].sum()
    refval=ref.query('policy == "Reference"')[list(AREA_DIMS)+['total_ton']].rename(columns={'total_ton':'reference_Mt'})
    d=ref.merge(refval,on=list(AREA_DIMS),validate='many_to_one')
    d['reduction_pct']=100*(d.reference_Mt-d.total_ton)/d.reference_Mt
    d.to_csv(out/'SI_spatial_policy_percentage_change_2024_2060.csv',index=False)
    print('Fig4a year-specific independent population and ArcGIS tables complete; NO IMAGES GENERATED.')
if __name__=='__main__':main()
