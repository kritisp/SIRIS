import re
import unicodedata
from typing import Dict, List, Optional, Tuple
from app.normalization.models import EntityType, NormalizedEntity

TITLES = {
    "shri", "smt", "mr", "mrs", "ms", "dr", "advocate", "adv", "inspector", "si", "asi",
    "shree", "miss", "late", "babu", "master"
}


def compute_soundex(name: str) -> str:
    """Computes standard Soundex code adapted for name token phonetic representation."""
    name = re.sub(r"[^a-zA-Z]", "", name.upper())
    if not name:
        return ""

    first_char = name[0]
    char_map = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6'
    }

    code = first_char
    prev_digit = char_map.get(first_char, '')

    for char in name[1:]:
        digit = char_map.get(char, '')
        if digit and digit != prev_digit:
            code += digit
            prev_digit = digit
        elif not digit:
            prev_digit = ''

    return (code + "000")[:4]


def normalize_person_name(raw_name: Optional[str]) -> NormalizedEntity:
    """Normalizes person names with title stripping, initials handling, alias parsing, and Soundex encoding."""
    if not raw_name or not raw_name.strip():
        return NormalizedEntity(
            entity_type=EntityType.PERSON,
            raw_value=raw_name or "",
            normalized_value="",
            phonetic_value="",
            tokens=[],
            metadata={"is_empty": True}
        )

    clean = raw_name.strip()

    # 1. Unicode NFKD normalization
    clean = unicodedata.normalize("NFKD", clean).encode("ASCII", "ignore").decode("utf-8")

    # 2. Extract alias if present (e.g., "Rahul Kumar alias Raju")
    alias: Optional[str] = None
    alias_match = re.search(r"\balias\b\s+(.*)$", clean, re.IGNORECASE)
    if alias_match:
        alias = alias_match.group(1).strip().lower()
        clean = clean[:alias_match.start()].strip()

    # 3. Lowercase & remove punctuation except whitespace
    clean = re.sub(r"[^\w\s]", " ", clean.lower())
    clean = re.sub(r"\s+", " ", clean).strip()

    # 4. Filter titles
    words = clean.split()
    filtered_words = [w for w in words if w not in TITLES]
    if not filtered_words:
        filtered_words = words

    norm_value = " ".join(filtered_words)

    # 5. Phonetic codes for tokens
    phonetics = [compute_soundex(w) for w in filtered_words if w]
    phonetic_val = "-".join([p for p in phonetics if p])

    metadata: Dict[str, Any] = {
        "word_count": len(filtered_words),
        "has_initials": any(len(w) == 1 for w in filtered_words),
    }
    if alias:
        metadata["alias"] = alias
        metadata["alias_phonetic"] = compute_soundex(alias)

    return NormalizedEntity(
        entity_type=EntityType.PERSON,
        raw_value=raw_name,
        normalized_value=norm_value,
        phonetic_value=phonetic_val,
        tokens=filtered_words,
        metadata=metadata
    )
