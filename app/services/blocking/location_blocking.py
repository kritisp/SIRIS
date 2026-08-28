from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple
from app.normalization.models import EntityType
from app.normalization.service import EntityNormalizationService
from app.services.blocking.models import CandidatePair


def generate_location_candidates(locations: List[Dict[str, Any]]) -> List[CandidatePair]:
    """Generates location candidate pairs using normalized locality and district buckets."""
    buckets: Dict[str, Dict[str, Set[str]]] = {
        "NORMALIZED_LOCALITY": defaultdict(set),
        "DISTRICT": defaultdict(set),
    }

    pair_signals: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    for loc in locations:
        lid = str(loc.get("id"))
        raw_loc = loc.get("locality") or loc.get("address")
        if not lid or not raw_loc:
            continue

        norm = EntityNormalizationService.normalize_location(raw_loc)
        if norm.normalized_value:
            buckets["NORMALIZED_LOCALITY"][norm.normalized_value].add(lid)

        district = loc.get("district")
        if district:
            buckets["DISTRICT"][district.lower().strip()].add(lid)

    for signal_name, bucket_dict in buckets.items():
        for key, lids in bucket_dict.items():
            if len(lids) < 2:
                continue
            lid_list = sorted(list(lids))
            for i in range(len(lid_list)):
                for j in range(i + 1, len(lid_list)):
                    pair = (lid_list[i], lid_list[j])
                    pair_signals[pair].add(signal_name)

    candidates: List[CandidatePair] = []
    for (id1, id2), signals in pair_signals.items():
        candidates.append(
            CandidatePair(
                entity_type=EntityType.LOCATION,
                source_entity_id=id1,
                candidate_entity_id=id2,
                blocking_signals=sorted(list(signals))
            )
        )

    return candidates
