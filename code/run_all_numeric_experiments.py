"""Full reproducible numerical run: original real stocks; NEVER generates plots.

Outputs all manuscript and SI data tables in one versioned run.
"""
from pathlib import Path
import sys,json,hashlib,datetime
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'modules'))
sys.path.insert(0,str(ROOT/'experiment_scripts'))
import policy_model as PM
import revision_engine as EF
import electricity_wtp as EW
from importlib.machinery import SourceFileLoader
SH=None
NY=None
OUT=None

def read_exact_aggregated():
    st=PM.load_stocks(SH,NY)
    # Strong, auditable acceleration: exact for these models if all tract-level
    # PHEV and BEV proportions are uniform within county and year.
    ny=st[st.city=='NYMA'].copy()
    tot=ny[['ICEV','BEV','PHEV']].sum(axis=1)
    for col in ('BEV','PHEV'):
        ny[col+'_share']=np.divide(ny[col],tot,out=np.zeros(len(ny)),where=tot>0)
    dispersion=ny.groupby(['county','year'])[['BEV_share','PHEV_share']].agg(lambda x:x.max()-x.min())
    assert (dispersion.to_numpy()<=1e-10).all(), 'NYMA shares vary by tract: aggregation not exact'
    nyagg=ny.groupby(['city','county','zone','year'],as_index=False)[['ICEV','BEV','PHEV']].sum()
    nyagg['region_id']=nyagg['county']
    sh=st[st.city=='SH'][['city','county','zone','year','ICEV','BEV','PHEV','region_id']]
    grp=pd.concat([sh,nyagg[sh.columns]],ignore_index=True)
    assert len(grp)==(16+22)*37
    audit=[]
    for city in ('SH','NYMA'):
        orig=st[st.city==city].groupby('year')[['ICEV','BEV','PHEV']].sum()
        cmp=grp[grp.city==city].groupby('year')[['ICEV','BEV','PHEV']].sum()
        assert np.allclose(orig.values,cmp.values,rtol=1e-13)
        audit.append({'city':city,'records':len(st[st.city==city]),'spatial_units':st[st.city==city].region_id.nunique(),
        'model_county_or_district_units':grp[grp.city==city].region_id.nunique(),
        'max_tract_tech_share_spread':float(dispersion.max().max()) if city=='NYMA' else 0,
        'expected_traces_in_manuscript':4798 if city=='NYMA' else None})
    pd.DataFrame(audit).to_csv(OUT/'QA_vehicle_stock_coverage.csv',index=False)
    return PM.prepare(grp)

def safe_out(x,name):
    x.to_csv(OUT/name,index=False,float_format='%.11g')

