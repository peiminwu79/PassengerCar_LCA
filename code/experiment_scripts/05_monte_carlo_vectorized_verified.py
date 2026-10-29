"""10,000 real-stock Monte Carlo draws with exact array-equivalent policy model.
No image creation. Validate vectorized formulas against the single-source core
policy_model.simulate before writing numerical results.
"""
from pathlib import Path
import sys,argparse
import numpy as np,pandas as pd
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'modules'))
import policy_model as PM
import revision_engine as EF
import electricity_wtp as EW
RANGES={
 'V2G':{'reduction':(.05,.15,.25)},
 'Battery Charging':{'improvement':(.05,.12,.20)},
 'EV Subsidy':{'decay_rate':(.05,.10,.20)},
 'Tax Incentive':{'decay_rate':(.02,.05,.10)},
 'CAFC Credit':{'slope1':(.003,.005,.008),'slope2':(.006,.010,.015),'mfg_red':(.02,.05,.08)},
 'NEV Credit':{'increment':(.02,.03,.04),'cap':(.50,.60,.70),'compliance':(.70,.80,.90)},
 'Grid Decarb':{'target_year_sh':(2040,2045,2050),'target_year_ny':(2030,2035,2040)},
 'Charging Station':{'rate1':(.005,.010,.015),'rate2':(.002,.005,.008),'cap':(.25,.35,.45)},
}
def pert(rng,low,mode,high,size):
    if not low<=mode<=high:raise ValueError('Unordered PERT parameters')
    if low==high:return np.full(size,low)
    return low+(high-low)*rng.beta(1+4*(mode-low)/(high-low),1+4*(high-mode)/(high-low),size)

