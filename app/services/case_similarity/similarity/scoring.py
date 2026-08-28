from typing import List, Tuple
from app.config.settings import settings
from app.services.case_similarity.similarity.models import (
    CaseSimilarityResult,
    CaseSimilaritySignal,
    SignalStatus,
    SimilarityLevel,
)


def compute_case_similarity_score(
    source_case_id: str,
    candidate_case_id: str,
    signals: List[CaseSimilaritySignal]
) -> CaseSimilarityResult:
    """Aggregates multi-signal similarity, normalizes score by available evidence weight, and determines similarity level."""

    # Handle Self-Comparison
    if source_case_id == candidate_case_id:
        return CaseSimilarityResult(
            source_case_id=source_case_id,
            candidate_case_id=candidate_case_id,
            overall_score=1.0,
            similarity_level=SimilarityLevel.SELF_COMPARISON,
            signals=signals,
            strongest_evidence=["Self-comparison: Same case record"],
            explanation="SELF_COMPARISON (Score: 1.00). Source and candidate case are identical."
        )

    available_signals = [s for s in signals if s.status != SignalStatus.UNAVAILABLE]
    available_weight = sum(s.weight for s in available_signals)

    # Insufficient Data Check
    if available_weight < 0.20:
        return CaseSimilarityResult(
            source_case_id=source_case_id,
            candidate_case_id=candidate_case_id,
            overall_score=0.0,
            similarity_level=SimilarityLevel.INSUFFICIENT_DATA,
            signals=signals,
            strongest_evidence=[],
            explanation="INSUFFICIENT_DATA (Score: 0.00). Total available signal weight is below threshold."
        )

    raw_weighted_sum = sum(s.weighted_score for s in available_signals)
    normalized_score = min(1.0, max(0.0, raw_weighted_sum / available_weight))
    normalized_score = round(normalized_score, 4)

    # Evaluate Threshold
    if normalized_score >= settings.THRESHOLD_HIGH_SIMILARITY:
        level = SimilarityLevel.HIGH_SIMILARITY
    elif normalized_score >= settings.THRESHOLD_MODERATE_SIMILARITY:
        level = SimilarityLevel.MODERATE_SIMILARITY
    else:
        level = SimilarityLevel.LOW_SIMILARITY

    # Collect strongest evidence strings
    strongest_evidence: List[str] = []
    for s in available_signals:
        if s.status in (SignalStatus.MATCH, SignalStatus.PARTIAL) and s.evidence:
            strongest_evidence.extend(s.evidence)

    # Deterministic explanation
    matched_names = [s.signal_name for s in available_signals if s.status == SignalStatus.MATCH]
    partial_names = [s.signal_name for s in available_signals if s.status == SignalStatus.PARTIAL]
    mismatch_names = [s.signal_name for s in available_signals if s.status == SignalStatus.MISMATCH]
    unavail_names = [s.signal_name for s in signals if s.status == SignalStatus.UNAVAILABLE]

    exp_parts = []
    if matched_names:
        exp_parts.append(f"Matching Signals: {', '.join(matched_names)}")
    if partial_names:
        exp_parts.append(f"Partial Signals: {', '.join(partial_names)}")
    if mismatch_names:
        exp_parts.append(f"Mismatched Signals: {', '.join(mismatch_names)}")
    if unavail_names:
        exp_parts.append(f"Unavailable Signals: {', '.join(unavail_names)}")

    explanation = f"{level.value} (Score: {normalized_score:.2f}). " + " | ".join(exp_parts)

    return CaseSimilarityResult(
        source_case_id=source_case_id,
        candidate_case_id=candidate_case_id,
        overall_score=normalized_score,
        similarity_level=level,
        signals=signals,
        strongest_evidence=strongest_evidence,
        explanation=explanation
    )
