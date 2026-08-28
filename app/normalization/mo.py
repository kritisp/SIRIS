import re
import unicodedata
from typing import Dict, List, Optional
from app.normalization.models import EntityType, NormalizedEntity

STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "from", "by", "with", "of", "for",
    "was", "were", "been", "is", "are", "using", "via", "through"
}

SYNONYMS: Dict[str, str] = {
    "entry": "enter",
    "entered": "enter",
    "entering": "enter",
    "broken": "break",
    "breaking": "break",
    "broke": "break",
    "cut": "cutting",
    "cutter": "cutting",
    "stolen": "theft",
    "stealing": "theft",
}


def normalize_modus_operandi(raw_mo: Optional[str]) -> NormalizedEntity:
    """Normalizes Modus Operandi text into canonical comparison tokens and standardized terminology."""
    if not raw_mo or not raw_mo.strip():
        return NormalizedEntity(
            entity_type=EntityType.MO,
            raw_value=raw_mo or "",
            normalized_value="",
            tokens=[],
            metadata={"is_empty": True}
        )

    clean = raw_mo.strip()
    clean = unicodedata.normalize("NFKD", clean).encode("ASCII", "ignore").decode("utf-8")
    clean = re.sub(r"[^\w\s]", " ", clean.lower())
    words = re.sub(r"\s+", " ", clean).strip().split()

    tokens: List[str] = []
    for w in words:
        if w in STOP_WORDS:
            continue
        token = SYNONYMS.get(w, w)
        tokens.append(token)

    norm_value = " ".join(tokens)

    return NormalizedEntity(
        entity_type=EntityType.MO,
        raw_value=raw_mo,
        normalized_value=norm_value,
        tokens=tokens,
        metadata={"original_word_count": len(words), "normalized_token_count": len(tokens)}
    )
