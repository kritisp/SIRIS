from typing import List, Tuple
from app.config.settings import settings
from app.services.resolution.models import (
    ResolutionDecision,
    SignalEvidence,
    SignalStatus,
)


def compute_evidence_score(
    signals: List[SignalEvidence],
    unavailable: List[str]
) -> Tuple[float, ResolutionDecision, str]:
    """Computes evidence-aware normalized score, evaluates decision threshold, and generates explanation."""

    matching = [s for s in signals if s.status == SignalStatus.MATCH]
    conflicts = [s for s in signals if s.status == SignalStatus.CONFLICT]

    # Calculate total weight of available signals
    available_weight = sum(s.weight for s in signals)
    if available_weight == 0.0:
        return 0.0, ResolutionDecision.NO_MATCH, "Insufficient evidence available for resolution."

    # Sum of weighted scores from matching signals
    raw_weighted_sum = sum(s.weighted_score for s in matching)

    # Normalize by total available weight so missing attributes are not penalized heavily
    normalized_score = min(1.0, max(0.0, raw_weighted_sum / available_weight))

    # Apply explicit conflict penalty if strong contradictions exist (e.g. conflicting DOB or phone)
    conflict_penalty = 0.0
    for c in conflicts:
        if c.name in ("DOB_MATCH", "PHONE_MATCH"):
            conflict_penalty += 0.25
        else:
            conflict_penalty += 0.10

    final_score = min(1.0, max(0.0, normalized_score - conflict_penalty))
    final_score = round(final_score, 4)

    # Threshold evaluation
    if final_score >= settings.THRESHOLD_HIGH_CONFIDENCE:
        decision = ResolutionDecision.HIGH_CONFIDENCE_MATCH
    elif final_score >= settings.THRESHOLD_POSSIBLE_MATCH:
        decision = ResolutionDecision.POSSIBLE_MATCH
    else:
        decision = ResolutionDecision.NO_MATCH

    # Human-readable evidence explanation
    match_names = [s.name for s in matching]
    conflict_names = [s.name for s in conflicts]

    exp_parts = []
    if match_names:
        exp_parts.append(f"Matching Evidence: {', '.join(match_names)}")
    if conflict_names:
        exp_parts.append(f"Conflicting Evidence: {', '.join(conflict_names)}")
    if unavailable:
        exp_parts.append(f"Unavailable Attributes: {', '.join(unavailable)}")

    explanation = f"{decision.value} (Score: {final_score:.2f}). " + " | ".join(exp_parts)

    return final_score, decision, explanation
