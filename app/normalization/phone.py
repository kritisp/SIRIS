import re
from typing import Optional
from app.normalization.models import EntityType, NormalizedEntity


def normalize_phone_number(raw_phone: Optional[str]) -> NormalizedEntity:
    """Normalizes Indian phone numbers into canonical E.164 (+91XXXXXXXXXX) representation."""
    if not raw_phone or not raw_phone.strip():
        return NormalizedEntity(
            entity_type=EntityType.PHONE,
            raw_value=raw_phone or "",
            normalized_value="",
            metadata={"is_valid": False, "reason": "empty_input"}
        )

    # 1. Strip non-digits except leading '+'
    digits = re.sub(r"[^\d]", "", raw_phone)

    country_code = "+91"
    national_number = ""
    is_valid = False

    if len(digits) == 10:
        national_number = digits
        is_valid = True
    elif len(digits) == 11 and digits.startswith("0"):
        national_number = digits[1:]
        is_valid = True
    elif len(digits) == 12 and digits.startswith("91"):
        national_number = digits[2:]
        is_valid = True
    elif len(digits) > 10 and digits[-10:]:
        national_number = digits[-10:]
        is_valid = True
    else:
        national_number = digits
        is_valid = False

    canonical = f"{country_code}{national_number}" if is_valid else digits

    return NormalizedEntity(
        entity_type=EntityType.PHONE,
        raw_value=raw_phone,
        normalized_value=canonical,
        tokens=[national_number] if is_valid else [digits],
        metadata={
            "country_code": country_code,
            "national_number": national_number,
            "is_valid": is_valid,
            "digit_length": len(digits)
        }
    )
