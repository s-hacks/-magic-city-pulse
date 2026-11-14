"""Optional server-side Birmingham geocoding. Failures never escape to clients."""
import json
import math
import os
import re
from urllib.parse import urlencode
import urllib.request
from scripts.demo_data import ZIPS


def street_address(message):
    match = re.search(r'\b\d{1,6}\s+(?:[\w.\'-]+\s+){0,6}(?:avenue|ave|street|st|road|rd|boulevard|blvd|drive|dr|lane|ln|court|ct|way)\b(?:\s+(?:NE|NW|SE|SW|N|S|E|W)\b)?', message, re.I)
    return match.group(0) if match else None


def geocode(location):
    key = os.getenv('GOOGLE_MAPS_API_KEY', '').strip()
    if not key or not isinstance(location, str) or not location.strip():
        return None
    params = {'address': location + ', Birmingham, AL, USA',
              'components': 'administrative_area:AL|country:US', 'key': key}
    try:
        url = 'https://maps.googleapis.com/maps/api/geocode/json?' + urlencode(params)
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.load(response)
        if payload.get('status') != 'OK':
            return None
        for result in payload.get('results', []):
            coords = result['geometry']['location']
            lat, lon = float(coords['lat']), float(coords['lng'])
            # Reject bad or distant matches rather than relocating a neighbor outside Birmingham.
            if not (math.isfinite(lat) and math.isfinite(lon) and 33.3 < lat < 33.75 and -87.1 < lon < -86.5):
                continue
            components = result.get('address_components', [])
            zip_code = next((c['short_name'] for c in components if 'postal_code' in c.get('types', [])), None)
            return {'lat': lat, 'lon': lon, 'zip_code': zip_code,
                    'source': 'Google Geocoding', 'precision': result['geometry'].get('location_type', 'unknown')}
    except Exception:
        # Never log URLs/exceptions: Google's URL contains the API key.
        return None
    return None


def resolve(message, state):
    address = street_address(message) or state.get('address')
    if address:
        return geocode(address)
    lower = message.casefold()
    for info in ZIPS.values():
        if info[0].casefold() in lower:
            return geocode(info[0])
    zip_code = str(state.get('zip_code', ''))
    return geocode(zip_code) if zip_code in ZIPS else None
