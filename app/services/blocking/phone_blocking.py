from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple
from app.normalization.models import EntityType
from app.normalization.service import EntityNormalizationService
from app.services.blocking.models import CandidatePair


def generate_phone_candidates(phones: List[Dict[str, Any]]) -> List[CandidatePair]:
    """Generates phone candidate pairs using normalized E.164 phone buckets."""
    phone_bucket: Dict[str, Set[str]] = defaultdict(set)
    pair_signals: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    for p in phones:
        pid = str(p.get("id"))
        raw_num = p.get("normalized_number") or p.get("raw_number")
        if not pid or not raw_num:
            continue

        norm = EntityNormalizationService.normalize_phone(raw_num)
        if norm.metadata.get("is_valid") and norm.normalized_value:
            phone_bucket[norm.normalized_value].add(pid)

    for norm_num, pids in phone_bucket.items():
        if len(pids) < 2:
            continue
        pid_list = sorted(list(pids))
        for i in range(len(pid_list)):
            for j in range(i + 1, len(pid_list)):
                pair = (pid_list[i], pid_list[j])
                pair_signals[pair].add("NORMALIZED_PHONE")

    candidates: List[CandidatePair] = []
    for (id1, id2), signals in pair_signals.items():
        candidates.append(
            CandidatePair(
                entity_type=EntityType.PHONE,
                source_entity_id=id1,
                candidate_entity_id=id2,
                blocking_signals=sorted(list(signals))
            )
        )

    return candidates
