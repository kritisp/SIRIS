from typing import List
from pydantic import BaseModel, Field
from app.normalization.models import EntityType


class CandidatePair(BaseModel):
    """Structured candidate pair object emitted by Candidate Generation / Blocking Engine."""
    entity_type: EntityType
    source_entity_id: str
    candidate_entity_id: str
    blocking_signals: List[str] = Field(default_factory=list)
