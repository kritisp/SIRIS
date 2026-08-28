import re
import unicodedata
from typing import Dict, List, Optional
from app.normalization.models import EntityType, NormalizedEntity

LOCATION_ABBREVIATIONS: Dict[str, str] = {
    "ps": "police station",
    "p.s.": "police station",
    "chhak": "square",
    "chok": "square",
    "sq": "square",
    "sqr": "square",
    "rd": "road",
    "st": "street",
    "bhub": "bhubaneswar",
    "bbsr": "bhubaneswar",
    "ctc": "cuttack",
    "puri": "puri",
    "sbp": "sambalpur",
    "rkl": "rourkela",
    "dist": "district",
    "nr": "near",
}


def normalize_location_text(raw_location: Optional[str]) -> NormalizedEntity:
    """Normalizes location text by cleaning whitespace, punctuation, and expanding common police/locality abbreviations."""
    if not raw_location or not raw_location.strip():
        return NormalizedEntity(
            entity_type=EntityType.LOCATION,
            raw_value=raw_location or "",
            normalized_value="",
            tokens=[],
            metadata={"is_empty": True}
        )

    clean = raw_location.strip()
    clean = unicodedata.normalize("NFKD", clean).encode("ASCII", "ignore").decode("utf-8")
    clean = re.sub(r"[^\w\s]", " ", clean.lower())
    words = re.sub(r"\s+", " ", clean).strip().split()

    expanded_tokens: List[str] = []
    for w in words:
        expanded_tokens.append(LOCATION_ABBREVIATIONS.get(w, w))

    norm_value = " ".join(expanded_tokens)

    return NormalizedEntity(
        entity_type=EntityType.LOCATION,
        raw_value=raw_location,
        normalized_value=norm_value,
        tokens=expanded_tokens,
        metadata={"token_count": len(expanded_tokens)}
    )
