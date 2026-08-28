from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.normalization.models import EntityType


class ResolutionDecision(str, Enum):
    HIGH_CONFIDENCE_MATCH = "HIGH_CONFIDENCE_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    NO_MATCH = "NO_MATCH"


class SignalStatus(str, Enum):
    MATCH = "MATCH"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"


class SignalEvidence(BaseModel):
    """Represents a specific matching or conflicting evidence signal."""
    name: str
    raw_score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    weighted_score: float = Field(ge=0.0, le=1.0)
    status: SignalStatus
    description: Optional[str] = None


class ResolutionResult(BaseModel):
    """Structured, evidence-aware entity resolution result emitted by Step 3C."""
    source_entity_id: str
    candidate_entity_id: str
    entity_type: EntityType
    overall_score: float = Field(ge=0.0, le=1.0)
    decision: ResolutionDecision
    matching_signals: List[SignalEvidence] = Field(default_factory=list)
    conflicting_signals: List[SignalEvidence] = Field(default_factory=list)
    unavailable_signals: List[str] = Field(default_factory=list)
    explanation: str
