"""Cache pinned Leaflet assets locally; CDN fallback remains available."""
from pathlib import Path
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
for name in ('leaflet.js','leaflet.css','LICENSE'):
    target=ROOT/'static'/'vendor'/name
    try:
        url='https://unpkg.com/leaflet@1.9.4/'+('LICENSE' if name=='LICENSE' else 'dist/'+name)
        request=urllib.request.Request(url,headers={'User-Agent':'MagicCityPulse/1.0'})
        with urllib.request.urlopen(request,timeout=15) as response: data=response.read()
        if len(data)<1000: raise ValueError('Incomplete asset')
        target.parent.mkdir(exist_ok=True);target.write_bytes(data)
        print('Cached',name)
    except Exception:
        print('Could not cache',name,'— CDN fallback will be used')
