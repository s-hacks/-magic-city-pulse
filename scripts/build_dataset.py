#!/usr/bin/env python3
"""Build Magic City Pulse data using only the Python standard library."""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SNAP = 'https://services1.arcgis.com/RLQu0rK7h4kbsBq5/arcgis/rest/services/snap_retailer_location_data/FeatureServer/0/query'
HRSA = 'https://data.hrsa.gov/DataDownload/DD_Files/Health_Center_Service_Delivery_and_LookAlike_Sites.csv'
CORRIDORS = {
    'Downtown': (33.5165, -86.8091, 'Central Station / downtown corridor'),
    'Ensley': (33.4981, -86.8768, 'Bessemer Rd / Ensley corridor'),
    'West End': (33.4956, -86.8524, 'Tuscaloosa Ave / West End corridor'),
    'Woodlawn': (33.5382, -86.7469, '1st Ave N / Woodlawn corridor'),
    'Southside': (33.5015, -86.7985, '11th Ave S / Southside corridor'),
    'Avondale': (33.5245, -86.7839, '2nd Ave N / Avondale corridor'),
}
SEEDS = [
("Firehouse Ministries (Men's Emergency Shelter & Meals)", '626 2nd Ave N', '35203',33.5165,-86.8091,'shelter','emergency_shelter','Daily check-in 4:00 PM; Lunch 11:30 AM open to all','ID if available','MAX Route 20 / Central Station (2 blocks)'),
('First Light Shelter (Women & Families)','2230 4th Ave N','35203',33.5198,-86.8041,'shelter','emergency_shelter','24/7 Emergency Shelter & Day Program','Photo ID if available','MAX Route 17 / 4th Ave N & 22nd St'),
("Jimmie Hale Mission (Men's Shelter & Recovery)",'3420 2nd Ave N','35222',33.5245,-86.7839,'shelter','shelter_recovery','Check-in 3:30 PM - 5:30 PM daily','Valid ID','MAX Route 1 / 2nd Ave N & 34th St'),
('Urban Ministry WE Care Food Pantry (West End / Ensley area)','1229 Cotton Ave SW','35211',33.4956,-86.8524,'food','food_pantry','Tue & Thu 9:00 AM - 12:00 PM','Photo ID & proof of Jefferson County address','MAX Route 45 / Tuscaloosa Ave'),
('First United CPCA Mobile & Neighborhood Pantry (Ensley)','1843 Bessemer Rd','35208',33.4981,-86.8768,'food','food_pantry','Wed & Fri 10:00 AM - 1:00 PM','Reusable bags, ID helpful','MAX Route 45 / Bessemer Rd'),
("Community Kitchens at St. Andrew's (Southside Hot Lunch)",'1024 12th St S','35205',33.5015,-86.7985,'food','soup_kitchen','Daily hot lunch 11:30 AM - 12:30 PM','Nothing required — open to everyone','MAX Route 14 / 11th Ave S'),
('Grace Episcopal Church Community Kitchen (Woodlawn)','5712 1st Ave N','35212',33.5382,-86.7469,'food','soup_kitchen','Weekdays Breakfast 9:00 AM; Daily Lunch 12:00 PM','Nothing required','MAX Route 1 / 1st Ave N & 57th St'),
('Church of the Highlands Dream Center (Woodlawn Food & Outreach)','5705 1st Ave N','35212',33.5389,-86.7472,'food','food_pantry','Sat 9:00 AM - 11:30 AM','Photo ID','MAX Route 1 / 1st Ave N & 57th St'),
('Christian Service Mission (Food & Family Aid)','3600 3rd Ave S','35222',33.5162,-86.7795,'food','food_pantry','Mon-Fri 8:30 AM - 3:30 PM','Photo ID','MAX Route 28 / 3rd Ave S'),
('Christ Health Center (Woodlawn Sliding-Scale Clinic)','5804 1st Ave S','35212',33.5356,-86.7448,'health','sliding_scale_clinic','Mon-Fri 7:30 AM - 5:00 PM (Walk-ins welcome)','ID & proof of income if available (no one turned away)','MAX Route 1 / 1st Ave N'),
]

def now():
    return datetime.now(timezone.utc).isoformat()


def distance(lat, lon, lat2, lon2):
    a,b = math.radians(lat),math.radians(lat2)
    v=math.sin((b-a)/2)**2+math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon)/2)**2
    return 6371*2*math.asin(math.sqrt(min(1,max(0,v))))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)
            f.write('\n')
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def pick(row,*keys,default=''):
    normalized={k.lower().replace('_',' ').strip():v for k,v in row.items() if k}
    for k in keys:
        value=normalized.get(k.lower().replace('_',' ').strip())
        if value is not None and str(value).strip(): return str(value).strip()
    return default


def record(name,address,zip_code,lat,lon,category,subcategory,source,**extra):
    lat,lon=float(lat),float(lon)
    if not (math.isfinite(lat) and math.isfinite(lon) and 30<lat<35.1 and -89<lon<-84):
        raise ValueError(f'Invalid Alabama coordinates: {name}: {lat}, {lon}')
    neighborhood=min(CORRIDORS,key=lambda n:distance(lat,lon,*CORRIDORS[n][:2]))
    key='|'.join([name.lower().strip(),address.lower().strip()])
    r=dict(id=hashlib.sha256(key.encode()).hexdigest()[:16],name=name,category=category,
           subcategory=subcategory,neighborhood=neighborhood,address=address,zip=zip_code[:5],
           lat=lat,lon=lon,phone='',hours_today='Hours unavailable; contact provider',status='limited',
           what_to_bring='',nearest_max_stop='Approximate corridor: '+CORRIDORS[neighborhood][2],
           last_verified=None,source=source,retrieved_at=now(),
           transit_is_approximate=True,status_note='Current service availability has not been confirmed')
    r.update(extra)
    return r


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'MagicCityPulse/1.0'}),timeout=90)


