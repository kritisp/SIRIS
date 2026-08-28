from typing import List, Tuple
from app.config.settings import settings
from app.services.case_similarity.models import ExtractedCaseFeatures
from app.services.case_similarity.similarity.models import CaseSimilaritySignal, SignalStatus


def compute_person_overlap_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes person entity overlap signal between cases without asserting identity."""
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

    names1 = {p.normalized_name for p in p1_list if p.normalized_name}
    names2 = {p.normalized_name for p in p2_list if p.normalized_name}

    shared_names = names1 & names2
    if shared_names:
        evidence = [f"Matching normalized person name(s): {', '.join(sorted(list(shared_names)))}"]
        return CaseSimilaritySignal(
            signal_name="PERSON_OVERLAP",
            raw_score=1.0,
            weight=w,
            weighted_score=w,
            status=SignalStatus.MATCH,
            evidence=evidence,
            explanation=f"Exact normalized person name overlap: {len(shared_names)} person(s)."
        )

    ph1_set = {p.phonetic_name for p in p1_list if p.phonetic_name}
    ph2_set = {p.phonetic_name for p in p2_list if p.phonetic_name}

    shared_ph = ph1_set & ph2_set
    if shared_ph:
        evidence = [f"Phonetic name overlap code(s): {', '.join(sorted(list(shared_ph)))}"]
        return CaseSimilaritySignal(
            signal_name="PERSON_OVERLAP",
            raw_score=0.60,
            weight=w,
            weighted_score=round(0.60 * w, 4),
            status=SignalStatus.PARTIAL,
            evidence=evidence,
            explanation=f"Phonetic Soundex overlap: {len(shared_ph)} code(s)."
        )

    return CaseSimilaritySignal(
        signal_name="PERSON_OVERLAP",
        raw_score=0.0,
        weight=w,
        weighted_score=0.0,
        status=SignalStatus.MISMATCH,
        evidence=[],
        explanation="No matching person entities or phonetic overlaps found."
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
