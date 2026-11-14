from datetime import datetime
from zoneinfo import ZoneInfo

# Published seed service windows; no inference of hours for federal records.
WINDOWS = {
    'First Light': (range(7), [(0,1440)]),
    'Jimmie Hale': (range(7), [(930,1050)]),
    'Urban Ministry': ([1,3], [(540,720)]),
    'First United': ([2,4], [(600,780)]),
    'Community Kitchens': (range(7), [(690,750)]),
    'Church of the Highlands': ([5], [(540,690)]),
    'Christian Service': (range(5), [(510,930)]),
    'Christ Health': (range(5), [(450,1020)]),
}


def active_status(r):
    current=datetime.now(ZoneInfo('America/Chicago'))
    if r.get('provider_confirmed'):
        stamp=datetime.fromisoformat(r['confirmed_at']).astimezone(ZoneInfo('America/Chicago'))
        return r['status'] if stamp.date()==current.date() else 'limited'
    if r.get('is_demo') and not r.get('volunteer_updated'):
        return r['status']
    if r.get('volunteer_updated'):
        stamp=datetime.fromisoformat(r['last_verified']).astimezone(ZoneInfo('America/Chicago'))
        return r['status'] if stamp.date()==current.date() else 'limited'
    for prefix,(days,windows) in WINDOWS.items():
        if r['name'].startswith(prefix):
            minute=current.hour*60+current.minute
            return 'open' if current.weekday() in days and any(a<=minute<b for a,b in windows) else 'closed'
    return 'limited'



def scheduled_status(resource, when):
    """Check a requested Chicago service time; unknown/demo hours stay unconfirmed."""
    if when.tzinfo: when=when.astimezone(ZoneInfo('America/Chicago'))
    if resource.get('is_demo') or resource.get('volunteer_updated') or resource.get('provider_confirmed'):
        return 'limited'
    for prefix,(days,windows) in WINDOWS.items():
        if resource['name'].startswith(prefix):
            minute=when.hour*60+when.minute
            return 'open' if when.weekday() in days and any(a<=minute<b for a,b in windows) else 'closed'
    return 'limited'
