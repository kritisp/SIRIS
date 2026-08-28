from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.services.relationship_engine.models import RelationshipSignal


class RelationshipConfidenceLevel(str, Enum):
    SELF_COMPARISON = "SELF_COMPARISON"
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class SignalFamily(str, Enum):
    PERSON_IDENTITY = "PERSON_IDENTITY"
    CONTACT = "CONTACT"
    VEHICLE = "VEHICLE"
    LOCATION = "LOCATION"
    BEHAVIORAL = "BEHAVIORAL"
    LEGAL = "LEGAL"
    TEMPORAL = "TEMPORAL"


class RelationshipConfidenceAssessment(BaseModel):
    """Aggregated, evidence-backed relationship confidence assessment between two cases emitted by Step 5B."""
    source_case_id: str
    target_case_id: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_level: RelationshipConfidenceLevel
    contributing_signals: List[RelationshipSignal] = Field(default_factory=list)
    high_confidence_signals: List[RelationshipSignal] = Field(default_factory=list)
    possible_signals: List[RelationshipSignal] = Field(default_factory=list)
    weak_signals: List[RelationshipSignal] = Field(default_factory=list)
    conflicting_or_cautionary_signals: List[str] = Field(default_factory=list)
    contributing_families: List[SignalFamily] = Field(default_factory=list)
    evidence_summary: str
    explanation: str
    uncertainty_notes: List[str] = Field(default_factory=list)
    provenance: str = "Step 5A Relationship Signals"
    methodology_version: str = "relationship-confidence-v1"
