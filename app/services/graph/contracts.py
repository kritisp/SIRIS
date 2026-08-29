import uuid
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.services.relationship_engine.confidence.models import RelationshipConfidenceAssessment


def canonicalize_case_pair(id1: str, id2: str) -> tuple[str, str, str]:
    """Returns (min_case_id, max_case_id, canonical_relationship_key) for any pair of case IDs.
    
    Raises ValueError if id1 and id2 are identical or malformed UUIDs.
    """
    u1 = uuid.UUID(str(id1))
    u2 = uuid.UUID(str(id2))

    if u1 == u2:
        raise ValueError("Self-comparison relationships between identical case IDs are invalid.")

    s1, s2 = sorted([str(u1), str(u2)])
    return s1, s2, f"{s1}:{s2}:RELATED_TO"


# =====================================================================
# 1. NODE PROJECTION CONTRACTS
# =====================================================================

class BaseGraphNode(BaseModel):
    """Base projection contract for all Neo4j graph nodes."""
    node_id: str
    source_system: str = "postgresql"
    source_id: str
    projection_version: str = "graph-v1"

    @field_validator("node_id", "source_id")
    def validate_uuid_string(cls, v: str) -> str:
        # Ensures node_id is a valid UUID string
        uuid.UUID(str(v))
        return str(v)


class CaseGraphNode(BaseGraphNode):
    """Projection contract for (:Case) graph nodes."""
    label: str = "Case"
    fir_number: str
    station_id: str
    police_station: str
    district: str
    state: str
    registration_date: str  # YYYY-MM-DD
    incident_date: Optional[str] = None
    crime_type: str
    crime_category: str
    status: str = "UNDER_INVESTIGATION"


class PersonGraphNode(BaseGraphNode):
    """Projection contract for (:Person) graph nodes."""
    label: str = "Person"
    name: str
    normalized_name: Optional[str] = None
    gender: Optional[str] = None
    identifier_hash: Optional[str] = None
    # Note: date_of_birth and address are excluded from Neo4j to protect PII.


class VehicleGraphNode(BaseGraphNode):
    """Projection contract for (:Vehicle) graph nodes."""
    label: str = "Vehicle"
    registration_number: str
    normalized_reg: Optional[str] = None
    vehicle_type: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None


class PhoneGraphNode(BaseGraphNode):
    """Projection contract for (:Phone) graph nodes."""
    label: str = "Phone"
    normalized_number: str
    number_hash: Optional[str] = None


class LocationGraphNode(BaseGraphNode):
    """Projection contract for (:Location) graph nodes."""
    label: str = "Location"
    locality: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class EvidenceGraphNode(BaseGraphNode):
    """Projection contract for (:Evidence) graph nodes."""
    label: str = "Evidence"
    evidence_type: str
    source: Optional[str] = None
    status: str = "COLLECTED"


class LegalSectionGraphNode(BaseGraphNode):
    """Projection contract for (:LegalSection) graph nodes."""
    label: str = "LegalSection"
    code: str
    title: str
    law_name: str = "IPC"


# =====================================================================
# 2. BASE RELATIONSHIP CONTRACT
# =====================================================================

class BaseGraphRelationship(BaseModel):
    """Base contract for graph relationships enforcing UUID validation on ID fields."""

    @field_validator(
        "case_id",
        "person_id",
        "vehicle_id",
        "phone_id",
        "location_id",
        "evidence_id",
        "legal_section_id",
        "source_case_id",
        "target_case_id",
        mode="before",
        check_fields=False,
    )
    def validate_uuid_relationship_field(cls, v: str) -> str:
        if v is not None:
            uuid.UUID(str(v))
            return str(v)
        return v


# =====================================================================
# 3. ENTITY ASSOCIATION RELATIONSHIP CONTRACTS
# =====================================================================

class CasePersonRelContract(BaseGraphRelationship):
    """Contract for (:Case)-[:HAS_PERSON {role: ...}]->(:Person)."""
    type: str = "HAS_PERSON"
    case_id: str
    person_id: str
    role: str = "OTHER"
    projection_version: str = "graph-v1"


class CaseVehicleRelContract(BaseGraphRelationship):
    """Contract for (:Case)-[:HAS_VEHICLE {role: ...}]->(:Vehicle)."""
    type: str = "HAS_VEHICLE"
    case_id: str
    vehicle_id: str
    role: str = "OTHER"
    projection_version: str = "graph-v1"


class CasePhoneRelContract(BaseGraphRelationship):
    """Contract for (:Case)-[:HAS_PHONE]->(:Phone)."""
    type: str = "HAS_PHONE"
    case_id: str
    phone_id: str
    projection_version: str = "graph-v1"


class CaseLocationRelContract(BaseGraphRelationship):
    """Contract for (:Case)-[:HAS_LOCATION]->(:Location)."""
    type: str = "HAS_LOCATION"
    case_id: str
    location_id: str
    projection_version: str = "graph-v1"


class CaseEvidenceRelContract(BaseGraphRelationship):
    """Contract for (:Case)-[:HAS_EVIDENCE {evidence_type: ...}]->(:Evidence)."""
    type: str = "HAS_EVIDENCE"
    case_id: str
    evidence_id: str
    evidence_type: str
    projection_version: str = "graph-v1"


class CaseLegalSectionRelContract(BaseGraphRelationship):
    """Contract for (:Case)-[:HAS_LEGAL_SECTION]->(:LegalSection)."""
    type: str = "HAS_LEGAL_SECTION"
    case_id: str
    legal_section_id: str
    projection_version: str = "graph-v1"


# =====================================================================
# 4. CASE-TO-CASE ANALYTICAL RELATIONSHIP CONTRACT
# =====================================================================

class RelatedToCaseRelContract(BaseGraphRelationship):
    """Contract for (:Case)-[:RELATED_TO]->(:Case) representing Step 5B assessments."""
    type: str = "RELATED_TO"
    canonical_relationship_key: str
    source_case_id: str  # min(case_id_a, case_id_b)
    target_case_id: str  # max(case_id_a, case_id_b)
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_level: str
    contributing_families: List[str] = Field(default_factory=list)
    evidence_summary: str
    explanation: str
    uncertainty_notes: List[str] = Field(default_factory=list)
    provenance: str = "Step 5A Relationship Signals"
    methodology_version: str = "relationship-confidence-v1"
    projection_version: str = "graph-v1"

    @classmethod
    def from_assessment(cls, assessment: RelationshipConfidenceAssessment) -> "RelatedToCaseRelContract":
        """Factory creating a canonicalized RelatedToCaseRelContract from a Step 5B assessment."""
        src_min, tgt_max, key = canonicalize_case_pair(
            assessment.source_case_id, assessment.target_case_id
        )
        return cls(
            canonical_relationship_key=key,
            source_case_id=src_min,
            target_case_id=tgt_max,
            confidence_score=assessment.confidence_score,
            confidence_level=assessment.confidence_level.value,
            contributing_families=[f.value for f in assessment.contributing_families],
            evidence_summary=assessment.evidence_summary,
            explanation=assessment.explanation,
            uncertainty_notes=assessment.uncertainty_notes,
            provenance=assessment.provenance,
            methodology_version=assessment.methodology_version,
            projection_version=assessment.projection_version,
        )
