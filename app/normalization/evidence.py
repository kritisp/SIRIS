import re
import unicodedata
from typing import Optional
from app.normalization.models import EntityType, NormalizedEntity


def normalize_evidence_description(raw_text: Optional[str]) -> NormalizedEntity:
    """Normalizes evidence, weapon, and stolen property descriptions into canonical comparison tokens."""
    if not raw_text or not raw_text.strip():
        return NormalizedEntity(
            entity_type=EntityType.EVIDENCE,
            raw_value=raw_text or "",
            normalized_value="",
            tokens=[],
            metadata={"is_empty": True}
        )

    clean = raw_text.strip()
    clean = unicodedata.normalize("NFKD", clean).encode("ASCII", "ignore").decode("utf-8")
    clean = re.sub(r"[^\w\s]", " ", clean.lower())
    tokens = re.sub(r"\s+", " ", clean).strip().split()

    norm_value = " ".join(tokens)

    return NormalizedEntity(
        entity_type=EntityType.EVIDENCE,
        raw_value=raw_text,
        normalized_value=norm_value,
        tokens=tokens,
        metadata={"token_count": len(tokens)}
    )