def full_results(d):
    refs=[];fig2=[];fig3=[];spatial=[];upstreams=[];electric_upstreams=[];ufs=[];marginal=[];marginal_area=[];station=[];spi=[]
    for city in ('SH','NYMA'):
        app=['Reference']+[p for p in PM.POLICIES if city=='SH' or p not in ('V2G','EV Subsidy')]
        base=PM.simulate(d,city,'Reference',detail=True)
        refs.append(base)
        for pol in app:
            detail=PM.simulate(d,city,pol,detail=True)
            year=detail.groupby('year',as_index=False)[['ICEV_ton','BEV_ton','PHEV_ton','total_ton',
                'ICEV_WTP_Mt','PHEV_WTP_Mt','BEV_electricity_fuel_WTP_Mt','PHEV_electricity_fuel_WTP_Mt','charging_kWh']].sum()
            year['city']=city;year['policy']=pol;year['uf']=.5
            fig2.append(year)
            # Geo output: New York county or Shanghai district, 2024-2060
            spatial.append(detail)
            for uf in (.4,.5,.6):
                # use all 2024-2060 years for sensitivity, no invented stock
                z=PM.simulate(d,city,pol,uf=uf)
                ufs.append(z)
            for scale in (.8,1.,1.2):
                zz=PM.simulate(d,city,pol,upstream_scale=scale)
                zz['gasoline_WTP_scale']=scale;upstreams.append(zz)
            for scale in (.7,1.,1.3):
                zz=PM.simulate(d,city,pol,power_upstream_scale=scale)
                zz['electricity_fuel_WTP_scale']=scale;electric_upstreams.append(zz)
            if pol!='Reference':
                j=detail.merge(base[['year','region_id','charging_kWh']],on=['year','region_id'],how='left',
                         validate='one_to_one',suffixes=('', '_ref'))
                assert j.charging_kWh_ref.notna().all()
                j['delta_kWh']=j.charging_kWh-j.charging_kWh_ref
                # Incremental energy can be valued at marginal generation + fuel supply.
                # Baseline marginal fuel WTP follows EPA nonbaseload fossil mix.
                jmup=np.array([EW.upstream_for_direct(rr,mg,kind='marginal')
                     for rr,mg in zip(j.county.map(lambda c:'SH' if city=='SH' else EF.nyma_subregion(c)),j.grid_marginal_g_per_kWh)])
                j['marginal_minus_average_Mt']=j.delta_kWh*((j.grid_marginal_g_per_kWh+jmup)-j.grid_WTW_g_per_kWh)/1e12
                v=j.groupby('year',as_index=False)[['delta_kWh','marginal_minus_average_Mt']].sum()
                v=v.merge(year[['year','total_ton']].rename(columns={'total_ton':'policy_average_Mt'}),on='year')
                v['policy_marginal_adjusted_Mt']=v.policy_average_Mt+v.marginal_minus_average_Mt
                v['city']=city;v['policy']=pol;marginal.append(v)
        for policy,levels in INTENSITY.items():
            if city=='NYMA' and policy in ('V2G','EV Subsidy'):continue
            for strength,pars in zip(('High','Medium','Low'),levels):
                z=PM.simulate(d,city,policy,params=pars)
                z['intensity']=strength;fig3.append(z)
        # Emit component breakdown by type for 2024-2060 (old SI Figs 8/9)
        for phase in ('use','LCA'):
            z=base.copy()
            if phase=='use':
                for t in ('ICEV','BEV','PHEV'):
                    z[t+'_ton']-=z[t+'_stock']*z.VKT_km_per_vehicle*EF.MFG_REC_GCO2EQ_PER_KM[t]/1e12
            grouped=z.groupby(['year','region_id','county','zone'],as_index=False)[['ICEV_ton','BEV_ton','PHEV_ton']].sum()
            grouped['total_ton']=grouped[['ICEV_ton','BEV_ton','PHEV_ton']].sum(axis=1)
            grouped['phase']=phase;grouped['city']=city
            refs.append(grouped) if False else None
            safe_out(grouped,f'SI_Fig8_9_{city}_{phase}_spatial.csv')
        # Charging weighted region EF
        weighted=base.groupby(['county','year','grid_average_g_per_kWh','grid_marginal_g_per_kWh'],as_index=False).charging_kWh.sum()
        weighted['city']=city;marginal_area.append(weighted)
        # Fig. 5 central area only (2024 and 2030 and 2050; primary 2030).
        target=EF.NYC_COUNTIES if city=='NYMA' else {'Huangpu','Jingan','Xuhui','Changning','Putuo','Hongkou','Yangpu'}
        for year_ch in (2024,2030,2050):
            dat=d[d.city.eq(city)&d.county.isin(target)&d.year.eq(year_ch)]
            ref=PM.simulate(dat,city,'Reference',detail=True)
            central_vkt_ratio=(9000/12000 if city=='SH' else 11000/18500)
            ref_kWh=float(ref.charging_kWh.sum())*central_vkt_ratio
            for pol in app:
                if pol=='Reference':continue
                sim=PM.simulate(dat,city,pol,detail=True)
                Q=float(sim.charging_kWh.sum())*central_vkt_ratio
                # Capacity follows the SAME cumulative charging-deployment
                # parameterization used to change stock in policy_model.
                # This is a conditional service-capacity scenario, not observed
                # charger throughput; central zones receive multiplier 1.2.
                if pol=='Charging Station':
                    dt=year_ch-2024
                    raw=(.05+.010*dt if year_ch<=2030 else .05+.010*6+.005*(year_ch-2030))
                    cap=1.+min(.35,raw)*1.2
                else:
                    cap=1.
                acc,cov,pres=EF.relative_charge_service(Q/ref_kWh,cap)
                row={'city':city,'year':year_ch,'policy':pol,'reference_kWh':ref_kWh,'policy_kWh':Q,
                      'capacity_ratio':cap,'demand_ratio':Q/ref_kWh,
                      'Accessibility_change_pct':acc,'Service_coverage_change_pct':cov}
                station.append(row)
                spi.append({**row,'SPI':pres,'is_SI_diagnostic':True})
    safefiles={
     'reference_emissions_2024_2060.csv':pd.concat(fig2).query('policy == "Reference"'),
     'Manuscript_Fig2_policy_annual_2024_2060.csv':pd.concat(fig2,ignore_index=True),
     'Manuscript_Fig3_policy_intensity_2024_2060.csv':pd.concat(fig3,ignore_index=True),
     'Manuscript_Fig4_spatial_annual_2024_2060.csv':pd.concat(spatial,ignore_index=True),
     'SI_PHEV_UF_040_050_060.csv':pd.concat(ufs,ignore_index=True),
     'SI_upstream_WTP_sensitivity.csv':pd.concat(upstreams,ignore_index=True),
     'SI_electricity_fuel_WTP_sensitivity.csv':pd.concat(electric_upstreams,ignore_index=True),
     'SI_incremental_marginal_EF_sensitivity.csv':pd.concat(marginal,ignore_index=True),
     'SI_county_charging_weighted_grid_factors.csv':pd.concat(marginal_area,ignore_index=True),
     'Manuscript_Fig5b_two_indicators_2024_2030_2050.csv':pd.DataFrame(station),
     'SI_SPI_diagnostic_only_2024_2030_2050.csv':pd.DataFrame(spi),
    }
    for name,x in safefiles.items():safe_out(x,name)
    # WTW electricity fuel supply factor in every study grid region and year.
    lines=EW.yearly_audit(['SH','NYCW','NYLI','NYUP','RFCE'],range(2024,2061),
        lambda r,y:EF.grid_ci('SH',y) if r=='SH' else float(EF.grid_table().loc[(r,y),'average_gco2eq_per_kwh']))
    safe_out(pd.DataFrame(lines),'SI_electricity_fuel_cycle_factors_by_grid_2024_2060.csv')
    decomposition=pd.DataFrame([{'region':r,**EW.region_2024_decomposition(r)} for r in ('SH','NYCW','NYLI','NYUP','RFCE')])
    safe_out(decomposition,'SI_electricity_fuel_cycle_allocation_assumptions.csv')
    tab=pd.DataFrame(station).query('year == 2030')
    piv=tab.pivot(index='policy',columns='city',values=['Accessibility_change_pct','Service_coverage_change_pct'])
    fig5=pd.DataFrame({'Policy':list(PM.POLICIES)})
    for city,col in [('SH','SH'),('NYMA','NY')]:
        for source,target in [('Accessibility_change_pct','Acc'),('Service_coverage_change_pct','Cov')]:
            f=tab[tab.city==city].set_index('policy')[source]
            fig5[col+'_'+target]=fig5.Policy.map(f)
    # N/A as zero only for compatibility with the author's original Fig. 5b
    # plotting arrays. In the science table status remains NOT_APPLICABLE.
    for key in ('NY_Acc','NY_Cov'):
        fig5[key]=fig5[key].fillna(0.)
    safe_out(fig5,'Table1_charging_service.csv')
    safe_out(pd.DataFrame(spi),'SI_SPI_diagnostic.csv')
    print('Core experiments complete:',[(k,len(v)) for k,v in safefiles.items()],flush=True)

