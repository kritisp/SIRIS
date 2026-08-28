from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    PERSON = "PERSON"
    PHONE = "PHONE"
    VEHICLE = "VEHICLE"
    LOCATION = "LOCATION"
    EVIDENCE = "EVIDENCE"
    MO = "MO"
    DATETIME = "DATETIME"


class NormalizedEntity(BaseModel):
    """Reusable internal normalized entity representation for SIRIS Central Engine."""
    entity_type: EntityType
    raw_value: str
    normalized_value: str
    phonetic_value: Optional[str] = None
    tokens: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
