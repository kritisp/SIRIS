from typing import List, Optional
from app.services.case_similarity.models import ExtractedCaseFeatures, ExtractedPersonEntity
from app.services.relationship_engine.models import (
    RelationshipSignal,
    RelationshipType,
    SignalCertainty,
)
from app.services.resolution.models import ResolutionDecision
from app.services.resolution.person_resolution import resolve_person_pair


def _person_to_dict(p: ExtractedPersonEntity) -> dict:
    return {
        "id": p.person_id,
        "name": p.name,
        "normalized_name": p.normalized_name,
        "phonetic_name": p.phonetic_name,
        "date_of_birth": p.date_of_birth,
        "role": p.role,
        "gender": p.gender
    }


def extract_person_relationship_signals(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> List[RelationshipSignal]:
    """Extracts person relationship signals using Step 3C Entity Resolution outputs."""
    src_id = c1.identity.case_id
    tgt_id = c2.identity.case_id
    p1_list = c1.entities.persons or []
    p2_list = c2.entities.persons or []

    if not p1_list or not p2_list:
        return []

    signals: List[RelationshipSignal] = []

    for p1 in p1_list:
        dict1 = _person_to_dict(p1)
        for p2 in p2_list:
            dict2 = _person_to_dict(p2)
            res = resolve_person_pair(dict1, dict2)

            if res.decision == ResolutionDecision.HIGH_CONFIDENCE_MATCH:
                signals.append(
                    RelationshipSignal(
                        relationship_type=RelationshipType.SHARED_HIGH_CONFIDENCE_PERSON,
                        source_case_id=src_id,
                        target_case_id=tgt_id,
                        raw_score=1.0,
                        certainty=SignalCertainty.HIGH_CONFIDENCE,
                        evidence=[f"Step 3C high-confidence person match: {p1.name} <-> {p2.name}"],
                        explanation=f"Strong entity resolution evidence indicates confirmed person match ({p1.name}).",
                        supporting_entity_ids=[p1.person_id, p2.person_id],
                        provenance="Step 3C Entity Resolution",
                        uncertainty_note=None
                    )
                )
            elif res.decision == ResolutionDecision.POSSIBLE_MATCH:
                signals.append(
                    RelationshipSignal(
                        relationship_type=RelationshipType.POSSIBLE_PERSON_RELATIONSHIP,
                        source_case_id=src_id,
                        target_case_id=tgt_id,
                        raw_score=0.70,
                        certainty=SignalCertainty.POSSIBLE,
                        evidence=[f"Step 3C indicates a possible person match: {p1.name} <-> {p2.name}"],
                        explanation=f"Possible person relationship indicated by Step 3C resolution ({res.overall_score:.2f}).",
                        supporting_entity_ids=[p1.person_id, p2.person_id],
                        provenance="Step 3C Entity Resolution",
                        uncertainty_note="Identity is unconfirmed by Step 3C; requires further investigation."
                    )
                )
            elif p1.normalized_name and p2.normalized_name and p1.normalized_name == p2.normalized_name:
                signals.append(
                    RelationshipSignal(
                        relationship_type=RelationshipType.POSSIBLE_PERSON_RELATIONSHIP,
                        source_case_id=src_id,
                        target_case_id=tgt_id,
                        raw_score=0.35,
                        certainty=SignalCertainty.WEAK_UNVERIFIED,
                        evidence=[f"Matching normalized person name (unverified identity): {p1.name}"],
                        explanation=f"Name-only match across cases ({p1.normalized_name}).",
                        supporting_entity_ids=[p1.person_id, p2.person_id],
                        provenance="Step 3A Person Normalization",
                        uncertainty_note="Name-only match without supporting DOB/phone evidence is unverified identity."
                    )
                )
            elif p1.phonetic_name and p2.phonetic_name and p1.phonetic_name == p2.phonetic_name:
                signals.append(
                    RelationshipSignal(
                        relationship_type=RelationshipType.POSSIBLE_PERSON_RELATIONSHIP,
                        source_case_id=src_id,
                        target_case_id=tgt_id,
                        raw_score=0.40,
                        certainty=SignalCertainty.WEAK_UNVERIFIED,
                        evidence=[f"Phonetic Soundex name code overlap: {p1.phonetic_name}"],
                        explanation=f"Phonetic name overlap code ({p1.phonetic_name}).",
                        supporting_entity_ids=[p1.person_id, p2.person_id],
                        provenance="Step 3A Soundex Normalization",
                        uncertainty_note="Phonetic overlap only; names may represent distinct individuals."
                    )
                )

    return signals
