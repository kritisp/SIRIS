from typing import Any, Dict, List
from app.services.blocking.models import CandidatePair
from app.services.resolution.models import ResolutionResult
from app.services.resolution.person_resolution import resolve_person_pair
from app.services.resolution.phone_resolution import resolve_phone_pair
from app.services.resolution.vehicle_resolution import resolve_vehicle_pair
from app.services.resolution.location_resolution import resolve_location_pair


class EntityResolver:
    """Unified evidence-aware entity resolution engine for S.I.R.I.S."""

    @staticmethod
    def resolve_person(p1: Dict[str, Any], p2: Dict[str, Any]) -> ResolutionResult:
        return resolve_person_pair(p1, p2)

    @staticmethod
    def resolve_phone(ph1: Dict[str, Any], ph2: Dict[str, Any]) -> ResolutionResult:
        return resolve_phone_pair(ph1, ph2)

    @staticmethod
    def resolve_vehicle(v1: Dict[str, Any], v2: Dict[str, Any]) -> ResolutionResult:
        return resolve_vehicle_pair(v1, v2)

    @staticmethod
    def resolve_location(l1: Dict[str, Any], l2: Dict[str, Any]) -> ResolutionResult:
        return resolve_location_pair(l1, l2)

    @classmethod
    def resolve_person_candidates(
        cls,
        candidates: List[CandidatePair],
        person_lookup: Dict[str, Dict[str, Any]]
    ) -> List[ResolutionResult]:
        results: List[ResolutionResult] = []
        for pair in candidates:
            p1 = person_lookup.get(pair.source_entity_id)
            p2 = person_lookup.get(pair.candidate_entity_id)
            if p1 and p2:
                res = cls.resolve_person(p1, p2)
                results.append(res)
        return results
