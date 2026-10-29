"""Recompute the ORIGINAL SI Fig. 10 / Table 12 one-factor-at-a-time
policy parameter sweep after upstream/grid/PHEV updates; no plotting.
"""
import sys,argparse
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'modules'))
import policy_model as PM
# Original Supplementary Table 12, 15 equally spaced points per parameter.
PARAMS={
 'EV Subsidy':('decay_rate',.02,.10,.30,('SH',)),
 'Tax Incentive':('decay_rate',.01,.05,.20,('SH','NYMA')),
 'CAFC Credit':('slope1',.001,.005,.015,('SH','NYMA')),
 'NEV Credit':('increment',.01,.03,.06,('SH','NYMA')),
 'Grid Decarb':('target_year_sh',2030,2045,2054,('SH',)),
 'Grid Decarb_NY':('target_year_ny',2030,2035,2040,('NYMA',)),
 'Charging Station':('rate1',.002,.010,.025,('SH','NYMA')),
}
def main():
 p=argparse.ArgumentParser();p.add_argument('--sh',required=True);p.add_argument('--ny',required=True);p.add_argument('--out',required=True)
 a=p.parse_args();out=Path(a.out);out.mkdir(exist_ok=True,parents=True)
 d=PM.load_stocks(a.sh,a.ny)
 ny=d[d.city=='NYMA'].copy()
 for t in ('BEV','PHEV'):
  den=ny[['ICEV','BEV','PHEV']].sum(axis=1)
  shares=ny[t]/den
  if (shares.groupby([ny.county,ny.year]).agg(lambda v: v.max()-v.min())>1e-9).any():
   raise ValueError('NYMA tract proportions not county-homogeneous')
 n=ny.groupby(['city','county','zone','year'],as_index=False)[['ICEV','BEV','PHEV']].sum();n['region_id']=n.county
 sh=d[d.city=='SH'];d=PM.prepare(pd.concat([sh,n[sh.columns]],ignore_index=True))
 records=[]
 for name,(param,lo,base,hi,applicable) in PARAMS.items():
  pol=name.replace('_NY','')
  for city in applicable:
   b=PM.simulate(d,city,'Reference',year_filter=[2050]).total_ton.iat[0]
   for i,val in enumerate(np.linspace(lo,hi,15)):
    new=PM.simulate(d,city,pol,params={param:val},year_filter=[2050]).total_ton.iat[0]
    records.append({'city':city,'policy':pol,'parameter':param,'point':i+1,
     'parameter_value':val,'normalized_x':(val-lo)/(hi-lo),
     'reference_Mt':b,'policy_Mt':new,'emission_reduction_pct':100*(b-new)/b,
     'source':'Original Supplementary Table 12: conditional OFAT Low/Medium/High range'})
 pd.DataFrame(records).to_csv(out/'SI_Fig10_updated_OFAT_15points_2050.csv',index=False)
 print('Completed',len(records),'original-SI OFAT points from author stock data; no plots')
if __name__=='__main__':main()
