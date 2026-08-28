from typing import List
from app.services.case_similarity.models import ExtractedCaseFeatures
from app.services.case_similarity.similarity.text_similarity import (
    compute_crime_category_similarity,
    compute_mo_text_similarity,
)
from app.services.case_similarity.similarity.legal_similarity import (
    compute_legal_section_similarity,
)
from app.services.case_similarity.similarity.temporal_similarity import (
    compute_temporal_similarity,
)
from app.services.case_similarity.similarity.models import SignalStatus
from app.services.relationship_engine.models import (
    RelationshipSignal,
    RelationshipType,
    SignalCertainty,
)


def extract_case_relationship_signals(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> List[RelationshipSignal]:
    """Extracts MO similarity, crime category, legal sections, and temporal proximity relationship signals."""
    src_id = c1.identity.case_id
    tgt_id = c2.identity.case_id
    signals: List[RelationshipSignal] = []

    # 1. SIMILAR_MODUS_OPERANDI Signal
    mo_sig = compute_mo_text_similarity(c1, c2)
    if mo_sig.status in (SignalStatus.MATCH, SignalStatus.PARTIAL):
        cert = SignalCertainty.HIGH_CONFIDENCE if mo_sig.status == SignalStatus.MATCH else SignalCertainty.POSSIBLE
        signals.append(
            RelationshipSignal(
                relationship_type=RelationshipType.SIMILAR_MODUS_OPERANDI,
                source_case_id=src_id,
                target_case_id=tgt_id,
                raw_score=mo_sig.raw_score,
                certainty=cert,
                evidence=mo_sig.evidence,
                explanation=mo_sig.explanation,
                supporting_entity_ids=[],
                provenance="Step 4B MO Text Similarity",
                uncertainty_note="Modus operandi text similarity evidence; does not prove same perpetrator identity or criminal coordination."
            )
        )

    # 2. SIMILAR_CRIME_CATEGORY Signal
    cat_sig = compute_crime_category_similarity(c1, c2)
    if cat_sig.status == SignalStatus.MATCH:
        signals.append(
            RelationshipSignal(
                relationship_type=RelationshipType.SIMILAR_CRIME_CATEGORY,
                source_case_id=src_id,
                target_case_id=tgt_id,
                raw_score=cat_sig.raw_score,
                certainty=SignalCertainty.POSSIBLE,
                evidence=cat_sig.evidence,
                explanation=cat_sig.explanation,
                supporting_entity_ids=[],
                provenance="Step 4B Crime Category Matching",
                uncertainty_note="Crime classification similarity; common crime categories naturally overlap across independent cases."
            )
        )

    # 3. SIMILAR_LEGAL_SECTIONS Signal
    legal_sig = compute_legal_section_similarity(c1, c2)
    if legal_sig.status in (SignalStatus.MATCH, SignalStatus.PARTIAL):
        cert = SignalCertainty.HIGH_CONFIDENCE if legal_sig.status == SignalStatus.MATCH else SignalCertainty.POSSIBLE
        signals.append(
            RelationshipSignal(
                relationship_type=RelationshipType.SIMILAR_LEGAL_SECTIONS,
                source_case_id=src_id,
                target_case_id=tgt_id,
                raw_score=legal_sig.raw_score,
                certainty=cert,
                evidence=legal_sig.evidence,
                explanation=legal_sig.explanation,
                supporting_entity_ids=[],
                provenance="Step 4B Legal Section Matching",
                uncertainty_note="Legal charge section overlap; common legal statutes naturally recur across independent cases."
            )
        )

    # 4. TEMPORAL_PROXIMITY Signal
    temp_sig = compute_temporal_similarity(c1, c2)
    if temp_sig.status in (SignalStatus.MATCH, SignalStatus.PARTIAL):
        cert = SignalCertainty.HIGH_CONFIDENCE if temp_sig.status == SignalStatus.MATCH else SignalCertainty.POSSIBLE
        signals.append(
            RelationshipSignal(
                relationship_type=RelationshipType.TEMPORAL_PROXIMITY,
                source_case_id=src_id,
                target_case_id=tgt_id,
                raw_score=temp_sig.raw_score,
                certainty=cert,
                evidence=temp_sig.evidence,
                explanation=temp_sig.explanation,
                supporting_entity_ids=[],
                provenance="Step 4B Temporal Proximity Decay",
                uncertainty_note="Temporal proximity evidence; does not prove criminal coordination or common causality."
            )
        )

    return signals
