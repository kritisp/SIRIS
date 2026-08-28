import math
from typing import List, Set, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.config.settings import settings
from app.services.case_similarity.models import ExtractedCaseFeatures, MOSourceType
from app.services.case_similarity.similarity.models import CaseSimilaritySignal, SignalStatus


def compute_tfidf_cosine_similarity(text1: str, text2: str) -> float:
    """Computes TF-IDF cosine similarity between two text strings using scikit-learn."""
    if not text1 or not text2 or not text1.strip() or not text2.strip():
        return 0.0
    try:
        vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        sim_matrix = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return float(sim_matrix[0][0])
    except Exception:
        return 0.0


def compute_mo_text_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes hybrid TF-IDF Cosine + Keyword Overlap MO similarity with source attribution weighting."""
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

    raw_text1 = c1.crime.raw_mo or ""
    raw_text2 = c2.crime.raw_mo or ""

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

    # 1. TF-IDF Cosine Similarity
    tfidf_sim = compute_tfidf_cosine_similarity(raw_text1, raw_text2)

    # 2. Jaccard Keyword Overlap
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    jaccard_sim = len(intersection) / len(union) if union else 0.0

    # 3. Hybrid Combination (60% TF-IDF Cosine + 40% Jaccard Overlap)
    hybrid_score = 0.60 * tfidf_sim + 0.40 * jaccard_sim

    # 4. Source Attribution Weight Factor
    # Dedicated MO carries full weight; description-derived text carries a 0.90x factor
    if mo_source1 == MOSourceType.DEDICATED_MO and mo_source2 == MOSourceType.DEDICATED_MO:
        final_score = hybrid_score
        source_note = "Both cases have dedicated MO"
    elif mo_source1 == MOSourceType.DEDICATED_MO or mo_source2 == MOSourceType.DEDICATED_MO:
        final_score = hybrid_score * 0.95
        source_note = "One case has dedicated MO, one description-derived"
    else:
        final_score = hybrid_score * 0.90
        source_note = "Both cases use description-derived MO"

    final_score = round(min(1.0, max(0.0, final_score)), 4)

    if final_score >= 0.70:
        status = SignalStatus.MATCH
    elif final_score >= 0.25:
        status = SignalStatus.PARTIAL
    else:
        status = SignalStatus.MISMATCH

    shared_keywords = sorted(list(intersection))
    evidence = []
    if shared_keywords:
        evidence.append(f"Shared normalized MO keywords: {', '.join(shared_keywords[:5])}")
    evidence.append(f"Hybrid TF-IDF Cosine: {tfidf_sim:.2f}, Jaccard: {jaccard_sim:.2f} ({source_note})")

    return CaseSimilaritySignal(
        signal_name="MO_TEXT_SIMILARITY",
        raw_score=final_score,
        weight=w,
        weighted_score=round(final_score * w, 4),
        status=status,
        evidence=evidence,
        explanation=f"Hybrid TF-IDF Cosine + Jaccard MO similarity: {final_score:.2f} ({source_note})."
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
