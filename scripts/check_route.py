"""Probe pedestrian routing with public downtown coordinates, not a user's location."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import routing
from scripts.build_dataset import DATA, atomic_json, now
import json
resource={'id':'public-downtown-test','lat':33.5198,'lon':-86.8041,'is_demo':False}
result=routing.route((33.5165,-86.8091),resource)
report={'checked_at':now(),'available':result['available'],'message':result['message'],
        'distance_m':result.get('distance_m'),'duration_s':result.get('duration_s')}
atomic_json(DATA/'route_probe.json',report)
print(json.dumps(report,indent=2))
