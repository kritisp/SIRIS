from typing import Dict, List, Tuple
from app.config.settings import settings
from app.services.relationship_engine.models import RelationshipSignal, RelationshipType
from app.services.relationship_engine.confidence.models import SignalFamily


def get_signal_family(rel_type: RelationshipType) -> SignalFamily:
    """Maps a RelationshipType enum to its corresponding evidence SignalFamily."""
    if rel_type in (RelationshipType.SHARED_HIGH_CONFIDENCE_PERSON, RelationshipType.POSSIBLE_PERSON_RELATIONSHIP):
        return SignalFamily.PERSON_IDENTITY
    elif rel_type == RelationshipType.SHARED_PHONE:
        return SignalFamily.CONTACT
    elif rel_type == RelationshipType.SHARED_VEHICLE:
        return SignalFamily.VEHICLE
    elif rel_type == RelationshipType.SHARED_LOCATION:
        return SignalFamily.LOCATION
    elif rel_type in (RelationshipType.SIMILAR_MODUS_OPERANDI, RelationshipType.SIMILAR_CRIME_CATEGORY):
        return SignalFamily.BEHAVIORAL
    elif rel_type == RelationshipType.SIMILAR_LEGAL_SECTIONS:
        return SignalFamily.LEGAL
    elif rel_type == RelationshipType.TEMPORAL_PROXIMITY:
        return SignalFamily.TEMPORAL
    return SignalFamily.BEHAVIORAL


def get_signal_base_weight(rel_type: RelationshipType) -> float:
    """Returns the configured evidentiary contribution weight for a RelationshipType."""
    weights = {
        RelationshipType.SHARED_HIGH_CONFIDENCE_PERSON: settings.REL_WEIGHT_SHARED_HIGH_CONFIDENCE_PERSON,
        RelationshipType.SHARED_PHONE: settings.REL_WEIGHT_SHARED_PHONE,
        RelationshipType.SHARED_VEHICLE: settings.REL_WEIGHT_SHARED_VEHICLE,
        RelationshipType.SIMILAR_MODUS_OPERANDI: settings.REL_WEIGHT_SIMILAR_MODUS_OPERANDI,
        RelationshipType.SHARED_LOCATION: settings.REL_WEIGHT_SHARED_LOCATION,
        RelationshipType.POSSIBLE_PERSON_RELATIONSHIP: settings.REL_WEIGHT_POSSIBLE_PERSON_RELATIONSHIP,
        RelationshipType.TEMPORAL_PROXIMITY: settings.REL_WEIGHT_TEMPORAL_PROXIMITY,
        RelationshipType.SIMILAR_CRIME_CATEGORY: settings.REL_WEIGHT_SIMILAR_CRIME_CATEGORY,
        RelationshipType.SIMILAR_LEGAL_SECTIONS: settings.REL_WEIGHT_SIMILAR_LEGAL_SECTIONS,
    }
    return weights.get(rel_type, 0.20)


def group_signals_by_family(
    signals: List[RelationshipSignal]
) -> Dict[SignalFamily, List[Tuple[RelationshipSignal, float]]]:
    """Groups signals by evidence family and computes diminishing-return weights to prevent double-counting.
    
    The primary (strongest) signal in an evidence family gets 100% contribution factor (1.0).
    Secondary signals in the same evidence family get a 25% diminishing factor (0.25).
    """
    family_map: Dict[SignalFamily, List[RelationshipSignal]] = {}
    for sig in signals:
        fam = get_signal_family(sig.relationship_type)
        family_map.setdefault(fam, []).append(sig)

    grouped_result: Dict[SignalFamily, List[Tuple[RelationshipSignal, float]]] = {}

    for fam, sig_list in family_map.items():
        # Sort signals by raw contribution (base_weight * raw_score) descending
        sorted_sigs = sorted(
            sig_list,
            key=lambda s: get_signal_base_weight(s.relationship_type) * s.raw_score,
            reverse=True
        )

        family_items: List[Tuple[RelationshipSignal, float]] = []
        for idx, sig in enumerate(sorted_sigs):
            # First signal in family gets 1.0 factor; subsequent signals get 0.25 diminishing factor
            factor = 1.0 if idx == 0 else 0.25
            family_items.append((sig, factor))

        grouped_result[fam] = family_items

    return grouped_result
