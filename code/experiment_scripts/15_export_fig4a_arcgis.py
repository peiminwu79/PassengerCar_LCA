"""Extract finished WTW per-capita data with historical ArcGIS-friendly names; never plot."""
import sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'results/Manuscript_Fig4a_ARCGIS_join_2030_2050.csv'
OUT=ROOT/'results/ArcGIS_Fig4a_exports'
OUT.mkdir(exist_ok=True,parents=True)
SH_ALIAS={'Pudong':'Pudong New Area','Jingan':"Jing'an"}
NY_NAMES={'36061': 'Manhattan', '36047': 'Brooklyn', '36081': 'Queens', '36005': 'Bronx', '36085': 'Staten Island', '34017': 'Hudson', '34003': 'Bergen', '34031': 'Passaic', '34013': 'Essex', '34039': 'Union', '36119': 'Westchester', '36059': 'Nassau', '36087': 'Rockland', '36079': 'Putnam', '36103': 'Suffolk', '34023': 'Middlesex', '34035': 'Somerset', '34019': 'Hunterdon', '34027': 'Morris', '34037': 'Sussex', '34025': 'Monmouth', '34029': 'Ocean'}
POL={'Reference':'baseline','EV Subsidy':'subsidy','Tax Incentive':'tax','Charging Station':'station'}
COLS=['ICEV_kgCO2eq_per_capita','BEV_kgCO2eq_per_capita','PHEV_kgCO2eq_per_capita','total_kgCO2eq_per_capita']
d=pd.read_csv(SRC,dtype={'county':str})
assert d.year.isin([2030,2050]).all()
sh=d[d.city.eq('SH') & d.policy.isin(POL)].copy()
sh['region_id']=sh.county.replace(SH_ALIAS)
for (yr,policy),f in sh.groupby(['year','policy']):
    if len(f)!=16:raise ValueError('SH 16 districts required')
    f[['region_id','county','year','population']+COLS].to_csv(OUT/f'{yr}_SH_{POL[policy]}_per_capita.csv',index=False)
ny=d[d.city.eq('NYMA')].copy()
ny['FIPS']=ny.county.str.zfill(5);ny['DISTRICT']=ny.FIPS.map(NY_NAMES)
if ny.DISTRICT.isna().any():raise ValueError('NYMA county missing mapping')
for (yr,policy),f in ny.groupby(['year','policy']):
    if len(f)!=22:raise ValueError('NYMA 22 counties required')
    f[['FIPS','DISTRICT','year','population']+COLS].to_csv(OUT/f'NYMA_{policy.replace(" ","_")}_{yr}_per_capita.csv',index=False)
print('Fig4a ArcGIS WTW annual population join data generated; no imagery.')