def evaluate(d,city,year,policy,uf,upstream,pars,power_upstream=None):
    """Result is per draw in Mt CO2e. Equivalence tests compare to simulate.
    """
    x=d[(d.city==city)&(d.year==year)].sort_values('county')
    if len(x)==0:raise ValueError('Missing city/year')
    n=len(uf);m=len(x);shape=(n,1)
    if power_upstream is None:power_upstream=np.ones(n)
    icev=x.ICEV.to_numpy()[None,:].repeat(n,axis=0)
    bev=x.BEV.to_numpy()[None,:].repeat(n,axis=0)
    phev=x.PHEV.to_numpy()[None,:].repeat(n,axis=0)
    stock_total=icev+bev+phev
    vkt=x.VKT_reference.to_numpy()[None,:].repeat(n,axis=0)
    gas_ttw=x.TTW_gkm.to_numpy()[None,:]
    gas_wtp=x.WTP_gkm.to_numpy()[None,:]*upstream[:,None]
    gas=gas_ttw+gas_wtp
    elec=(x.grid_average.to_numpy()[None,:]+power_upstream[:,None]*x.grid_upstream.to_numpy()[None,:])*EF.BEV_KWH_PER_KM
    red=np.zeros((n,1))
    dt=year-2024
    if policy=='V2G':
        red=pars['reduction'][:,None] if city=='SH' and year>=2028 else red
    elif policy=='Battery Charging':
        red=pars['improvement'][:,None]*np.clip(dt/11,0,1)
    elif policy in ('EV Subsidy','Tax Incentive'):
        if policy=='EV Subsidy' and city=='NYMA':raise ValueError('Not applicable')
        intensity=.25 if policy=='EV Subsidy' else .20
        cap=.6 if policy=='EV Subsidy' else .5
        multipliers={'central':.5,'peri':1,'suburban':1.5} if policy=='EV Subsidy' else {'central':.6,'peri':1,'suburban':1.4}
        mult=x.zone.map(multipliers).to_numpy()[None,:]
        factor=np.clip(intensity*(1-pars['decay_rate'][:,None])**dt,0,cap)*mult
        moved=icev*factor
        icev=icev-moved
        frac=.7 if policy=='EV Subsidy' else .65
        bev=bev+moved*frac;phev=phev+moved*(1-frac)
        vkt=vkt*(1.01 if policy=='EV Subsidy' else 1.005)
    elif policy=='NEV Credit':
        ptarget=np.minimum(pars['cap'][:,None],.1+pars['increment'][:,None]*dt)
        share=np.divide(bev+phev,stock_total,out=np.zeros_like(stock_total),where=stock_total>0)
        moved=stock_total*np.maximum(0,ptarget-share)*pars['compliance'][:,None]
        moved=np.minimum(moved,icev)
        icev=icev-moved;bev=bev+.7*moved;phev=phev+.3*moved
    elif policy=='Charging Station':
        f=np.where(year<=2024,.05, np.where(year<=2030,
            .05+pars['rate1'][:,None]*dt,
            .05+pars['rate1'][:,None]*6+pars['rate2'][:,None]*(year-2030)))
        factor=np.minimum(pars['cap'][:,None],f)*x.zone.map({'central':1.2,'peri':1.,'suburban':.7}).to_numpy()[None,:]
        moved=icev*factor;icev=icev-moved;bev=bev+.8*moved;phev=phev+.2*moved
        vkt=vkt*1.015
    elif policy=='Grid Decarb':
        ty_key='target_year_sh' if city=='SH' else 'target_year_ny'
        ty=pars[ty_key].astype(int)[:,None]
        start=np.array([EF.grid_ci(city,2024,c) for c in x.county],dtype=float)[None,:]
        if city=='SH':
            goal=np.full((1,m),20.0*(1+EF.SH_GENERATION_NONCO2_OVER_CO2))
            yrend=ty
        else:
            r=np.array([EF.nyma_subregion(c) for c in x.county]);nj=(r=='RFCE')[None,:]
            yrend=np.where(nj,2050+(ty-2040),ty)
            goal=np.where(nj,np.array([EF.grid_ci(city,2060,c) for c in x.county])[None,:],0.)
        frac=np.clip(dt/(yrend-2024),0,1)
        direct=(start+(goal-start)*frac)
        # Relative fossil-fuel WTP follows the direct grid-policy electricity
        # pathway; uranium fuel-cycle remains the same anchored supply share.
        ratio=np.array([EW.region_2024_decomposition(g)['fossil_wtp_over_direct_ratio'] for g in x.grid_region])[None,:]
        uranium=np.array([EW.region_2024_decomposition(g)['nuclear_upstream_g_per_kwh'] for g in x.grid_region])[None,:]
        elec=(direct+power_upstream[:,None]*(direct*ratio+uranium))*EF.BEV_KWH_PER_KM
    ee=elec*(1-red)
    mfg_i=EF.MFG_REC_GCO2EQ_PER_KM['ICEV']
    gas_i=gas
    if policy=='CAFC Credit':
        extra=pars['slope1'][:,None]*min(dt,11)+pars['slope2'][:,None]*max(dt-11,0)
        gas_i=gas*(1-extra)
        mfg_i=mfg_i*(1-pars['mfg_red'][:,None]*np.clip(dt/10,0,1))
    ef_icev=gas_i+mfg_i
    ef_bev=ee+EF.MFG_REC_GCO2EQ_PER_KM['BEV']
    ef_phev=(1-uf[:,None])*gas+uf[:,None]*ee+EF.MFG_REC_GCO2EQ_PER_KM['PHEV']
    return ((icev*ef_icev+bev*ef_bev+phev*ef_phev)*vkt).sum(axis=1)/1e12

def validation(d):
    # Deterministic cross-check of array batch values against original core
    # implementation across every policy, year, region.
    rng=np.random.default_rng(73)
    errs=[]
    for city in ['SH','NYMA']:
      for year in [2024,2030,2050]:
       active=['Reference']+[p for p in PM.POLICIES if city=='SH' or p not in ('V2G','EV Subsidy')]
       for pol in active:
        n=4;uf=rng.uniform(.4,.6,n);up=rng.uniform(.8,1.2,n);power_up=rng.uniform(.7,1.3,n)
        params={key:pert(rng,*v,n) for key,v in RANGES.get(pol,{}).items()}
        a=evaluate(d,city,year,pol,uf,up,params,power_up)
        for j in range(n):
          b=PM.simulate(d,city,pol,params={k:float(v[j]) for k,v in params.items()},
                        uf=float(uf[j]),upstream_scale=float(up[j]),power_upstream_scale=float(power_up[j]),year_filter=[year]).total_ton.iat[0]
          err=abs(a[j]-b)
          errs.append({'city':city,'year':year,'policy':pol,'batch_Mt':a[j], 'core_Mt':b,'abs_error_Mt':err})
          if not np.isclose(a[j],b,rtol=1e-10,atol=1e-9):
              raise AssertionError(f'MC mismatch {city}/{year}/{pol}: array={a[j]} core={b}')
    return pd.DataFrame(errs)

