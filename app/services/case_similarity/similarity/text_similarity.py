from typing import List, Tuple
from app.config.settings import settings
from app.services.case_similarity.models import ExtractedCaseFeatures, MOSourceType
from app.services.case_similarity.similarity.models import CaseSimilaritySignal, SignalStatus


def compute_mo_text_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes deterministic Jaccard token overlap similarity for Modus Operandi (MO) and text descriptions."""
    w = settings.SIM_WEIGHT_MO_TEXT

    mo_source1 = c1.crime.mo_source
    mo_source2 = c2.crime.mo_source

    if mo_source1 == MOSourceType.UNAVAILABLE or mo_source2 == MOSourceType.UNAVAILABLE:
        return CaseSimilaritySignal(
            signal_name="MO_TEXT_SIMILARITY",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.UNAVAILABLE,
            evidence=[],
            explanation="Modus Operandi / text description unavailable on one or both cases."
        )

    tokens1 = set(c1.crime.normalized_mo_tokens or [])
    tokens2 = set(c2.crime.normalized_mo_tokens or [])

    if not tokens1 or not tokens2:
        return CaseSimilaritySignal(
            signal_name="MO_TEXT_SIMILARITY",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.UNAVAILABLE,
            evidence=[],
            explanation="No MO tokens available for comparison."
        )

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    jaccard_score = len(intersection) / len(union) if union else 0.0
    jaccard_score = round(jaccard_score, 4)

    if jaccard_score >= 0.70:
        status = SignalStatus.MATCH
    elif jaccard_score >= 0.25:
        status = SignalStatus.PARTIAL
    else:
        status = SignalStatus.MISMATCH

    shared_keywords = sorted(list(intersection))
    evidence = []
    if shared_keywords:
        evidence.append(f"Same normalized MO keywords: {', '.join(shared_keywords[:5])}")

    return CaseSimilaritySignal(
        signal_name="MO_TEXT_SIMILARITY",
        raw_score=jaccard_score,
        weight=w,
        weighted_score=round(jaccard_score * w, 4),
        status=status,
        evidence=evidence,
        explanation=f"Jaccard token overlap: {jaccard_score:.2f} across {len(union)} unique tokens. MO Sources: {mo_source1.value} vs {mo_source2.value}"
    )


def compute_crime_category_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes crime category and crime type matching signal."""
    w = settings.SIM_WEIGHT_CRIME_CATEGORY
    cat1 = c1.crime.crime_category
    cat2 = c2.crime.crime_category

    if not cat1 or not cat2:
        return CaseSimilaritySignal(
            signal_name="CRIME_CATEGORY_SIMILARITY",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.UNAVAILABLE,
            evidence=[],
            explanation="Crime category unavailable on one or both cases."
        )

    cat1_clean = cat1.upper().strip()
    cat2_clean = cat2.upper().strip()

    if cat1_clean == cat2_clean:
        type1 = (c1.crime.crime_type or "").upper().strip()
        type2 = (c2.crime.crime_type or "").upper().strip()
        score = 1.0 if (type1 and type2 and type1 == type2) else 0.85

        evidence = [f"Both cases belong to {cat1_clean} category"]
        if type1 and type1 == type2:
            evidence.append(f"Matching crime sub-type: {type1}")

        return CaseSimilaritySignal(
            signal_name="CRIME_CATEGORY_SIMILARITY",
            raw_score=score,
            weight=w,
            weighted_score=round(score * w, 4),
            status=SignalStatus.MATCH,
            evidence=evidence,
            explanation=f"Category match: {cat1_clean}"
        )
    else:
        return CaseSimilaritySignal(
            signal_name="CRIME_CATEGORY_SIMILARITY",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.MISMATCH,
            evidence=[],
            explanation=f"Category mismatch: {cat1_clean} vs {cat2_clean}"
        )
