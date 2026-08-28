from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple
from app.normalization.models import EntityType
from app.normalization.service import EntityNormalizationService
from app.services.blocking.models import CandidatePair


def generate_person_candidates(persons: List[Dict[str, Any]]) -> List[CandidatePair]:
    """Generates person candidate pairs using multi-signal inverted index buckets."""
    buckets: Dict[str, Dict[str, Set[str]]] = {
        "EXACT_NAME": defaultdict(set),
        "PHONETIC_NAME": defaultdict(set),
        "SURNAME": defaultdict(set),
        "DOB_YEAR": defaultdict(set),
    }

    # Store signals per pair (id1, id2) where id1 < id2
    pair_signals: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    for p in persons:
        pid = str(p.get("id"))
        raw_name = p.get("name")
        if not pid or not raw_name:
            continue

        norm = EntityNormalizationService.normalize_person(raw_name)
        if not norm.normalized_value:
            continue

        # 1. Exact Name Bucket
        buckets["EXACT_NAME"][norm.normalized_value].add(pid)

        # 2. Phonetic Bucket
        if norm.phonetic_value:
            buckets["PHONETIC_NAME"][norm.phonetic_value].add(pid)

        # 3. Surname Bucket
        if norm.tokens and len(norm.tokens) >= 2:
            surname = norm.tokens[-1]
            if len(surname) >= 3:
                buckets["SURNAME"][surname].add(pid)

        # 4. DOB Year Bucket
        dob = p.get("date_of_birth")
        if dob:
            year_str = str(dob.year) if hasattr(dob, "year") else str(dob)[:4]
            if year_str.isdigit():
                buckets["DOB_YEAR"][year_str].add(pid)

    # Collect pairs from buckets
    for signal_name, bucket_dict in buckets.items():
        for key, pids in bucket_dict.items():
            if len(pids) < 2:
                continue
            pid_list = sorted(list(pids))
            for i in range(len(pid_list)):
                for j in range(i + 1, len(pid_list)):
                    pair = (pid_list[i], pid_list[j])
                    pair_signals[pair].add(signal_name)

    candidates: List[CandidatePair] = []
    for (id1, id2), signals in pair_signals.items():
        candidates.append(
            CandidatePair(
                entity_type=EntityType.PERSON,
                source_entity_id=id1,
                candidate_entity_id=id2,
                blocking_signals=sorted(list(signals))
            )
        )

    return candidates