def run(d,out,draws=10000,seed=20261007):
    if draws<1:raise ValueError('draw count must be positive')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    validation(d).to_csv(out/'QA_monte_carlo_core_equivalence.csv',index=False)
    rng=np.random.default_rng(seed)
    uf=pert(rng,.4,.5,.6,draws)
    upstream=pert(rng,.8,1.,1.2,draws)
    power_upstream=pert(rng,.7,1.,1.3,draws)
    records=[]
    for city in ('SH','NYMA'):
      active=[p for p in PM.POLICIES if city=='SH' or p not in ('V2G','EV Subsidy')]
      draws_policy={p:{name:pert(rng,*v,draws) for name,v in RANGES[p].items()} for p in active}
      for year in (2030,2050):
        ref=evaluate(d,city,year,'Reference',uf,upstream,{},power_upstream)
        for pol in active:
          vals=evaluate(d,city,year,pol,uf,upstream,draws_policy[pol],power_upstream)
          red=100*(ref-vals)/ref
          records.append(pd.DataFrame({'draw':np.arange(draws),'city':city,'year':year,'policy':pol,
                        'UF':uf,'gasoline_upstream_multiplier':upstream,'electricity_fuel_upstream_multiplier':power_upstream,'reference_Mt':ref,'policy_Mt':vals,'reduction_pct':red}))
    res=pd.concat(records,ignore_index=True)
    res.to_csv(out/'SI_MC_10000_draws.csv',index=False,float_format='%.11g')
    summary=res.groupby(['city','year','policy']).reduction_pct.agg(
      median='median',p05=lambda v:v.quantile(.05),p95=lambda v:v.quantile(.95),
      prob_reduction=lambda v:(v>0).mean(),prob_rebound=lambda v:(v<0).mean()).reset_index()
    summary.to_csv(out/'SI_MC_median_P05_P95.csv',index=False)
    # Rankings: pay fractional credit for tied maxima, not arbitrary order.
    res['max_value']=res.groupby(['city','year','draw']).reduction_pct.transform('max')
    res['is_max']=np.isclose(res.reduction_pct,res.max_value,rtol=0,atol=1e-10)
    res['winners_count']=res.groupby(['city','year','draw']).is_max.transform('sum')
    res['win_share']=np.where(res.is_max,1/res.winners_count,0.)
    rank=res.groupby(['city','year','policy'],as_index=False).win_share.mean()
    rank.to_csv(out/'SI_MC_policy_rank1_probability.csv',index=False)
    assert np.allclose(rank.groupby(['city','year']).win_share.sum().to_numpy(),1.0)
    # SI statement caution: PERT based on original assumed Low/Medium/High ranges,
    # independent policy-specific response params: NOT empirically calibrated CI.
    return summary,rank
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser()
 parser.add_argument('--sh',required=True);parser.add_argument('--ny',required=True)
 parser.add_argument('--out',default='results');parser.add_argument('--draws',type=int,default=10000)
 args=parser.parse_args()
 st=PM.load_stocks(args.sh,args.ny)
 ny=st[st.city=='NYMA'].copy()
 for c in ['BEV','PHEV']:
    den=ny[['ICEV','BEV','PHEV']].sum(axis=1)
    s=ny[c]/den
    if (s.groupby([ny.county,ny.year]).agg(lambda x:x.max()-x.min())>1e-9).any():
        raise ValueError('Cannot losslessly aggregate tract stocks: shares differ')
 agg=ny.groupby(['city','county','zone','year'],as_index=False)[['ICEV','BEV','PHEV']].sum()
 agg['region_id']=agg.county
 sh=st[st.city=='SH']; st=pd.concat([sh,agg[sh.columns]],ignore_index=True)
 d=PM.prepare(st)
 q,r=run(d,args.out,args.draws)
 print('Done. All Monte Carlo batches equivalence-tested against policy_model:',len(q),'summaries',len(r),'ranking rows')
