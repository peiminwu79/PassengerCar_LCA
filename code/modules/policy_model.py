"""One computational pathway for ALL Shanghai/NYMA policy, LCA, sensitivity,
Monte Carlo, and existing-figure-data outputs.  No plots, no synthetic stocks.

Original policy response definitions: Emission_updated.ipynb, cell 0.
Minor differences from original: fuel upstream, spatial NYMA grid, correct PHEV
fuel/electric decomposition, parameterized SI Table 11, PHEV UF shared across
all modules.  Physical assumptions remain scenario assumptions, not causal estimates.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
import revision_engine as EF
import electricity_wtp as EW

SH_ZONES = {
 'Huangpu':'central','Jingan':'central','Xuhui':'central','Changning':'central',
 'Putuo':'central','Hongkou':'central','Yangpu':'central','Pudong':'peri',
 'Minhang':'peri','Baoshan':'peri','Jiading':'suburban','Qingpu':'suburban',
 'Songjiang':'suburban','Jinshan':'suburban','Fengxian':'suburban','Chongming':'suburban',
}
NY_PERI={'34017','34003','34031','34013','34039','36119','36059'}
POLICIES=('V2G','Battery Charging','EV Subsidy','Tax Incentive',
          'CAFC Credit','NEV Credit','Grid Decarb','Charging Station')
CLASS_TO_NAME = {
 'Policy':'Reference','V2GPolicy':'V2G',
 'BatteryChargingPolicy':'Battery Charging','SubsidyPolicy':'EV Subsidy',
 'TaxIncentivePolicy':'Tax Incentive','CAFCPolicy':'CAFC Credit',
 'NEVCreditPolicy':'NEV Credit','GridDecarbPolicy':'Grid Decarb',
 'ChargingStationPolicy':'Charging Station',
}
PARAMS = {
 'V2G':{'reduction':.15},'Battery Charging':{'improvement':.12},
 'EV Subsidy':{'intensity_2024':.25,'decay_rate':.10},
 'Tax Incentive':{'intensity_2024':.20,'decay_rate':.05},
 'CAFC Credit':{'slope1':.005,'slope2':.010,'mfg_red':.05},
 'NEV Credit':{'increment':.03,'cap':.60,'compliance':.80},
 'Grid Decarb':{'target_year_sh':2045,'target_year_ny':2035},
 'Charging Station':{'rate1':.010,'rate2':.005,'cap':.35},
}

def _sh_norm(v):
 s=str(v).strip().replace('\u65b0\u533a','').replace('\u533a','').replace('\u9759\u5b89','Jingan')
 return s

def load_stocks(sh_path,ny_path):
    """Reads the real stock CSVs created by the author's original PCA/Poisson code.
    For Shanghai columns ICEV/PHEV/BEV are in 10^4 vehicles; NYMA in vehicles.
    No interpolation or filler is allowed for missing data.
    """
    sh=pd.read_csv(sh_path)
    ny=pd.read_csv(ny_path,dtype={'tract':str})
    needed_sh={'district','year','ICEV','BEV','PHEV'}
    needed_ny={'tract','year','ICEV','BEV','PHEV'}
    for frame,need,label in [(sh,needed_sh,'Shanghai'),(ny,needed_ny,'NYMA')]:
        miss=need-set(frame.columns)
        if miss: raise ValueError(f'{label} stock columns missing: {miss}')
    sh['region_id']=sh['district'].map(_sh_norm)
    unknown=set(sh.region_id)-set(SH_ZONES)
    if unknown: raise ValueError('Unmapped Shanghai districts: '+str(unknown))
    sh['zone']=sh.region_id.map(SH_ZONES)
    sh['county']=sh['region_id']
    sh['city']='SH'
    for k in ('ICEV','BEV','PHEV'):
        sh[k]=pd.to_numeric(sh[k],errors='raise')*10000
    ny['tract']=ny['tract'].astype(str).str.replace(r'\.0$','',regex=True).str.zfill(11)
    if (ny.tract.str.len()!=11).any():
        raise ValueError('Invalid 11-digit NYMA census tract GEOID')
    ny['county']=ny.tract.str[:5]
    EF.require_22_counties(ny.county.unique())
    ny['region_id']=ny['tract']
    ny['zone']=np.select([ny.county.isin(EF.NYC_COUNTIES),ny.county.isin(NY_PERI)],
                         ['central','peri'],default='suburban')
    ny['city']='NYMA'
    for k in ('ICEV','BEV','PHEV'):
        ny[k]=pd.to_numeric(ny[k],errors='raise')
    result=pd.concat([sh,ny],ignore_index=True)
    result['year']=result['year'].astype(int)
    if ((result[['ICEV','BEV','PHEV']]<0).any().any()):
        raise ValueError('Negative stock count found')
    for city in ('SH','NYMA'):
        y=set(result.loc[result.city==city,'year'])
        if y!=set(range(2024,2061)):
            raise ValueError(f'{city}: expected years 2024–2060, found missing={sorted(set(range(2024,2061))-y)} extra={sorted(y-set(range(2024,2061)))}')
    return result[['city','region_id','county','zone','year','ICEV','BEV','PHEV']]


def prepare(stocks):
    """Precompute constant fuel/grid factors; do not run any experiment."""
    d=stocks.copy()
    years=d.year.to_numpy(int)
    sh=d.city.eq('SH').to_numpy()
    d['VKT_reference']=np.where(sh,12000*1.003**(years-2024),
            18500*(1.005**(years-2024))*(0.994**(years-2024)))
    d['TTW_co2_gkm']=EF.TTW_BASE_GCO2_PER_KM*(1-EF.TTW_ANNUAL_IMPROVEMENT)**(years-2024)
    d['TTW_nonco2_gkm']=np.full(len(d),EF.TAILPIPE_NONCO2_GCO2E_GKM)
    d['TTW_gkm']=d['TTW_co2_gkm']+d['TTW_nonco2_gkm']
    d['WTP_gkm']=d['TTW_co2_gkm']*np.where(sh,EF.UPSTREAM_TTW_RATIO['SH'],EF.UPSTREAM_TTW_RATIO['NYMA'])
    # Map NYMA counties only; Shanghai district names are not FIPS.
    grid_codes=np.full(len(d),'SH',dtype=object)
    grid_codes[~sh]=d.loc[~sh,'county'].map(EF.nyma_subregion).to_numpy()
    d['grid_region']=grid_codes
    # Shanghai EFs are also present in data_inputs CSV; EF.sh_grid_ci uses same path assumptions.
    d['grid_average']=np.array([EF.grid_ci(c,y,r) for c,y,r in zip(d.city,years,d.county)],dtype=float)
    d['grid_marginal']=np.array([EF.grid_ci(c,y,r,'marginal') for c,y,r in zip(d.city,years,d.county)],dtype=float)
    d['grid_upstream']=np.array([EW.upstream_for_direct(r,f) for r,f in zip(d.grid_region,d.grid_average)],dtype=float)
    d['grid_marginal_upstream']=np.array([EW.upstream_for_direct(r,f,kind='marginal') for r,f in zip(d.grid_region,d.grid_marginal)],dtype=float)
    if d[['grid_average','grid_marginal']].isna().any().any():
        raise ValueError('Missing grid emission factors')
    return d


def _p(city,policy,params):
    p=PARAMS.get(policy,{}).copy()
    if params: p.update(params)
    return p


def simulate(prepared,city,policy='Reference',params=None,uf=.50,
             upstream_scale=1.0,year_filter=None,detail=False, power_upstream_scale=1.0):
    """Run policy on original tract/district stock rows, preserving scenario logic.
    Returns per-year emissions in Mt CO2e; `detail=True` also exposes each spatial row
    and charging kWh for weighted average EF, per-capita emissions and station analysis.
    Parameter values are scenario-response assumptions, not identified policy effects.
    """
    if policy not in ('Reference',*POLICIES):raise ValueError(policy)
    if not 0<=uf<=1 or upstream_scale<0 or power_upstream_scale<0:raise ValueError('Invalid UF or upstream scale')
    s=prepared.loc[prepared.city.eq(city)].copy()
    if year_filter is not None:
        years={int(x) for x in year_filter}
        s=s[s.year.isin(years)].copy()
    if s.empty:raise ValueError('No stock rows in selected area/years')
    p=_p(city,policy,params)
    y=s.year.to_numpy(int);dt=y-2024
    icev=s.ICEV.to_numpy(float).copy()
    bev=s.BEV.to_numpy(float).copy()
    phev=s.PHEV.to_numpy(float).copy()
    total=icev+bev+phev
    vkt=s.VKT_reference.to_numpy(float).copy()
    gas_ttw=s.TTW_gkm.to_numpy(float)
    gas_wtp=s.WTP_gkm.to_numpy(float)*float(upstream_scale)
    gas=gas_ttw+gas_wtp
    grid=s.grid_average.to_numpy(float)
    grid_wtp=s.grid_upstream.to_numpy(float)*power_upstream_scale
    elec=(grid+grid_wtp)*EF.BEV_KWH_PER_KM
    electric_reduction=np.zeros(len(s))
    if policy=='V2G' and city=='SH':
        electric_reduction=np.where(y>=2028,p['reduction'],0.)
    elif policy=='Battery Charging':
        electric_reduction=p['improvement']*np.clip((y-2024)/11,0,1)
    elif policy=='EV Subsidy' and city=='SH':
        factor=np.clip(p['intensity_2024']*(1-p['decay_rate'])**np.maximum(dt,0),0,.6)
        factor*=s.zone.map({'central':.5,'peri':1.0,'suburban':1.5}).to_numpy(float)
        moved=icev*factor
        icev-=moved;bev+=.7*moved;phev+=.3*moved
        vkt*=1.01
    elif policy=='Tax Incentive':
        factor=np.clip(p['intensity_2024']*(1-p['decay_rate'])**np.maximum(dt,0),0,.5)
        factor*=s.zone.map({'central':.6,'peri':1.0,'suburban':1.4}).to_numpy(float)
        moved=icev*factor
        icev-=moved;bev+=.65*moved;phev+=.35*moved
        vkt*=1.005
    elif policy=='CAFC Credit':
        extra=np.where(y<=2024,0.,np.where(y<=2035,p['slope1']*(y-2024),
                           p['slope1']*11+p['slope2']*(y-2035)))
        # Original code modifies only ICEV, not PHEV gasoline operation.
        gas_icev=gas*(1-extra)
    elif policy=='NEV Credit':
        target=np.minimum(p['cap'],.1+p['increment']*dt)
        share=np.divide(bev+phev,total,out=np.zeros_like(total),where=total>0)
        moved=total*np.maximum(0,target-share)*p['compliance']
        moved=np.minimum(moved,icev)
        icev-=moved;bev+=.7*moved;phev+=.3*moved
    elif policy=='Grid Decarb':
        target_year=p['target_year_sh' if city=='SH' else 'target_year_ny']
        grid=np.array([EF.policy_grid_ci(c,int(t),r,target_year)
                       for c,t,r in zip(s.city,y,s.county)],dtype=float)
        grid_wtp=np.array([EW.upstream_for_direct(r, f, scale=power_upstream_scale)
            for r,f in zip(s.grid_region,grid)],dtype=float)
        elec=(grid+grid_wtp)*EF.BEV_KWH_PER_KM
    elif policy=='Charging Station':
        factor=np.where(y<=2024,.05,np.where(y<=2030,
                .05+p['rate1']*(y-2024),.05+p['rate1']*6+p['rate2']*(y-2030)))
        factor=np.minimum(p['cap'],factor)
        factor*=s.zone.map({'central':1.2,'peri':1.0,'suburban':.7}).to_numpy(float)
        moved=icev*factor
        icev-=moved;bev+=.8*moved;phev+=.2*moved
        vkt*=1.015
    if (icev<-.001).any():raise ValueError('Negative ICEV stock after policy')
    elec_after=elec*(1-electric_reduction)
    ef_icev=gas_icev if policy=='CAFC Credit' else gas
    mfg_icev=EF.MFG_REC_GCO2EQ_PER_KM['ICEV']*np.ones(len(s))
    if policy=='CAFC Credit':
        mfg_icev*=1-p['mfg_red']*np.clip((y-2024)/10,0,1)
    ef_icev=ef_icev+mfg_icev
    ef_bev=elec_after+EF.MFG_REC_GCO2EQ_PER_KM['BEV']
    ef_phev=(1-uf)*gas+uf*elec_after+EF.MFG_REC_GCO2EQ_PER_KM['PHEV']
    charging=(bev+uf*phev)*EF.BEV_KWH_PER_KM*vkt*(1-electric_reduction)
    out=s[['city','region_id','county','zone','year']].copy()
    out['ICEV_stock']=icev;out['BEV_stock']=bev;out['PHEV_stock']=phev
    out['VKT_km_per_vehicle']=vkt
    out['ICEV_ton']=icev*ef_icev*vkt/1e12  # legacy column name, UNITS ACTUALLY Mt
    out['BEV_ton']=bev*ef_bev*vkt/1e12
    out['PHEV_ton']=phev*ef_phev*vkt/1e12
    out['total_ton']=out[['ICEV_ton','BEV_ton','PHEV_ton']].sum(axis=1)
    cafc_scale=np.where(policy=='CAFC Credit', 1-np.where(y<=2024,0.,
            np.where(y<=2035,p.get('slope1',.005)*(y-2024),
            p.get('slope1',.005)*11+p.get('slope2',.010)*(y-2035))),1.)
    out['ICEV_TTW_Mt']=icev*gas_ttw*cafc_scale*vkt/1e12
    out['ICEV_WTP_Mt']=icev*gas_wtp*cafc_scale*vkt/1e12
    out['PHEV_TTW_Mt']=phev*(1-uf)*gas_ttw*vkt/1e12
    out['ICEV_manufacturing_recycling_Mt']=icev*mfg_icev*vkt/1e12
    out['BEV_manufacturing_recycling_Mt']=bev*EF.MFG_REC_GCO2EQ_PER_KM['BEV']*vkt/1e12
    out['PHEV_manufacturing_recycling_Mt']=phev*EF.MFG_REC_GCO2EQ_PER_KM['PHEV']*vkt/1e12
    out['BEV_power_generation_Mt']=bev*grid*EF.BEV_KWH_PER_KM*vkt*(1-electric_reduction)/1e12
    out['PHEV_power_generation_Mt']=phev*uf*grid*EF.BEV_KWH_PER_KM*vkt*(1-electric_reduction)/1e12
    out['BEV_electricity_fuel_WTP_Mt']=bev*grid_wtp*EF.BEV_KWH_PER_KM*vkt*(1-electric_reduction)/1e12
    out['PHEV_electricity_fuel_WTP_Mt']=phev*uf*grid_wtp*EF.BEV_KWH_PER_KM*vkt*(1-electric_reduction)/1e12
    out['PHEV_WTP_Mt']=phev*(1-uf)*gas_wtp*vkt/1e12
    out['ICEV_tailpipe_nonCO2_Mt']=icev*s.TTW_nonco2_gkm.to_numpy(float)*cafc_scale*vkt/1e12
    out['PHEV_tailpipe_nonCO2_Mt']=phev*(1-uf)*s.TTW_nonco2_gkm.to_numpy(float)*vkt/1e12
    out['SH_grid_generation_nonCO2_Mt']=np.where(s.city.eq('SH'),(out.BEV_power_generation_Mt+out.PHEV_power_generation_Mt)*EF.SH_GENERATION_NONCO2_OVER_CO2/(1+EF.SH_GENERATION_NONCO2_OVER_CO2),0.0)
    out['charging_kWh']=charging
    out['grid_average_g_per_kWh']=s.grid_average.to_numpy(float)
    out['grid_upstream_g_per_kWh']=grid_wtp
    out['grid_WTW_g_per_kWh']=grid+grid_wtp
    out['grid_marginal_g_per_kWh']=s.grid_marginal.to_numpy(float)
    out['policy']=policy;out['uf']=uf
    if detail:return out
    aggregate=out.groupby('year',as_index=False)[['ICEV_ton','BEV_ton','PHEV_ton',
        'total_ton','ICEV_WTP_Mt','PHEV_WTP_Mt','BEV_electricity_fuel_WTP_Mt','PHEV_electricity_fuel_WTP_Mt','ICEV_TTW_Mt','PHEV_TTW_Mt','ICEV_manufacturing_recycling_Mt','BEV_manufacturing_recycling_Mt','PHEV_manufacturing_recycling_Mt','BEV_power_generation_Mt','PHEV_power_generation_Mt','charging_kWh']].sum()
    aggregate['city']=city;aggregate['policy']=policy;aggregate['uf']=uf
    return aggregate


def evaluate_from_frame(city,stock_frame,policy,uf=.50,detail=False):
    """Adapter used by existing original-style Figure 2/3/4 Notebook cells.
    Input is already scaled original `load_stock_data` result, including region_id.
    """
    name=CLASS_TO_NAME.get(policy.__class__.__name__)
    if name is None:raise ValueError('Unrecognized policy object class')
    df=stock_frame.copy()
    df['city']=city
    if city=='SH':
        df['county']=df.region_id.map(_sh_norm)
        df['zone']=df.county.map(SH_ZONES)
    else:
        df['region_id']=df.region_id.astype(str).str.replace(r'\.0$','',regex=True).str.zfill(11)
        df['county']=df.region_id.str[:5]
        df['zone']=np.select([df.county.isin(EF.NYC_COUNTIES),df.county.isin(NY_PERI)],
                             ['central','peri'],default='suburban')
        EF.require_22_counties(df.county.unique())
    if df.zone.isna().any():raise ValueError('Unmapped zone in original notebook stock frame')
    # Lossless county aggregation only when individual tract powertrain shares
    # are identical within every county/year. Preserves original policy stock
    # transfer and EV EF exactly while speeding up author's original notebooks.
    if city=='NYMA':
        denom=df[['ICEV','BEV','PHEV']].sum(axis=1)
        for t in ('BEV','PHEV'):
            df[t+'_share']=np.divide(df[t],denom,out=np.zeros(len(df)),where=denom>0)
        spread=df.groupby(['county','year'])[['BEV_share','PHEV_share']].agg(lambda z:float(z.max()-z.min()))
        if (spread.to_numpy()<=1e-10).all():
            df=df.groupby(['city','county','zone','year'],as_index=False)[['ICEV','BEV','PHEV']].sum()
            df['region_id']=df['county']
        else:
            df=df.drop(columns=['BEV_share','PHEV_share'])
    q=prepare(df)
    # original class Policy instance can be 'dummy'; no policy double counting.
    p=getattr(policy,'params',{}) or {}
    if 'target_year' in p:
        p=p.copy();p['target_year_sh' if city=='SH' else 'target_year_ny']=p.pop('target_year')
    return simulate(q,city,name,p,uf,detail=detail)


def _inspect_invariants():
    # Pure source-level validation: no model/data execution.
    assert set(POLICIES)==set(PARAMS)
    assert len(EF.NYMA_COUNTIES)==22

_inspect_invariants()
