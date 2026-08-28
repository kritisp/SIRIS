from typing import Any, Dict, List
from app.services.blocking.models import CandidatePair
from app.services.blocking.person_blocking import generate_person_candidates
from app.services.blocking.phone_blocking import generate_phone_candidates
from app.services.blocking.vehicle_blocking import generate_vehicle_candidates
from app.services.blocking.location_blocking import generate_location_candidates
from app.services.blocking.text_blocking import generate_mo_candidates


class CandidateBlockingEngine:
    """Unified engine for multi-signal candidate pair generation across SIRIS entity types."""

    @staticmethod
    def block_persons(persons: List[Dict[str, Any]]) -> List[CandidatePair]:
        return generate_person_candidates(persons)

    @staticmethod
    def block_phones(phones: List[Dict[str, Any]]) -> List[CandidatePair]:
        return generate_phone_candidates(phones)

    @staticmethod
    def block_vehicles(vehicles: List[Dict[str, Any]]) -> List[CandidatePair]:
        return generate_vehicle_candidates(vehicles)

    @staticmethod
    def block_locations(locations: List[Dict[str, Any]]) -> List[CandidatePair]:
        return generate_location_candidates(locations)

    @staticmethod
    def block_mo_cases(cases: List[Dict[str, Any]]) -> List[CandidatePair]:
        return generate_mo_candidates(cases)
