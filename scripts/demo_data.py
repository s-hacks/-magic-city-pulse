"""Idempotent local demo expansion. Never represents synthetic data as verified fact."""
from datetime import datetime
from zoneinfo import ZoneInfo
from scripts.build_dataset import DATA, atomic_json, record, now
import json

ZIPS={
 '35203':('Downtown',33.5165,-86.8091,'Central Station','MAX Route 20 / Central Station'),
 '35204':('Smithfield',33.526,-86.835,'Smithfield community host','MAX Route 6 / 8th Ave N & Center St'),
 '35205':('Southside',33.5015,-86.7985,'Southside community host','MAX Route 14 / 11th Ave S & 12th St S'),
 '35208':('Ensley',33.4981,-86.8768,'First United CPCA','MAX Route 45 / Bessemer Rd'),
 '35211':('West End',33.4956,-86.8524,'Urban Ministry','MAX Route 45 / Tuscaloosa Ave'),
 '35212':('Woodlawn',33.5382,-86.7469,'Woodlawn community host','MAX Route 1 / 1st Ave N & 57th St'),
 '35218':('Ensley',33.512,-86.893,'For-Word Christian Center (proposed demo host)','MAX Route 6 / Ensley Ave & 19th St'),
}

def initialize():
    rows=json.loads((DATA/'resources.json').read_text())
    for r in rows:
        r.setdefault('is_demo',False)
        if r['category']=='food': r.setdefault('bags_available',None)
        if r['category']=='health': r.setdefault('no_insurance_ok',True)
        if r['category']=='shelter':
            # Eligibility/bed counts below are demo overlays, not provider confirmation.
            r.setdefault('min_age',18)
            r.setdefault('allowed_genders',['female','family'] if 'First Light' in r['name'] else ['male'])
            r.setdefault('beds_available',6 if 'First Light' in r['name'] else 8)
            r.setdefault('check_in_window',r['hours_today'])
            r['availability_is_demo']=True
    existing={r['id'] for r in rows}
    specs=[('35218','food','Ensley neighborhood grocery','snap_retailer'),('35218','food','Ensley evening bag table','food_pantry'),('35211','food','West End fresh food share','food_pantry'),('35204','food','Smithfield community pantry','food_pantry'),('35205','food','Southside neighborhood market','snap_retailer'),('35212','food','Woodlawn supper table','soup_kitchen'),('35208','food','Ensley family food shelf','food_pantry'),('35203','food','Downtown meal circle','soup_kitchen'),('35204','health','Smithfield community care','community_clinic'),('35211','health','West End walk-in care','community_clinic'),('35212','health','Woodlawn evening care','community_clinic'),('35218','shelter','Ensley welcome house','emergency_shelter'),('35204','shelter','Smithfield family welcome','emergency_shelter'),('35205','shelter','Southside night haven','emergency_shelter')]
    for i,(z,cat,name,sub) in enumerate(specs):
        n,lat,lon,host,bus=ZIPS[z]
        r=record(name+' · Demo',f'Demo host near {host}, Birmingham, AL {z}',z,lat+(i%3)*.001,lon+(i%2)*.001,cat,sub,'Synthetic demo',is_demo=True,status='open' if i%5 else 'limited',neighborhood=n,hours_today='Demo hours: daily 8 AM–8 PM',what_to_bring='EBT / SNAP Card (purchases, not free bags)' if sub=='snap_retailer' else 'ID if available; demo service',nearest_max_stop=bus,transit_is_approximate=True,last_verified=None)
        if cat=='food': r['bags_available']=0 if sub=='snap_retailer' else 12+i
        if cat=='health': r['no_insurance_ok']=True
        if cat=='shelter': r.update(min_age=18,allowed_genders=['all'] if z=='35218' else ['female','family'],beds_available=5,check_in_window='Demo check-in: 4 PM–8 PM',availability_is_demo=True)
        if r['id'] not in existing: rows.append(r)
    atomic_json(DATA/'resources.json',rows)
    if not (DATA/'requests.json').exists():
        date=datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
        requests=[]
        names=['Avery','Jordan','Taylor','Morgan','Casey','Riley','Cameron','Drew','Jamie','Alex','Sam','Robin','Charlie','Reese','Quinn','Skyler','Rowan','Blake']
        for i,z in enumerate(['35218']*9+['35211']*5+['35212']*4):
            dt=date+'T18:00'; name=names[i]
            requests.append(dict(request_key=f'{name.lower()}_{z}_{dt}',name=name,zip_code=z,date_time=dt,category='food',age=None,gender=None,status='pending',created_at=now(),is_demo=True))
        atomic_json(DATA/'requests.json',requests)
    if not (DATA/'deployments.json').exists(): atomic_json(DATA/'deployments.json',[])

if __name__=='__main__': initialize()
