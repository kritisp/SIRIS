from typing import List
from app.services.case_similarity.models import ExtractedCaseFeatures
from app.services.case_similarity.similarity.geographic_similarity import (
    haversine_distance_km,
    is_valid_coordinate,
)
from app.services.relationship_engine.models import (
    RelationshipSignal,
    RelationshipType,
    SignalCertainty,
    get_canonical_relationship_key,
)


def extract_attribute_relationship_signals(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> List[RelationshipSignal]:
    """Extracts shared phone, shared vehicle, and shared location attribute relationship signals."""
    src_id = c1.identity.case_id
    tgt_id = c2.identity.case_id
    key = get_canonical_relationship_key(src_id, tgt_id)
    signals: List[RelationshipSignal] = []

    # 1. SHARED_PHONE Signal
    ph1_list = [ph for ph in (c1.entities.phones or []) if ph.normalized_e164 and ph.is_valid]
    ph2_list = [ph for ph in (c2.entities.phones or []) if ph.normalized_e164 and ph.is_valid]

    ph1_dict = {ph.normalized_e164: ph.phone_id for ph in ph1_list}
    ph2_dict = {ph.normalized_e164: ph.phone_id for ph in ph2_list}

    shared_phones = set(ph1_dict.keys()) & set(ph2_dict.keys())
    for num in sorted(list(shared_phones)):
        signals.append(
            RelationshipSignal(
                relationship_type=RelationshipType.SHARED_PHONE,
                source_case_id=src_id,
                target_case_id=tgt_id,
                canonical_relationship_key=key,
                raw_score=1.0,
                certainty=SignalCertainty.EXACT_ATTRIBUTE_MATCH,
                evidence=[f"Same normalized E.164 phone number: {num} [phone_id: {ph1_dict[num]}]"],
                explanation=f"Exact phone number attribute overlap ({num}).",
                supporting_entity_ids=[ph1_dict[num], ph2_dict[num]],
                provenance="Step 3A Phone Normalization",
                uncertainty_note="Exact normalized phone attribute match; does not establish person identity, ownership, or criminal association."
            )
        )

    # 2. SHARED_VEHICLE Signal
    v1_list = [v for v in (c1.entities.vehicles or []) if v.normalized_reg]
    v2_list = [v for v in (c2.entities.vehicles or []) if v.normalized_reg]

    v1_dict = {v.normalized_reg: v.vehicle_id for v in v1_list}
    v2_dict = {v.normalized_reg: v.vehicle_id for v in v2_list}

    shared_vehicles = set(v1_dict.keys()) & set(v2_dict.keys())
    for reg in sorted(list(shared_vehicles)):
        signals.append(
            RelationshipSignal(
                relationship_type=RelationshipType.SHARED_VEHICLE,
                source_case_id=src_id,
                target_case_id=tgt_id,
                canonical_relationship_key=key,
                raw_score=1.0,
                certainty=SignalCertainty.EXACT_ATTRIBUTE_MATCH,
                evidence=[f"Same normalized vehicle registration: {reg} [vehicle_id: {v1_dict[reg]}]"],
                explanation=f"Exact vehicle registration attribute overlap ({reg}).",
                supporting_entity_ids=[v1_dict[reg], v2_dict[reg]],
                provenance="Step 3A Vehicle Normalization",
                uncertainty_note="Exact normalized vehicle registration match; does not establish ownership, possession, or criminal association."
            )
        )

    # 3. SHARED_LOCATION Signal
    g1 = c1.geographic
    g2 = c2.geographic

    if is_valid_coordinate(g1.latitude, g1.longitude) and is_valid_coordinate(g2.latitude, g2.longitude):
        dist_km = haversine_distance_km(g1.latitude, g1.longitude, g2.latitude, g2.longitude)
        if dist_km <= 1.0:
            signals.append(
                RelationshipSignal(
                    relationship_type=RelationshipType.SHARED_LOCATION,
                    source_case_id=src_id,
                    target_case_id=tgt_id,
                    canonical_relationship_key=key,
                    raw_score=1.0,
                    certainty=SignalCertainty.CORRELATIONAL,
                    evidence=[f"Cases occurred within {dist_km:.2f} km of each other (EXACT/SAME LOCATION)"],
                    explanation=f"Exact spatial proximity: {dist_km:.2f} km.",
                    supporting_entity_ids=[],
                    provenance="Step 4A Geographic Coordinates",
                    uncertainty_note="Spatial proximity evidence; does not establish causal relationship or offender identity."
                )
            )
        elif dist_km <= 15.0:
            signals.append(
                RelationshipSignal(
                    relationship_type=RelationshipType.SHARED_LOCATION,
                    source_case_id=src_id,
                    target_case_id=tgt_id,
                    canonical_relationship_key=key,
                    raw_score=round(1.0 - (dist_km / 15.0) * 0.5, 4),
                    certainty=SignalCertainty.CORRELATIONAL,
                    evidence=[f"Cases occurred {dist_km:.1f} km apart (NEARBY GPS LOCATION)"],
                    explanation=f"Nearby GPS spatial proximity: {dist_km:.2f} km.",
                    supporting_entity_ids=[],
                    provenance="Step 4A Geographic Coordinates",
                    uncertainty_note="Spatial proximity evidence; does not establish causal relationship or offender identity."
                )
            )
    else:
        # Locality fallback
        has_loc1 = bool(g1.locality or g1.address)
        has_loc2 = bool(g2.locality or g2.address)
        if has_loc1 and has_loc2:
            loc1_tokens = set(g1.location_tokens or [])
            loc2_tokens = set(g2.location_tokens or [])
            if loc1_tokens and loc2_tokens:
                inter = loc1_tokens & loc2_tokens
                union = loc1_tokens | loc2_tokens
                text_sim = len(inter) / len(union) if union else 0.0
                if text_sim >= 0.70:
                    signals.append(
                        RelationshipSignal(
                            relationship_type=RelationshipType.SHARED_LOCATION,
                            source_case_id=src_id,
                            target_case_id=tgt_id,
                            canonical_relationship_key=key,
                            raw_score=0.75,
                            certainty=SignalCertainty.CORRELATIONAL,
                            evidence=[f"Shared locality tokens: {', '.join(sorted(list(inter)))}"],
                            explanation=f"Locality text token overlap: {text_sim:.2f} (SAME LOCALITY).",
                            supporting_entity_ids=[],
                            provenance="Step 3A Location Normalization",
                            uncertainty_note="Locality text overlap evidence; does not establish exact incident site concurrency."
                        )
                    )

    return signals
