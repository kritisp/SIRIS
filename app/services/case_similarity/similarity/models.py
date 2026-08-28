from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SignalStatus(str, Enum):
    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    MISMATCH = "MISMATCH"
    UNAVAILABLE = "UNAVAILABLE"


class SimilarityLevel(str, Enum):
    SELF_COMPARISON = "SELF_COMPARISON"
    HIGH_SIMILARITY = "HIGH_SIMILARITY"
    MODERATE_SIMILARITY = "MODERATE_SIMILARITY"
    LOW_SIMILARITY = "LOW_SIMILARITY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CaseSimilaritySignal(BaseModel):
    """Represents a specific multi-signal similarity component between two cases."""
    signal_name: str
    raw_score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    weighted_score: float = Field(ge=0.0, le=1.0)
    status: SignalStatus
    evidence: List[str] = Field(default_factory=list)
    explanation: str


class CaseSimilarityResult(BaseModel):
    """Complete, strongly typed, explainable case similarity evaluation result."""
    source_case_id: str
    candidate_case_id: str
    overall_score: float = Field(ge=0.0, le=1.0)
    similarity_level: SimilarityLevel
    signals: List[CaseSimilaritySignal] = Field(default_factory=list)
    strongest_evidence: List[str] = Field(default_factory=list)
    explanation: str
