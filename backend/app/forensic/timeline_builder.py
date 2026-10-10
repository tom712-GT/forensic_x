import datetime
import hashlib
from typing import Optional, Any

def parse_to_datetime(ts: Any) -> tuple[Optional[datetime.datetime], str]:
    if ts is None:
        return None, "ABSENT"
    if not isinstance(ts, str):
        return None, "UNPARSEABLE_TIMESTAMP"
    ts = ts.strip()
    if not ts:
        return None, "ABSENT"
        
    try:
        dt = datetime.datetime.fromisoformat(ts)
        
        flags = ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
            flags = "TIMEZONE_ASSUMED_UTC"
        else:
            dt = dt.astimezone(datetime.timezone.utc)
            
        return dt, flags
    except (ValueError, OverflowError, TypeError):
        return None, "UNPARSEABLE_TIMESTAMP"

def format_timestamp(dt: datetime.datetime) -> str:
    ms = dt.microsecond
    if ms == 0:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def parse_timestamp(ts: Any) -> tuple[Optional[str], str]:
    dt, flags = parse_to_datetime(ts)
    if dt is None:
        return None, flags
    if dt.year < 1 or dt.year > 9999:
        return None, "UNPARSEABLE_TIMESTAMP"
    return format_timestamp(dt), flags

def build_event_id(kind: str, evidence_id: str, source_key: str) -> str:
    h = hashlib.sha256(f"{kind}|{evidence_id}|{source_key}".encode("utf-8")).hexdigest()
    return h[:16].lower()

def sort_key(event: dict) -> tuple:
    # time_source rank: TOOL_CLOCK=0 < USER_DECLARED=1 < CONTAINER_CLAIM=2
    ranks = {"TOOL_CLOCK": 0, "USER_DECLARED": 1, "CONTAINER_CLAIM": 2}
    rank = ranks.get(event["time_source"], 3)
    return (event.get("dt", event.get("timestamp")), rank, event["kind"], event["event_id"])
