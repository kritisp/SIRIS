from typing import Any, Dict
from app.normalization.models import EntityType
from app.normalization.service import EntityNormalizationService
from app.services.resolution.models import (
    ResolutionDecision,
    ResolutionResult,
    SignalEvidence,
    SignalStatus,
)


def resolve_vehicle_pair(v1: Dict[str, Any], v2: Dict[str, Any]) -> ResolutionResult:
    """Deterministic vehicle candidate pair resolution based on canonical registration equality."""
    id1 = str(v1.get("id"))
    id2 = str(v2.get("id"))

    reg1 = v1.get("registration_number")
    reg2 = v2.get("registration_number")

    norm1 = EntityNormalizationService.normalize_vehicle(reg1)
    norm2 = EntityNormalizationService.normalize_vehicle(reg2)

    is_match = (
        norm1.metadata.get("is_valid")
        and norm2.metadata.get("is_valid")
        and norm1.normalized_value == norm2.normalized_value
    )

    score = 1.0 if is_match else 0.0
    decision = ResolutionDecision.HIGH_CONFIDENCE_MATCH if is_match else ResolutionDecision.NO_MATCH

    signal = SignalEvidence(
        name="EXACT_VEHICLE_REGISTRATION_MATCH",
        raw_score=score,
        weight=1.0,
        weighted_score=score,
        status=SignalStatus.MATCH if is_match else SignalStatus.CONFLICT,
        description=f"Canonical reg match: {norm1.normalized_value}" if is_match else "Registration mismatch"
    )

    return ResolutionResult(
        source_entity_id=id1,
        candidate_entity_id=id2,
        entity_type=EntityType.VEHICLE,
        overall_score=score,
        decision=decision,
        matching_signals=[signal] if is_match else [],
        conflicting_signals=[signal] if not is_match else [],
        unavailable_signals=[],
        explanation=f"{decision.value} (Score: {score:.2f})."
    )
