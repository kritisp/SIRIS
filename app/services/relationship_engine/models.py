from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


def get_canonical_relationship_key(id1: str, id2: str) -> str:
    """Returns a deterministic, ordering-independent canonical relationship key for a case pair."""
    s1, s2 = sorted([str(id1), str(id2)])
    return f"{s1}:{s2}:RELATED_TO"


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
    HIGH_CONFIDENCE_ENTITY = "HIGH_CONFIDENCE_ENTITY"
    EXACT_ATTRIBUTE_MATCH = "EXACT_ATTRIBUTE_MATCH"
    CORRELATIONAL = "CORRELATIONAL"
    INFERRED_PATTERN = "INFERRED_PATTERN"
    CONTEXTUAL = "CONTEXTUAL"
    POSSIBLE_ENTITY = "POSSIBLE_ENTITY"
    WEAK_UNVERIFIED = "WEAK_UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"

    # Aliases for backwards compatibility
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE_ENTITY"
    POSSIBLE = "POSSIBLE_ENTITY"


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
    canonical_relationship_key: Optional[str] = None


class CaseRelationshipAnalysis(BaseModel):
    """Structured collection of relationship signals discovered between two cases."""
    source_case_id: str
    target_case_id: str
    signals: List[RelationshipSignal] = Field(default_factory=list)
    summary_explanation: str
    canonical_relationship_key: Optional[str] = None
