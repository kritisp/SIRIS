import abc
import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GraphNodeLabel(str, enum.Enum):
    CASE = "Case"
    PERSON = "Person"
    VEHICLE = "Vehicle"
    PHONE = "Phone"
    LOCATION = "Location"
    EVIDENCE = "Evidence"
    LEGAL_SECTION = "LegalSection"


class GraphRelationshipType(str, enum.Enum):
    INVOLVED_IN = "INVOLVED_IN"
    HAS_EVIDENCE = "HAS_EVIDENCE"
    INVOLVES_VEHICLE = "INVOLVES_VEHICLE"
    USES_PHONE = "USES_PHONE"
    OCCURRED_AT = "OCCURRED_AT"
    HAS_SECTION = "HAS_SECTION"


class GraphNode(BaseModel):
    id: str = Field(..., description="Unique entity ID (matching Postgres UUID)")
    label: GraphNodeLabel = Field(..., description="Neo4j node primary label")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Node attributes")


class GraphRelationship(BaseModel):
    source_id: str = Field(..., description="Source node ID")
    source_label: GraphNodeLabel = Field(..., description="Source node label")
    target_id: str = Field(..., description="Target node ID")
    target_label: GraphNodeLabel = Field(..., description="Target node label")
    rel_type: GraphRelationshipType = Field(..., description="Neo4j relationship type")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Relationship edge properties")


class IGraphSyncProvider(abc.ABC):
    """Abstract provider interface for future PostgreSQL -> Neo4j projection pipeline."""

    @abc.abstractmethod
    def sync_case(self, case_id: str) -> bool:
        """Projects a single case and its connected entities into Neo4j."""
        pass

    @abc.abstractmethod
    def sync_batch_cases(self, case_ids: List[str]) -> int:
        """Projects a batch of cases into Neo4j."""
        pass
