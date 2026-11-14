"""Small, non-executing .env loader; process environment always takes precedence."""
import os
from pathlib import Path
import re
import shlex


def load_env(path=None):
    path = Path(path) if path is not None else Path(__file__).resolve().parent / '.env'
    try:
        lines = path.read_text(encoding='utf-8-sig').splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            continue
        try:
            parts = shlex.split(value, comments=True, posix=True)
        except ValueError:
            continue
        # No shell execution or ${...} expansion, including in quoted values.
        os.environ.setdefault(key, ' '.join(parts))
