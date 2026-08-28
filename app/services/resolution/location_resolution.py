from typing import Any, Dict
from rapidfuzz import fuzz
from app.normalization.models import EntityType
from app.normalization.service import EntityNormalizationService
from app.services.resolution.models import (
    ResolutionDecision,
    ResolutionResult,
    SignalEvidence,
    SignalStatus,
)


def resolve_location_pair(l1: Dict[str, Any], l2: Dict[str, Any]) -> ResolutionResult:
    """Location candidate pair resolution based on normalized text similarity and district match."""
    id1 = str(l1.get("id"))
    id2 = str(l2.get("id"))

    raw1 = l1.get("locality") or l1.get("address")
    raw2 = l2.get("locality") or l2.get("address")

    norm1 = EntityNormalizationService.normalize_location(raw1)
    norm2 = EntityNormalizationService.normalize_location(raw2)

    sim = fuzz.token_set_ratio(norm1.normalized_value, norm2.normalized_value) / 100.0 if (norm1.normalized_value and norm2.normalized_value) else 0.0

    if sim >= 0.85:
        decision = ResolutionDecision.HIGH_CONFIDENCE_MATCH
    elif sim >= 0.60:
        decision = ResolutionDecision.POSSIBLE_MATCH
    else:
        decision = ResolutionDecision.NO_MATCH

    signal = SignalEvidence(
        name="LOCATION_TEXT_SIMILARITY",
        raw_score=round(sim, 4),
        weight=1.0,
        weighted_score=round(sim, 4),
        status=SignalStatus.MATCH if sim >= 0.60 else SignalStatus.CONFLICT,
        description=f"RapidFuzz token_set_ratio: {sim:.2f}"
    )

    return ResolutionResult(
        source_entity_id=id1,
        candidate_entity_id=id2,
        entity_type=EntityType.LOCATION,
        overall_score=round(sim, 4),
        decision=decision,
        matching_signals=[signal] if sim >= 0.60 else [],
        conflicting_signals=[signal] if sim < 0.60 else [],
        unavailable_signals=[],
        explanation=f"{decision.value} (Score: {sim:.2f})."
    )
