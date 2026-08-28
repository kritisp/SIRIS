from typing import Any, Dict
from app.normalization.models import EntityType
from app.normalization.service import EntityNormalizationService
from app.services.resolution.models import (
    ResolutionDecision,
    ResolutionResult,
    SignalEvidence,
    SignalStatus,
)


def resolve_phone_pair(p1: Dict[str, Any], p2: Dict[str, Any]) -> ResolutionResult:
    """Deterministic phone candidate pair resolution based on E.164 normalized equality."""
    id1 = str(p1.get("id"))
    id2 = str(p2.get("id"))

    raw1 = p1.get("normalized_number") or p1.get("raw_number")
    raw2 = p2.get("normalized_number") or p2.get("raw_number")

    norm1 = EntityNormalizationService.normalize_phone(raw1)
    norm2 = EntityNormalizationService.normalize_phone(raw2)

    is_match = (
        norm1.metadata.get("is_valid")
        and norm2.metadata.get("is_valid")
        and norm1.normalized_value == norm2.normalized_value
    )

    score = 1.0 if is_match else 0.0
    decision = ResolutionDecision.HIGH_CONFIDENCE_MATCH if is_match else ResolutionDecision.NO_MATCH

    signal = SignalEvidence(
        name="EXACT_E164_PHONE_MATCH",
        raw_score=score,
        weight=1.0,
        weighted_score=score,
        status=SignalStatus.MATCH if is_match else SignalStatus.CONFLICT,
        description="E.164 Canonical Phone Match" if is_match else "Phone mismatch"
    )

    matching = [signal] if is_match else []
    conflicting = [signal] if not is_match else []

    return ResolutionResult(
        source_entity_id=id1,
        candidate_entity_id=id2,
        entity_type=EntityType.PHONE,
        overall_score=score,
        decision=decision,
        matching_signals=matching,
        conflicting_signals=conflicting,
        unavailable_signals=[],
        explanation=f"{decision.value} (Score: {score:.2f})."
    )
