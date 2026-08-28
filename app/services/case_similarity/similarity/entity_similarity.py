from typing import List, Tuple
from app.config.settings import settings
from app.services.case_similarity.models import ExtractedCaseFeatures, ExtractedPersonEntity
from app.services.case_similarity.similarity.models import CaseSimilaritySignal, SignalStatus
from app.services.resolution.models import ResolutionDecision
from app.services.resolution.person_resolution import resolve_person_pair


def _person_to_dict(p: ExtractedPersonEntity) -> dict:
    """Converts ExtractedPersonEntity to dict format expected by Step 3C Person Resolution."""
    return {
        "id": p.person_id,
        "name": p.name,
        "normalized_name": p.normalized_name,
        "phonetic_name": p.phonetic_name,
        "date_of_birth": p.date_of_birth,
        "role": p.role,
        "gender": p.gender
    }


def compute_person_overlap_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes person entity overlap signal reusing Step 3C resolution outputs without asserting identity."""
    w = settings.SIM_WEIGHT_PERSON_OVERLAP
    p1_list = c1.entities.persons or []
    p2_list = c2.entities.persons or []

    if not p1_list or not p2_list:
        return CaseSimilaritySignal(
            signal_name="PERSON_OVERLAP",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.UNAVAILABLE,
            evidence=[],
            explanation="Person entities unavailable on one or both cases."
        )

    best_score = 0.0
    best_status = SignalStatus.MISMATCH
    best_evidence: List[str] = []
    best_explanation = "No matching person entities found."

    # Evaluate candidate person pairs via Step 3C
    for p1 in p1_list:
        dict1 = _person_to_dict(p1)
        for p2 in p2_list:
            dict2 = _person_to_dict(p2)
            res = resolve_person_pair(dict1, dict2)

            if res.decision == ResolutionDecision.HIGH_CONFIDENCE_MATCH:
                score = 1.0
                ev = [f"Entity-resolution evidence indicates confirmed entity match ({p1.name})"]
                exp = f"EXACT_RESOLVED_ENTITY (Step 3C score: {res.overall_score:.2f})"
                if score > best_score:
                    best_score, best_status, best_evidence, best_explanation = score, SignalStatus.MATCH, ev, exp
            elif res.decision == ResolutionDecision.POSSIBLE_MATCH:
                score = 0.70
                ev = [f"Entity-resolution indicates possible entity match ({p1.name})"]
                exp = f"STRONG_ENTITY_EVIDENCE (Step 3C score: {res.overall_score:.2f})"
                if score > best_score:
                    best_score, best_status, best_evidence, best_explanation = score, SignalStatus.MATCH, ev, exp
            elif p1.normalized_name and p2.normalized_name and p1.normalized_name == p2.normalized_name:
                # Name-only match without confirmed DOB/phone evidence is unverified identity (0.35)
                score = 0.35
                ev = [f"Matching normalized person name (unverified identity): {p1.name}"]
                exp = f"NAME_ONLY match ({p1.normalized_name}) - unverified identity"
                if score > best_score:
                    best_score, best_status, best_evidence, best_explanation = score, SignalStatus.PARTIAL, ev, exp
            elif p1.phonetic_name and p2.phonetic_name and p1.phonetic_name == p2.phonetic_name:
                score = 0.40
                ev = [f"Phonetic name overlap code(s): {p1.phonetic_name}"]
                exp = f"PHONETIC_ONLY Soundex match ({p1.phonetic_name})"
                if score > best_score:
                    best_score, best_status, best_evidence, best_explanation = score, SignalStatus.PARTIAL, ev, exp

    return CaseSimilaritySignal(
        signal_name="PERSON_OVERLAP",
        raw_score=best_score,
        weight=w,
        weighted_score=round(best_score * w, 4),
        status=best_status,
        evidence=best_evidence,
        explanation=best_explanation
    )


def compute_vehicle_overlap_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes vehicle entity registration overlap signal."""
    w = settings.SIM_WEIGHT_VEHICLE_OVERLAP
    v1_list = c1.entities.vehicles or []
    v2_list = c2.entities.vehicles or []

    if not v1_list or not v2_list:
        return CaseSimilaritySignal(
            signal_name="VEHICLE_OVERLAP",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.UNAVAILABLE,
            evidence=[],
            explanation="Vehicle entities unavailable on one or both cases."
        )

    regs1 = {v.normalized_reg for v in v1_list if v.normalized_reg}
    regs2 = {v.normalized_reg for v in v2_list if v.normalized_reg}

    shared_regs = regs1 & regs2
    if shared_regs:
        evidence = [f"Same normalized vehicle registration: {', '.join(sorted(list(shared_regs)))}"]
        return CaseSimilaritySignal(
            signal_name="VEHICLE_OVERLAP",
            raw_score=1.0,
            weight=w,
            weighted_score=w,
            status=SignalStatus.MATCH,
            evidence=evidence,
            explanation=f"Exact vehicle registration overlap: {len(shared_regs)} vehicle(s)."
        )

    return CaseSimilaritySignal(
        signal_name="VEHICLE_OVERLAP",
        raw_score=0.0,
        weight=w,
        weighted_score=0.0,
        status=SignalStatus.MISMATCH,
        evidence=[],
        explanation="No matching vehicle registrations found."
    )


def compute_phone_overlap_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes phone entity E.164 number overlap signal."""
    w = settings.SIM_WEIGHT_PHONE_OVERLAP
    ph1_list = c1.entities.phones or []
    ph2_list = c2.entities.phones or []

    if not ph1_list or not ph2_list:
        return CaseSimilaritySignal(
            signal_name="PHONE_OVERLAP",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.UNAVAILABLE,
            evidence=[],
            explanation="Phone entities unavailable on one or both cases."
        )

    nums1 = {ph.normalized_e164 for ph in ph1_list if ph.normalized_e164 and ph.is_valid}
    nums2 = {ph.normalized_e164 for ph in ph2_list if ph.normalized_e164 and ph.is_valid}

    shared_nums = nums1 & nums2
    if shared_nums:
        evidence = [f"Same normalized phone number: {', '.join(sorted(list(shared_nums)))}"]
        return CaseSimilaritySignal(
            signal_name="PHONE_OVERLAP",
            raw_score=1.0,
            weight=w,
            weighted_score=w,
            status=SignalStatus.MATCH,
            evidence=evidence,
            explanation=f"Exact E.164 phone number overlap: {len(shared_nums)} phone(s)."
        )

    return CaseSimilaritySignal(
        signal_name="PHONE_OVERLAP",
        raw_score=0.0,
        weight=w,
        weighted_score=0.0,
        status=SignalStatus.MISMATCH,
        evidence=[],
        explanation="No matching phone numbers found."
    )
