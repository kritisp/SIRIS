import re
from typing import Optional
from app.normalization.models import EntityType, NormalizedEntity


def normalize_vehicle_registration(raw_reg: Optional[str]) -> NormalizedEntity:
    """Normalizes Indian vehicle registration numbers into canonical OD02AB1234 format and extracts RTO metadata."""
    if not raw_reg or not raw_reg.strip():
        return NormalizedEntity(
            entity_type=EntityType.VEHICLE,
            raw_value=raw_reg or "",
            normalized_value="",
            metadata={"is_valid": False, "reason": "empty_input"}
        )

    # 1. Uppercase & strip non-alphanumeric characters
    clean = re.sub(r"[^A-Z0-9]", "", raw_reg.upper().strip())

    # Standard Indian pattern: 2 letters (state) + 2 digits (rto) + 1-3 letters (series) + 4 digits (number)
    # e.g., OD02AB1234 or OD02A1234
    pattern = r"^([A-Z]{2})([0-9]{2})([A-Z]{1,3})([0-9]{4})$"
    match = re.match(pattern, clean)

    if match:
        state_code, rto_code, series, reg_num = match.groups()
        canonical = f"{state_code}{rto_code}{series}{reg_num}"
        metadata = {
            "state_code": state_code,
            "rto_code": rto_code,
            "series": series,
            "registration_number": reg_num,
            "is_valid": True,
        }
        tokens = [state_code, f"{state_code}{rto_code}", series, reg_num]
    else:
        canonical = clean
        metadata = {"is_valid": False, "raw_clean": clean}
        tokens = [clean]

    return NormalizedEntity(
        entity_type=EntityType.VEHICLE,
        raw_value=raw_reg,
        normalized_value=canonical,
        tokens=tokens,
        metadata=metadata
    )
