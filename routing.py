"""Optional pedestrian routing for the local demo. No keys or location persistence."""
import json
import math
import threading
import time
import urllib.request
from urllib.parse import urlencode

_CACHE = {}
_LOCK = threading.Lock()
_LAST_REQUEST = 0.0


def location(value):
    if not isinstance(value, dict): raise ValueError('Supply a location with lat and lon')
    lat,lon=value.get('lat'),value.get('lon')
    if isinstance(lat,bool) or isinstance(lon,bool) or not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)):
        raise ValueError('Coordinates must be numbers')
    if not (math.isfinite(lat) and math.isfinite(lon) and 33.3<lat<33.75 and -87.1<lon<-86.5):
        raise ValueError('Choose a starting point in the Birmingham area, or keep using your ZIP')
    return float(lat),float(lon)


def links(resource, origin=None):
    params={'api':1,'destination':f"{resource['lat']},{resource['lon']}"}
    if origin: params['origin']=f'{origin[0]},{origin[1]}'
    return {mode:'https://www.google.com/maps/dir/?'+urlencode({**params,'travelmode':mode}) for mode in ('walking','transit')}


def route(origin, resource):
    global _LAST_REQUEST
    base={'available':False,'destination_id':resource['id'],'mode':'walking'}
    if resource.get('is_demo'):
        return {**base,'message':'This is an illustrative demo place. Choose a local listing for real directions.'}
    base['links']=links(resource,origin)
    key=(*origin,resource['id'],resource['lat'],resource['lon'])
    # Public demo policy: at most one request per second. Keep a small ephemeral cache.
    with _LOCK:
        current=time.monotonic()
        for k in list(_CACHE):
            if current-_CACHE[k][0]>300: del _CACHE[k]
        if key in _CACHE: return _CACHE[key][1]
        if current-_LAST_REQUEST<1:
            return {**base,'message':'One moment, neighbor—try again in a second, or open directions.'}
        _LAST_REQUEST=current
    coords=f"{origin[1]},{origin[0]};{resource['lon']},{resource['lat']}"
    url='https://routing.openstreetmap.de/routed-foot/route/v1/foot/'+coords+'?overview=full&geometries=geojson&steps=true&generate_hints=false'
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'MagicCityPulse/1.0','Accept':'application/json'})
        with urllib.request.urlopen(request,timeout=10) as response: payload=json.load(response)
        if payload.get('code')!='Ok' or not payload.get('routes'): raise ValueError('No route')
        result=payload['routes'][0];geometry=result['geometry']
        if geometry.get('type')!='LineString' or len(geometry.get('coordinates',[]))<2: raise ValueError('Invalid route')
        for point in geometry['coordinates']: location({'lat':point[1],'lon':point[0]})
        meters,seconds=float(result['distance']),float(result['duration'])
        if not all(math.isfinite(v) and v>=0 for v in (meters,seconds)): raise ValueError('Invalid estimate')
        steps=[]
        for leg in result.get('legs',[]):
            for step in leg.get('steps',[]):
                maneuver=step.get('maneuver',{})
                steps.append({'type':maneuver.get('type','continue'),'modifier':maneuver.get('modifier',''),'street':step.get('name',''),'distance_m':step.get('distance',0)})
        answer={**base,'available':True,'geometry':geometry,'distance_m':meters,'duration_s':seconds,'steps':steps[:80],
                'attribution':'Walking route: OSRM / FOSSGIS · OpenStreetMap contributors',
                'message':'Estimated walking route; confirm the destination and service hours. Bus fares are not included.'}
        with _LOCK:
            if len(_CACHE)>=128: _CACHE.pop(next(iter(_CACHE)))
            _CACHE[key]=(time.monotonic(),answer)
        return answer
    except Exception:
        return {**base,'message':'Walking directions are temporarily unavailable. You can still open Google Maps. No route has been invented.'}
