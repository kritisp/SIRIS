from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MOSourceType(str, Enum):
    DEDICATED_MO = "DEDICATED_MO"
    DESCRIPTION_DERIVED = "DESCRIPTION_DERIVED"
    UNAVAILABLE = "UNAVAILABLE"


class CaseIdentityFeatures(BaseModel):
    """Case identity features with strict missing-data semantics."""
    case_id: str
    fir_number: str
    station_id: Optional[str] = None
    police_station: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    registration_date: Optional[str] = None
    incident_date: Optional[str] = None
    status: Optional[str] = None


class CrimeCharacteristicsFeatures(BaseModel):
    """Crime characteristics features with explicit MO source attribution."""
    crime_type: Optional[str] = None
    crime_category: Optional[str] = None
    description: Optional[str] = None
    raw_mo: Optional[str] = None
    mo_source: MOSourceType = MOSourceType.UNAVAILABLE
    normalized_mo_tokens: List[str] = Field(default_factory=list)
    mo_keywords: List[str] = Field(default_factory=list)


class LegalCharacteristicsFeatures(BaseModel):
    """Legal characteristics features."""
    legal_sections: List[str] = Field(default_factory=list)
    normalized_sections: List[str] = Field(default_factory=list)


class GeographicCharacteristicsFeatures(BaseModel):
    """Geographic characteristics features."""
    address: Optional[str] = None
    locality: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    normalized_location_text: Optional[str] = None
    location_tokens: List[str] = Field(default_factory=list)


class ExtractedPersonEntity(BaseModel):
    """Extracted person entity feature."""
    person_id: str
    name: str
    normalized_name: str
    phonetic_name: Optional[str] = None
    role: str = "OTHER"
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None


class ExtractedVehicleEntity(BaseModel):
    """Extracted vehicle entity feature."""
    vehicle_id: str
    registration_number: str
    normalized_reg: str
    role: str = "OTHER"
    vehicle_type: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None


class ExtractedPhoneEntity(BaseModel):
    """Extracted phone entity feature."""
    phone_id: str
    raw_number: str
    normalized_e164: str
    is_valid: bool = True


class ExtractedEvidenceEntity(BaseModel):
    """Extracted evidence entity feature."""
    evidence_id: str
    evidence_type: str
    description: Optional[str] = None
    normalized_tokens: List[str] = Field(default_factory=list)


class LinkedEntitiesFeatures(BaseModel):
    """Linked entities container features."""
    persons: List[ExtractedPersonEntity] = Field(default_factory=list)
    vehicles: List[ExtractedVehicleEntity] = Field(default_factory=list)
    phones: List[ExtractedPhoneEntity] = Field(default_factory=list)
    evidence: List[ExtractedEvidenceEntity] = Field(default_factory=list)


class TemporalFeatures(BaseModel):
    """Temporal features."""
    incident_datetime: Optional[str] = None
    incident_date: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday
    hour: Optional[int] = None
    time_of_day_bucket: Optional[str] = None  # MORNING, AFTERNOON, EVENING, NIGHT


class ExtractedCaseFeatures(BaseModel):
    """Complete, normalized, strongly typed extracted case feature model for SIRIS Central Engine."""
    identity: CaseIdentityFeatures
    crime: CrimeCharacteristicsFeatures
    legal: LegalCharacteristicsFeatures
    geographic: GeographicCharacteristicsFeatures
    entities: LinkedEntitiesFeatures
    temporal: TemporalFeatures
