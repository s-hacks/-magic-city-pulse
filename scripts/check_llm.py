"""Run a tiny real provider probe; save only safe diagnostic metadata."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from scripts.build_dataset import DATA, atomic_json

app.pulse.llm('Reply with the single word OK.', 'Connection check')
status=app.pulse.provider_status()
atomic_json(DATA/'llm_probe.json',status)
print(json.dumps(status,indent=2))
