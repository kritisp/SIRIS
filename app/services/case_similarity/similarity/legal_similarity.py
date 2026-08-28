from app.config.settings import settings
from app.services.case_similarity.models import ExtractedCaseFeatures
from app.services.case_similarity.similarity.models import CaseSimilaritySignal, SignalStatus


def compute_legal_section_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes set-based Jaccard similarity for normalized legal sections preserving law attribution."""
    w = settings.SIM_WEIGHT_LEGAL_SECTIONS
    sec1 = set(c1.legal.normalized_sections or [])
    sec2 = set(c2.legal.normalized_sections or [])

    if not sec1 or not sec2:
        return CaseSimilaritySignal(
            signal_name="LEGAL_SECTION_SIMILARITY",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.UNAVAILABLE,
            evidence=[],
            explanation="Legal sections unavailable on one or both cases."
        )

    intersection = sec1 & sec2
    union = sec1 | sec2
    jaccard_score = len(intersection) / len(union) if union else 0.0
    jaccard_score = round(jaccard_score, 4)

    if jaccard_score >= 0.80:
        status = SignalStatus.MATCH
    elif jaccard_score > 0.0:
        status = SignalStatus.PARTIAL
    else:
        status = SignalStatus.MISMATCH

    shared_secs = sorted(list(intersection))
    evidence = []
    if shared_secs:
        evidence.append(f"Normalized legal sections overlap: {', '.join(shared_secs)}")

    return CaseSimilaritySignal(
        signal_name="LEGAL_SECTION_SIMILARITY",
        raw_score=jaccard_score,
        weight=w,
        weighted_score=round(jaccard_score * w, 4),
        status=status,
        evidence=evidence,
        explanation=f"Jaccard section overlap: {len(intersection)}/{len(union)} sections ({jaccard_score:.2f})."
    )