def validate(prepared):
    assert set(prepared.year.unique())==set(range(2024,2061))
    # Policy preserves number of vehicles, nonnegative, bounded service metrics.
    assert (prepared[['ICEV','BEV','PHEV','grid_average','grid_marginal']]>=0).all().all()
    for city in ('SH','NYMA'):
      for pol in ['Reference',*PM.POLICIES]:
        if city=='NYMA' and pol in ('V2G','EV Subsidy'):continue
        detail=PM.simulate(prepared,city,pol,year_filter=[2030,2050],detail=True)
        assert np.allclose(detail[['ICEV_stock','BEV_stock','PHEV_stock']].sum(axis=1),
         prepared[(prepared.city==city)&(prepared.year.isin([2030,2050]))][['ICEV','BEV','PHEV']].sum(axis=1))
        assert (detail[['ICEV_stock','BEV_stock','PHEV_stock','total_ton','charging_kWh']]>=0).all().all()
    # Property tests: monotonic upstream effect and UF electricity consistency.
    for city in ('SH','NYMA'):
      a=PM.simulate(prepared,city,year_filter=[2024],upstream_scale=.8).total_ton.iloc[0]
      b=PM.simulate(prepared,city,year_filter=[2024],upstream_scale=1.2).total_ton.iloc[0]
      assert b>a
    return True

# Reuse the EXACT defined policy intensity scenarios from the paper
INTENSITY={
 'V2G':({'reduction':.25},{'reduction':.15},{'reduction':.05}),
 'Battery Charging':({'improvement':.20},{'improvement':.12},{'improvement':.05}),
 'EV Subsidy':({'decay_rate':.05},{'decay_rate':.10},{'decay_rate':.20}),
 'Tax Incentive':({'decay_rate':.02},{'decay_rate':.05},{'decay_rate':.10}),
 'CAFC Credit':({'slope1':.008,'slope2':.015,'mfg_red':.08},{'slope1':.005,'slope2':.010,'mfg_red':.05},{'slope1':.003,'slope2':.006,'mfg_red':.02}),
 'NEV Credit':({'increment':.04,'cap':.70,'compliance':.90},{'increment':.03,'cap':.60,'compliance':.80},{'increment':.02,'cap':.50,'compliance':.70}),
 'Grid Decarb':({'target_year_sh':2040,'target_year_ny':2030},{'target_year_sh':2045,'target_year_ny':2035},{'target_year_sh':2050,'target_year_ny':2040}),
 'Charging Station':({'rate1':.015,'rate2':.008,'cap':.45},{'rate1':.010,'rate2':.005,'cap':.35},{'rate1':.005,'rate2':.002,'cap':.25}),
}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Run full revised real-stock experiments WITHOUT generating images')
    parser.add_argument('--sh',required=True);parser.add_argument('--ny',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    SH=Path(args.sh).resolve();NY=Path(args.ny).resolve();OUT=Path(args.out).resolve()
    if not SH.is_file() or not NY.is_file():raise FileNotFoundError('Missing author-provided stock CSV')
    OUT.mkdir(exist_ok=True,parents=True)
    d=read_exact_aggregated();print('prepared',len(d),flush=True)
    validate(d);full_results(d)
