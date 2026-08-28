from typing import Any, Dict, List, Optional
from rapidfuzz import fuzz
from app.config.settings import settings
from app.normalization.models import EntityType
from app.normalization.service import EntityNormalizationService
from app.services.resolution.models import (
    ResolutionResult,
    SignalEvidence,
    SignalStatus,
)
from app.services.resolution.scoring import compute_evidence_score


def resolve_person_pair(p1: Dict[str, Any], p2: Dict[str, Any]) -> ResolutionResult:
    """Multi-factor evidence-aware person candidate resolution."""
    id1 = str(p1.get("id"))
    id2 = str(p2.get("id"))

    signals: List[SignalEvidence] = []
    unavailable: List[str] = []

    # 1. Name & Alias Normalization (Step 3A)
    norm1 = EntityNormalizationService.normalize_person(p1.get("name"))
    norm2 = EntityNormalizationService.normalize_person(p2.get("name"))

    if norm1.normalized_value and norm2.normalized_value:
        # RapidFuzz token_set_ratio handles name variations, initials, and aliases
        set_sim = fuzz.token_set_ratio(norm1.normalized_value, norm2.normalized_value) / 100.0
        w_sim = fuzz.WRatio(norm1.normalized_value, norm2.normalized_value) / 100.0
        name_score = max(set_sim, w_sim)

        w = settings.PERSON_WEIGHT_NAME
        status = SignalStatus.MATCH if name_score >= 0.45 else SignalStatus.CONFLICT
        signals.append(
            SignalEvidence(
                name="NAME_SIMILARITY",
                raw_score=round(name_score, 4),
                weight=w,
                weighted_score=round(name_score * w, 4),
                status=status,
                description=f"RapidFuzz token_set_ratio={set_sim:.2f}, WRatio={w_sim:.2f}"
            )
        )

        # Phonetic Signal (Step 3A Soundex)
        if norm1.phonetic_value and norm2.phonetic_value:
            has_initials = norm1.metadata.get("has_initials") or norm2.metadata.get("has_initials")
            ph_match = (norm1.phonetic_value == norm2.phonetic_value)
            if ph_match:
                ph_score = 1.0
                status = SignalStatus.MATCH
            elif has_initials:
                # Single-letter initials naturally produce abbreviated Soundex codes; treat as match
                ph_score = 0.75
                status = SignalStatus.MATCH
            else:
                ph_score = 0.40
                status = SignalStatus.CONFLICT

            pw = settings.PERSON_WEIGHT_PHONETIC
            signals.append(
                SignalEvidence(
                    name="PHONETIC_MATCH",
                    raw_score=ph_score,
                    weight=pw,
                    weighted_score=round(ph_score * pw, 4),
                    status=status,
                    description=f"Soundex: {norm1.phonetic_value} vs {norm2.phonetic_value}"
                )
            )
        else:
            unavailable.append("PHONETIC_NAME")
    else:
        unavailable.append("NAME")

    # 2. DOB Signal
    dob1 = p1.get("date_of_birth")
    dob2 = p2.get("date_of_birth")
    dw = settings.PERSON_WEIGHT_DOB

    if dob1 and dob2:
        dob1_str = str(dob1)
        dob2_str = str(dob2)
        if dob1_str == dob2_str:
            signals.append(
                SignalEvidence(
                    name="DOB_MATCH",
                    raw_score=1.0,
                    weight=dw,
                    weighted_score=dw,
                    status=SignalStatus.MATCH,
                    description="Exact DOB match"
                )
            )
        else:
            signals.append(
                SignalEvidence(
                    name="DOB_MATCH",
                    raw_score=0.0,
                    weight=dw,
                    weighted_score=0.0,
                    status=SignalStatus.CONFLICT,
                    description=f"Conflicting DOB: {dob1_str} vs {dob2_str}"
                )
            )
    else:
        unavailable.append("DOB")

    # 3. Phone Signal
    ph1 = p1.get("phone") or p1.get("normalized_number")
    ph2 = p2.get("phone") or p2.get("normalized_number")
    ph_w = settings.PERSON_WEIGHT_PHONE

    if ph1 and ph2:
        norm_ph1 = EntityNormalizationService.normalize_phone(ph1)
        norm_ph2 = EntityNormalizationService.normalize_phone(ph2)
        if norm_ph1.normalized_value and norm_ph2.normalized_value:
            if norm_ph1.normalized_value == norm_ph2.normalized_value:
                signals.append(
                    SignalEvidence(
                        name="PHONE_MATCH",
                        raw_score=1.0,
                        weight=ph_w,
                        weighted_score=ph_w,
                        status=SignalStatus.MATCH,
                        description="Exact normalized phone match"
                    )
                )
            else:
                signals.append(
                    SignalEvidence(
                        name="PHONE_MATCH",
                        raw_score=0.0,
                        weight=ph_w,
                        weighted_score=0.0,
                        status=SignalStatus.CONFLICT,
                        description="Conflicting phone numbers"
                    )
                )
        else:
            unavailable.append("PHONE")
    else:
        unavailable.append("PHONE")

    # 4. Vehicle Association Signal
    v1 = p1.get("vehicles") or []
    v2 = p2.get("vehicles") or []
    vw = settings.PERSON_WEIGHT_VEHICLE

    if v1 and v2:
        v_set1 = {EntityNormalizationService.normalize_vehicle(v).normalized_value for v in v1 if v}
        v_set2 = {EntityNormalizationService.normalize_vehicle(v).normalized_value for v in v2 if v}
        shared_veh = v_set1 & v_set2
        if shared_veh:
            signals.append(
                SignalEvidence(
                    name="VEHICLE_MATCH",
                    raw_score=1.0,
                    weight=vw,
                    weighted_score=vw,
                    status=SignalStatus.MATCH,
                    description=f"Shared vehicles: {len(shared_veh)}"
                )
            )
        else:
            unavailable.append("VEHICLE")
    else:
        unavailable.append("VEHICLE")

    # 5. Location / Address Signal
    addr1 = p1.get("address") or p1.get("district")
    addr2 = p2.get("address") or p2.get("district")
    lw = settings.PERSON_WEIGHT_LOCATION

    if addr1 and addr2:
        loc1 = EntityNormalizationService.normalize_location(addr1).normalized_value
        loc2 = EntityNormalizationService.normalize_location(addr2).normalized_value
        if loc1 and loc2:
            loc_sim = fuzz.token_set_ratio(loc1, loc2) / 100.0
            signals.append(
                SignalEvidence(
                    name="LOCATION_MATCH",
                    raw_score=round(loc_sim, 4),
                    weight=lw,
                    weighted_score=round(loc_sim * lw, 4),
                    status=SignalStatus.MATCH if loc_sim >= 0.65 else SignalStatus.CONFLICT,
                    description=f"Location similarity: {loc_sim:.2f}"
                )
            )
        else:
            unavailable.append("LOCATION")
    else:
        unavailable.append("LOCATION")

    # Calculate overall score & decision
    score, decision, explanation = compute_evidence_score(signals, unavailable)

    matching_signals = [s for s in signals if s.status == SignalStatus.MATCH]
    conflicting_signals = [s for s in signals if s.status == SignalStatus.CONFLICT]

    return ResolutionResult(
        source_entity_id=id1,
        candidate_entity_id=id2,
        entity_type=EntityType.PERSON,
        overall_score=score,
        decision=decision,
        matching_signals=matching_signals,
        conflicting_signals=conflicting_signals,
        unavailable_signals=unavailable,
        explanation=explanation
    )
