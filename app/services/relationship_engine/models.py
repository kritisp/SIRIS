from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    SHARED_HIGH_CONFIDENCE_PERSON = "SHARED_HIGH_CONFIDENCE_PERSON"
    POSSIBLE_PERSON_RELATIONSHIP = "POSSIBLE_PERSON_RELATIONSHIP"
    SHARED_PHONE = "SHARED_PHONE"
    SHARED_VEHICLE = "SHARED_VEHICLE"
    SHARED_LOCATION = "SHARED_LOCATION"
    SIMILAR_MODUS_OPERANDI = "SIMILAR_MODUS_OPERANDI"
    SIMILAR_CRIME_CATEGORY = "SIMILAR_CRIME_CATEGORY"
    SIMILAR_LEGAL_SECTIONS = "SIMILAR_LEGAL_SECTIONS"
    TEMPORAL_PROXIMITY = "TEMPORAL_PROXIMITY"


class SignalCertainty(str, Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    POSSIBLE = "POSSIBLE"
    WEAK_UNVERIFIED = "WEAK_UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"


class RelationshipSignal(BaseModel):
    """Represents an individual, evidence-backed relationship signal extracted between two cases."""
    relationship_type: RelationshipType
    source_case_id: str
    target_case_id: str
    raw_score: float = Field(ge=0.0, le=1.0)
    certainty: SignalCertainty
    evidence: List[str] = Field(default_factory=list)
    explanation: str
    supporting_entity_ids: List[str] = Field(default_factory=list)
    provenance: str
    uncertainty_note: Optional[str] = None


class CaseRelationshipAnalysis(BaseModel):
    """Structured collection of relationship signals discovered between two cases."""
    source_case_id: str
    target_case_id: str
    signals: List[RelationshipSignal] = Field(default_factory=list)
    summary_explanation: str
