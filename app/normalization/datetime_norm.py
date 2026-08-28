from datetime import date, datetime, time
from typing import Any, Dict, Optional, Union
from app.normalization.models import EntityType, NormalizedEntity


def normalize_datetime(raw_dt: Optional[Union[date, datetime, time, str]]) -> NormalizedEntity:
    """Normalizes dates, times, and timestamps into canonical ISO-8601 strings and Unix epoch metadata."""
    if raw_dt is None:
        return NormalizedEntity(
            entity_type=EntityType.DATETIME,
            raw_value="",
            normalized_value="",
            tokens=[],
            metadata={"is_empty": True}
        )

    norm_val = ""
    metadata: Dict[str, Any] = {}
    tokens = []

    if isinstance(raw_dt, datetime):
        norm_val = raw_dt.isoformat()
        metadata = {
            "year": raw_dt.year,
            "month": raw_dt.month,
            "day": raw_dt.day,
            "hour": raw_dt.hour,
            "epoch": int(raw_dt.timestamp()),
            "type": "datetime",
        }
        tokens = [str(raw_dt.year), f"{raw_dt.year:04d}-{raw_dt.month:02d}"]
    elif isinstance(raw_dt, date):
        norm_val = raw_dt.strftime("%Y-%m-%d")
        metadata = {
            "year": raw_dt.year,
            "month": raw_dt.month,
            "day": raw_dt.day,
            "type": "date",
        }
        tokens = [str(raw_dt.year), f"{raw_dt.year:04d}-{raw_dt.month:02d}"]
    elif isinstance(raw_dt, time):
        norm_val = raw_dt.strftime("%H:%M:%S")
        metadata = {
            "hour": raw_dt.hour,
            "minute": raw_dt.minute,
            "type": "time",
        }
        tokens = [f"{raw_dt.hour:02d}:00"]
    else:
        s = str(raw_dt).strip()
        norm_val = s
        metadata = {"type": "string"}
        tokens = [s]

    return NormalizedEntity(
        entity_type=EntityType.DATETIME,
        raw_value=str(raw_dt),
        normalized_value=norm_val,
        tokens=tokens,
        metadata=metadata
    )
