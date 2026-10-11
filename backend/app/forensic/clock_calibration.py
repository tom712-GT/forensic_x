import datetime

MAX_OFFSET_SECONDS = 315360000
MAX_UNCERTAINTY_SECONDS = 31536000

def compute_offset(device_dt: datetime.datetime, reference_dt: datetime.datetime) -> float:
    diff = (reference_dt - device_dt).total_seconds()
    return round(diff, 6)

def apply_offset(dt: datetime.datetime, offset_seconds: float, uncertainty_seconds: float):
    # offset_seconds = reference - device
    # corrected = device + offset
    try:
        offset_td = datetime.timedelta(seconds=offset_seconds)
        nominal = dt + offset_td
        
        uncertainty_td = datetime.timedelta(seconds=uncertainty_seconds)
        earliest = nominal - uncertainty_td
        latest = nominal + uncertainty_td
        
        return nominal, earliest, latest
    except (OverflowError, ValueError):
        raise OverflowError("Time out of range")
        
def within_plausible_years(dt: datetime.datetime, min_year: int, max_year: int) -> bool:
    if dt.year < min_year or dt.year > max_year:
        return False
    return True
