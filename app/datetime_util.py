import re
from datetime import timedelta, datetime, UTC
from zoneinfo import ZoneInfo
from time import struct_time
from cron_converter import Cron
from cron_converter.sub_modules.seeker import Seeker

_timespan_pattern = re.compile(r"^\s*(?:(?P<d>[0-9]+)d)?\s*(?:(?P<h>[0-9]+)h)?\s*(?:(?P<m>[0-9]+)m)?\s*(?:(?P<s>[0-9]+)s)?\s*$")
def parse_timespan(s) -> timedelta:
    time_match = _timespan_pattern.match(s)
    if time_match is None:
        raise ValueError(f'unable to parse timedelta string {s}')
    gd = time_match.groupdict()
    return timedelta(
        days=int(gd['d'] or 0),
        hours=int(gd['h'] or 0),
        minutes=int(gd['m'] or 0),
        seconds=int(gd['s'] or 0)
    )

def parse_cron_schedule(s: str, dt: datetime) -> Seeker:
    c = Cron(s)
    return c.schedule(dt)


def validate_timespan_str(s) -> bool:
    return try_parse_timespan(s) is not None

def try_parse_timespan(s) -> timedelta | None:
    try:
        return parse_timespan(s)
    except:
        return None

def validate_cron_str(s) -> bool:
    try:
        Cron(s)
        return True
    except:
        return False

def timedelta_to_str(td: timedelta) -> str:
    total = int(td.total_seconds())

    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")

    return "".join(parts)

def humanize_timedelta(td: timedelta, precise: bool = False) -> str:
    if precise:
        return timedelta_to_str(td)
    total = int(td.total_seconds())
    days, rem = divmod(total, 86400)
    if days:
        hours = rem // 3600
        return f"{days}d" if hours < 12 else f"{days + 1}d"
    hours, rem = divmod(rem, 3600)
    if hours:
        minutes = rem // 60
        return f"{hours}h" if minutes < 30 else f"{hours + 1}h"
    minutes, seconds = divmod(rem, 60)
    if minutes:
        return f"{minutes}m" if seconds < 30 else f"{minutes + 1}m"
    return f"{seconds}s"

def humanize_timedelta2(td: timedelta, precise: bool = False) -> str:
    if precise:
        return timedelta_to_str(td)
    total = int(td.total_seconds())
    days, rem = divmod(total, 86400)
    if days:
        return f"{days}d"
    hours, rem = divmod(rem, 3600)
    if hours:
        return f"{hours}h"
    minutes, seconds = divmod(rem, 60)
    if minutes:
        return f"{minutes}m"
    return f"{seconds}s"


def datetime_to_iso(dt: datetime, convert_to_utc: bool = True) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    if convert_to_utc:
        return dt.astimezone(UTC).isoformat()
    return dt.isoformat()

def humanize_datetime(dt: datetime) -> str:
    return f'{dt:%A, %B %d, %Y %I:%M %p %Z}'

def iso_to_datetime(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt

def tuple9_to_datetime(value: tuple | struct_time) -> datetime:
    if isinstance(value, struct_time):
        value = tuple(value)

    if len(value) < 6:
        raise ValueError(f"invalid 9-tuple (needs at least 6 fields): {value}")

    year, month, day, hour, minute, second = value[:6]

    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)

def now_iso() -> str:
    return datetime_to_iso(now_datetime())

def now_datetime(tz: str = "Etc/UTC") -> datetime:
    return datetime.now(ZoneInfo(tz))


def normalize_datetime(value) -> str:
    if isinstance(value, datetime):
        return datetime_to_iso(value)
    if isinstance(value, str):
        return datetime_to_iso(iso_to_datetime(value))
    if isinstance(value, struct_time) or isinstance(value, tuple):
        return datetime_to_iso(tuple9_to_datetime(value))
    raise TypeError(f"unsupported datetime type: {type(value)}")


def normalize_timedelta(value) -> timedelta:
    if isinstance(value, timedelta):
        return value
    if isinstance(value, str):
        td = try_parse_timespan(value)
        if td is None:
            raise ValueError(f"invalid timespan string: {value}")
        return td
    raise TypeError(f"unsupported timedelta type: {type(value)}")
