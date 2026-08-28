import math
from typing import Optional
from app.config.settings import settings
from app.services.case_similarity.models import ExtractedCaseFeatures
from app.services.case_similarity.similarity.models import CaseSimilaritySignal, SignalStatus


def is_valid_coordinate(lat: Optional[float], lon: Optional[float]) -> bool:
    """Validates that latitude is in [-90, 90] and longitude is in [-180, 180]."""
    if lat is None or lon is None:
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes Haversine distance in kilometers between two GPS coordinate points."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def compute_geographic_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes geographic similarity using validated Haversine coordinate decay or location text fallback."""
    w = settings.SIM_WEIGHT_GEOGRAPHIC

    g1 = c1.geographic
    g2 = c2.geographic

    # Scenario A: Valid GPS Coordinates Available on Both Cases
    if is_valid_coordinate(g1.latitude, g1.longitude) and is_valid_coordinate(g2.latitude, g2.longitude):
        dist_km = haversine_distance_km(g1.latitude, g1.longitude, g2.latitude, g2.longitude)
        decay_km = settings.GEO_DECAY_KM
        sim_score = math.exp(-dist_km / decay_km)
        sim_score = round(sim_score, 4)

        if dist_km <= 1.0:
            status = SignalStatus.MATCH
            qualifier = "EXACT/SAME LOCATION"
        elif dist_km <= 15.0:
            status = SignalStatus.PARTIAL
            qualifier = "NEARBY GPS LOCATION"
        else:
            status = SignalStatus.MISMATCH
            qualifier = "DIFFERENT LOCATION"

        evidence = [f"Cases occurred approximately {dist_km:.1f} km apart ({qualifier})"]

        return CaseSimilaritySignal(
            signal_name="GEOGRAPHIC_SIMILARITY",
            raw_score=sim_score,
            weight=w,
            weighted_score=round(sim_score * w, 4),
            status=status,
            evidence=evidence,
            explanation=f"Haversine GPS distance: {dist_km:.2f} km ({qualifier})."
        )

    # Scenario B: Text Locality Fallback (requires locality or address to be present)
    has_loc1 = bool(g1.locality or g1.address)
    has_loc2 = bool(g2.locality or g2.address)

    if has_loc1 and has_loc2:
        loc1_tokens = set(g1.location_tokens or [])
        loc2_tokens = set(g2.location_tokens or [])
        if loc1_tokens and loc2_tokens:
            inter = loc1_tokens & loc2_tokens
            union = loc1_tokens | loc2_tokens
            text_sim = len(inter) / len(union) if union else 0.0
            text_sim = round(text_sim, 4)

            if text_sim >= 0.70:
                status = SignalStatus.PARTIAL
                qualifier = "SAME LOCALITY"
                score = 0.75
            elif text_sim >= 0.30:
                status = SignalStatus.PARTIAL
                qualifier = "NEARBY LOCALITY"
                score = 0.50
            else:
                status = SignalStatus.MISMATCH
                qualifier = "DIFFERENT LOCALITY"
                score = 0.0

            shared_loc = sorted(list(inter))
            evidence = []
            if shared_loc:
                evidence.append(f"Shared locality tokens: {', '.join(shared_loc)}")

            return CaseSimilaritySignal(
                signal_name="GEOGRAPHIC_SIMILARITY",
                raw_score=score,
                weight=w,
                weighted_score=round(score * w, 4),
                status=status,
                evidence=evidence,
                explanation=f"Locality text token overlap: {text_sim:.2f} ({qualifier})."
            )

    # Scenario C: District Fallback (Weaker strength than GPS / Locality)
    dist1 = g1.district or c1.identity.district
    dist2 = g2.district or c2.identity.district

    if dist1 and dist2:
        if dist1.strip().lower() == dist2.strip().lower():
            return CaseSimilaritySignal(
                signal_name="GEOGRAPHIC_SIMILARITY",
                raw_score=0.40,
                weight=w,
                weighted_score=round(0.40 * w, 4),
                status=SignalStatus.PARTIAL,
                evidence=[f"Both cases occurred in same district: {dist1}"],
                explanation=f"District match: {dist1} (SAME DISTRICT)"
            )
        else:
            return CaseSimilaritySignal(
                signal_name="GEOGRAPHIC_SIMILARITY",
                raw_score=0.0,
                weight=w,
                weighted_score=0.0,
                status=SignalStatus.MISMATCH,
                evidence=[],
                explanation=f"District mismatch: {dist1} vs {dist2}"
            )

    return CaseSimilaritySignal(
        signal_name="GEOGRAPHIC_SIMILARITY",
        raw_score=0.0,
        weight=w,
        weighted_score=0.0,
        status=SignalStatus.UNAVAILABLE,
        evidence=[],
        explanation="Geographic information unavailable or coordinates invalid on one or both cases."
    )
