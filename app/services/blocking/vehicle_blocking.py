from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple
from app.normalization.models import EntityType
from app.normalization.service import EntityNormalizationService
from app.services.blocking.models import CandidatePair


def generate_vehicle_candidates(vehicles: List[Dict[str, Any]]) -> List[CandidatePair]:
    """Generates vehicle candidate pairs using normalized registration buckets."""
    buckets: Dict[str, Dict[str, Set[str]]] = {
        "NORMALIZED_VEHICLE": defaultdict(set),
        "RTO_SERIES": defaultdict(set),
    }

    pair_signals: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    for v in vehicles:
        vid = str(v.get("id"))
        raw_reg = v.get("registration_number")
        if not vid or not raw_reg:
            continue

        norm = EntityNormalizationService.normalize_vehicle(raw_reg)
        if not norm.normalized_value:
            continue

        # 1. Exact Vehicle Bucket
        buckets["NORMALIZED_VEHICLE"][norm.normalized_value].add(vid)

        # 2. RTO Series Bucket
        if norm.metadata.get("is_valid"):
            rto_key = f"{norm.metadata.get('state_code')}_{norm.metadata.get('rto_code')}_{norm.metadata.get('series')}"
            buckets["RTO_SERIES"][rto_key].add(vid)

    for signal_name, bucket_dict in buckets.items():
        for key, vids in bucket_dict.items():
            if len(vids) < 2:
                continue
            vid_list = sorted(list(vids))
            for i in range(len(vid_list)):
                for j in range(i + 1, len(vid_list)):
                    pair = (vid_list[i], vid_list[j])
                    pair_signals[pair].add(signal_name)

    candidates: List[CandidatePair] = []
    for (id1, id2), signals in pair_signals.items():
        candidates.append(
            CandidatePair(
                entity_type=EntityType.VEHICLE,
                source_entity_id=id1,
                candidate_entity_id=id2,
                blocking_signals=sorted(list(signals))
            )
        )

    return candidates
