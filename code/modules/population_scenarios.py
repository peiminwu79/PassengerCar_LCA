"""Independent population denominators for manuscript Fig. 4a; no stock regressions edited.

Shanghai: observed 2020–2024 residents, 2024-2035 interpolated city target of 25 million
and thereafter 25 million CENTRAL *scenario*, district shares follow bounded 2020–2024
log-linear trends with exponential relaxation. Plan is a population SCALE CONSTRAINT,
not a demographic forecast. 2024 observation never overwritten.
NYMA: population anchors from original SI Table 7 with yearly linear interpolation.
No plotting. Sources and assumptions live in code/data_inputs/.
"""
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1]
SH_INPUT=HERE/'data_inputs/SH_official_district_population_2020_2024.csv'
NY_INPUT=HERE/'data_inputs/NYMA_county_population_anchors_original_SI_Table7.csv'
YEAR0=2024
CITY_2024=24_802_600  # official sum; 24.8026 million
CITY_2035_CENTRAL=25_000_000 # Shanghai Master Plan 2017–2035 guideline, scenario anchor
TAU_BASE=8.0           # relaxation e-folding years, analyst scenario assumption
G_CLIP_BASE=.03         # maximum absolute district log-share growth (per annum), assumption

def official_sh():
    df=pd.read_csv(SH_INPUT)
    d=df.pivot(index='district',columns='year',values='population_persons').sort_index()
    if d.shape!=(16,5) or list(d.columns)!=list(range(2020,2025)):
        raise AssertionError('Shanghai official 2020–2024 district population input mismatch')
    if not np.isclose(d[2024].sum(),CITY_2024,atol=1):raise AssertionError('2024 official city total')
    return d

def annual_log_trends(d,g_clip=G_CLIP_BASE):
    yrs=np.arange(2020,2025,dtype=float)
    x=yrs-yrs.mean()
    logpop=np.log(d.loc[:,2020:2024].to_numpy(dtype=float))
    slopes=logpop@x/(x@x)
    return pd.Series(np.clip(slopes,-g_clip,g_clip),index=d.index,name='annual_log_trend_clipped')

def city_scenario_total(year,city_target_2035=CITY_2035_CENTRAL,city_target_2050=CITY_2035_CENTRAL):
    if year<YEAR0:raise ValueError('Only future scenario years accepted')
    if year<=2035:
        return CITY_2024+(city_target_2035-CITY_2024)*(year-2024)/11
    if year<=2050:
        return city_target_2035+(city_target_2050-city_target_2035)*(year-2035)/15
    return city_target_2050

def project_sh(years=range(2024,2061),tau=TAU_BASE,g_clip=G_CLIP_BASE,
               city_target_2035=CITY_2035_CENTRAL,city_target_2050=CITY_2035_CENTRAL,scenario='Central'):
    if tau<=0 or g_clip<=0:raise ValueError('Invalid scenario parameters')
    d=official_sh()
    g=annual_log_trends(d,g_clip)
    rows=[]
    for year in years:
        if year<2024:raise ValueError('Projection year before 2024')
        if year==2024:
            p=d[2024].astype(float)
        else:
            dt=year-2024
            attenuation=tau*(1-np.exp(-dt/tau))
            raw=d[2024].to_numpy(float)*np.exp(g.to_numpy()*attenuation)
            total=city_scenario_total(year,city_target_2035,city_target_2050)
            p=pd.Series(total*raw/raw.sum(),index=d.index)
        for district,pop in p.items():
            rows.append({'city':'SH','county':district,'year':year,'population':float(pop),
                'denominator_status':'OFFICIAL_2024' if year==2024 else 'SCENARIO_PROJECTED',
                'population_model':'OFFICIAL_2020_2024_LOG_TREND_SHRINKED_CITY_CONSTRAINED',
                'population_scenario':scenario,'tau_years':tau,'annual_log_trend_cap':g_clip,
                'city_target_2035':city_target_2035,'city_target_2050':city_target_2050,
                'district_historical_log_trend':float(g[district]),
                'source':'Shanghai Statistical Yearbooks 2021–2025 Tables 2.2 + Shanghai Master Plan 2017–2035 city total target (scenario)'} )
    return pd.DataFrame(rows)

def project_ny(years=range(2024,2061)):
    df=pd.read_csv(NY_INPUT,dtype={'FIPS':str}); df.FIPS=df.FIPS.str.zfill(5)
    if df.FIPS.nunique()!=22:raise AssertionError('NYMA 22-county source')
    rows=[]
    for county,g in df.groupby('FIPS'):
        g=g.sort_values('year')
        for year in years:
            pop=float(np.interp(year,g.year,g.population_persons))
            rows.append({'city':'NYMA','county':county,'year':year,'population':pop,
                'denominator_status':'ORIGINAL_SI_TABLE7_ANCHOR' if year in set(g.year) else 'ORIGINAL_SI_INTERPOLATED',
                'population_model':'ORIGINAL_SI_TABLE7_NYMTC_NJTPA_DEFAULT',
                'population_scenario':'Original_SI','tau_years':np.nan,'annual_log_trend_cap':np.nan,
                'city_target_2035':np.nan,'city_target_2050':np.nan,
                'district_historical_log_trend':np.nan,
                'source':'Original Supplementary Information Table 7 (forecasts, not observed census figures)'})
    return pd.DataFrame(rows)

def population_for_all(years=range(2024,2061)):
    frame=pd.concat([project_sh(years),project_ny(years)],ignore_index=True)
    if frame.groupby(['city','county','year']).size().max()!=1 or (frame.population<=0).any():
        raise AssertionError('Population coverage or positivity')
    return frame

if __name__=='__main__':
    sh=project_sh()
    print(sh.groupby('year').population.sum().loc[[2024,2030,2035,2050,2060]])