def fetch_snap():
    result=[]
    offset=0
    while True:
        params=dict(where="State='AL' AND City='BIRMINGHAM'",outFields='*',f='geojson',outSR=4326,resultOffset=offset,resultRecordCount=1000)
        with request(SNAP+'?'+urllib.parse.urlencode(params)) as f: payload=json.load(f)
        if 'error' in payload: raise RuntimeError(str(payload['error']))
        if 'features' not in payload: raise ValueError('USDA response missing features')
        features=payload['features']
        for feature in features:
            p=feature['properties']; coords=(feature.get('geometry') or {}).get('coordinates') or []
            lat=coords[1] if len(coords)>1 else pick(p,'Latitude','Y')
            lon=coords[0] if len(coords)>1 else pick(p,'Longitude','X')
            result.append(record(pick(p,'Store_Name','Store Name','Name'),pick(p,'Address','Address Line 1','Address1'),pick(p,'Zip','Zip Code'),lat,lon,'food','snap_retailer','USDA SNAP',what_to_bring='EBT / SNAP Card',source_url=SNAP,phone=pick(p,'Phone','Telephone')))
        if not payload.get('exceededTransferLimit') and not payload.get('properties',{}).get('exceededTransferLimit'): break
        if not features: raise ValueError('USDA pagination stalled')
        offset+=len(features)
    return result


def fetch_hrsa():
    result=[]
    with request(HRSA) as response:
        rows=csv.DictReader(io.TextIOWrapper(response,encoding='utf-8-sig',newline=''))
        required={'Site State Abbreviation','Site City'}
        if not required.issubset(set(rows.fieldnames or [])): raise ValueError('HRSA CSV filter columns missing: '+str(rows.fieldnames))
        for p in rows:
            if pick(p,'Site State Abbreviation').upper()!='AL' or pick(p,'Site City').upper()!='BIRMINGHAM': continue
            result.append(record(pick(p,'Site Name','Health Center Site Name'),pick(p,'Site Address','Site Street Address','Site Address Line 1'),pick(p,'Site ZIP Code','Site Postal Code'),pick(p,'Site Latitude','Latitude','Y'),pick(p,'Site Longitude','Longitude','X'),'health','fqhc_clinic','HRSA',phone=pick(p,'Site Telephone Number','Site Phone Number'),hours_today=pick(p,'Site Hours','Hours of Operation',default='Hours unavailable; contact clinic'),what_to_bring='Photo ID if available (sliding-scale care provided regardless of insurance or ability to pay)',source_url=HRSA))
    return result


def build():
    DATA.mkdir(exist_ok=True)
    stamp=now(); records=[]
    for name,address,z,lat,lon,category,sub,hours,bring,bus in SEEDS:
        records.append(record(name,f'{address}, Birmingham, AL {z}',z,lat,lon,category,sub,'One Roof / Local' if category in ('shelter','health') else 'Community Food Bank Partner',hours_today=hours,what_to_bring=bring,nearest_max_stop=bus,transit_is_approximate=False,last_verified=stamp,verified_by='Community Partner / Verified Local',verification_note='User-supplied local seed list; timestamp records import, not independent verification'))
    report={'built_at':stamp,'local_seed_count':len(records),'sources':{}}
    previous=json.loads((DATA/'resources.json').read_text()) if (DATA/'resources.json').exists() else []
    for source,fetch in [('USDA SNAP',fetch_snap),('HRSA',fetch_hrsa)]:
        try:
            downloaded=fetch()
            if not downloaded: raise ValueError('Source returned zero Birmingham records')
            records.extend(downloaded)
            report['sources'][source]={'downloaded':len(downloaded),'error':None}
        except Exception as exc:
            retained=[r for r in previous if r['source']==source]
            records.extend(retained)
            report['sources'][source]={'downloaded':0,'retained':len(retained),'error':str(exc)}
    # Preserve local dispatches, synthetic expansion, and volunteer corrections.
    overlays={r['id']:r for r in previous if r.get('volunteer_updated')}
    records=[overlays.get(r['id'],r) for r in records]
    records.extend(r for r in previous if r.get('is_demo') or (r.get('volunteer_updated') and r['id'] not in {x['id'] for x in records}))
    # Local records take precedence over a federal record with the same street address.
    unique=[]; seen=set()
    for r in records:
        key=('provider-drop',r['id']) if r.get('provider_confirmed') else (r['address'].split(',')[0].strip().lower(),r['category'])
        if key in seen: continue
        seen.add(key); unique.append(r)
    try:
        from scripts.availability import active_status
    except ModuleNotFoundError:
        from availability import active_status
    for r in unique:
        r['status'] = active_status(r)
        if r['status'] in ('open', 'closed'):
            r['status_note'] = 'Based on supplied schedule in America/Chicago; availability not live-confirmed'
    atomic_json(DATA/'resources.json',unique)
    report['saved']=len(unique)
    report['complete']=all(not s['error'] for s in report['sources'].values())
    atomic_json(DATA/'ingestion_report.json',report)
    print(json.dumps(report,indent=2))
    print('Sample records:')
    print(json.dumps(unique[:3],indent=2))
    return 0 if report['complete'] else 2

if __name__=='__main__':
    raise SystemExit(build())
