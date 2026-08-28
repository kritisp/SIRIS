from datetime import date, datetime, time
from typing import Optional, Union
from app.normalization.models import NormalizedEntity
from app.normalization.person import normalize_person_name
from app.normalization.phone import normalize_phone_number
from app.normalization.vehicle import normalize_vehicle_registration
from app.normalization.location import normalize_location_text
from app.normalization.evidence import normalize_evidence_description
from app.normalization.datetime_norm import normalize_datetime
from app.normalization.mo import normalize_modus_operandi


class EntityNormalizationService:
    """Unified service for deterministic entity normalization across SIRIS domain objects."""

    @staticmethod
    def normalize_person(raw_name: Optional[str]) -> NormalizedEntity:
        return normalize_person_name(raw_name)

    @staticmethod
    def normalize_phone(raw_phone: Optional[str]) -> NormalizedEntity:
        return normalize_phone_number(raw_phone)

    @staticmethod
    def normalize_vehicle(raw_reg: Optional[str]) -> NormalizedEntity:
        return normalize_vehicle_registration(raw_reg)

    @staticmethod
    def normalize_location(raw_location: Optional[str]) -> NormalizedEntity:
        return normalize_location_text(raw_location)

    @staticmethod
    def normalize_evidence(raw_text: Optional[str]) -> NormalizedEntity:
        return normalize_evidence_description(raw_text)

    @staticmethod
    def normalize_datetime(raw_dt: Optional[Union[date, datetime, time, str]]) -> NormalizedEntity:
        return normalize_datetime(raw_dt)

    @staticmethod
    def normalize_mo(raw_mo: Optional[str]) -> NormalizedEntity:
        return normalize_modus_operandi(raw_mo)
