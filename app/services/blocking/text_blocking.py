from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple
from app.normalization.models import EntityType
from app.normalization.service import EntityNormalizationService
from app.services.blocking.models import CandidatePair


def generate_mo_candidates(cases: List[Dict[str, Any]]) -> List[CandidatePair]:
    """Generates candidate case pairs sharing MO keyword tokens or crime category buckets."""
    buckets: Dict[str, Dict[str, Set[str]]] = {
        "CRIME_CATEGORY": defaultdict(set),
        "MO_KEYWORD_TOKEN": defaultdict(set),
    }

    pair_signals: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    for c in cases:
        cid = str(c.get("id"))
        desc = c.get("description")
        category = c.get("crime_category")
        if not cid:
            continue

        if category:
            buckets["CRIME_CATEGORY"][category.lower().strip()].add(cid)

        if desc:
            norm_mo = EntityNormalizationService.normalize_mo(desc)
            for token in norm_mo.tokens:
                if len(token) >= 4:
                    buckets["MO_KEYWORD_TOKEN"][token].add(cid)

    for signal_name, bucket_dict in buckets.items():
        for key, cids in bucket_dict.items():
            if len(cids) < 2 or len(cids) > 100:  # Cap max bucket size to prevent excessive pairs
                continue
            cid_list = sorted(list(cids))
            for i in range(len(cid_list)):
                for j in range(i + 1, len(cid_list)):
                    pair = (cid_list[i], cid_list[j])
                    pair_signals[pair].add(signal_name)

    candidates: List[CandidatePair] = []
    for (id1, id2), signals in pair_signals.items():
        candidates.append(
            CandidatePair(
                entity_type=EntityType.MO,
                source_entity_id=id1,
                candidate_entity_id=id2,
                blocking_signals=sorted(list(signals))
            )
        )

    return candidates
