from . import datetime_util as dt
from datetime import datetime

def _normalize_and_humanize_datetime(d: str | datetime) -> str:
    if isinstance(d, str):
        return dt.humanize_datetime(dt.iso_to_datetime(d))
    return dt.humanize_datetime(d)

def _relative_time(d: str | datetime) -> str:
    if isinstance(d, str):
        d = dt.iso_to_datetime(d)
    now = dt.now_datetime()
    delta = d - now
    if delta.total_seconds() < 0:
        return f'{dt.humanize_timedelta(-delta)} ago'
    return f'in {dt.humanize_timedelta(delta)}'

def add_filters(templates):
    templates.env.filters['datetime'] = _normalize_and_humanize_datetime
    templates.env.filters['reltime'] = _relative_time
    templates.env.filters['timespan'] = dt.humanize_timedelta
