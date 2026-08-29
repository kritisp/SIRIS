from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class WorkspaceContext(BaseModel):
    """Context for authorization boundary and multi-tenant investigation workspace."""
    investigator_id: Optional[str] = Field(default=None, description="Identifier of the investigating officer")
    station_id: Optional[str] = Field(default=None, description="Primary police station of the caller")
    role: Optional[str] = Field(default="INVESTIGATOR", description="Role/RBAC permission level")
    workspace_id: Optional[str] = Field(default=None, description="Active investigation workspace ID")


class IntelligenceAnalysisRequest(BaseModel):
    """Structured request payload for Central Intelligence Engine analysis."""
    target_case_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific Case UUIDs or FIR numbers to analyze"
    )
    target_station_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of police station IDs to scope cross-station analysis"
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Optional temporal start boundary for case window"
    )
    end_date: Optional[date] = Field(
        default=None,
        description="Optional temporal end boundary for case window"
    )
    analytical_scope: Optional[str] = Field(
        default="FULL",
        description="Analytical scope filter: FULL, CROSS_STATION, COMMUNITY, MULTI_HOP"
    )
    max_traversal_depth: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum graph hop traversal depth (1 to 5)"
    )
    max_cases: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of cases to include in single analysis batch (1 to 100)"
    )
    workspace_context: Optional[WorkspaceContext] = Field(
        default=None,
        description="Optional authorization & workspace context for RBAC enforcement"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_case_ids": ["FIR/2026/SYN_001", "FIR/2026/SYN_004"],
                "target_station_ids": ["PS_BBSR_SYN1", "PS_CTC_SYN2"],
                "analytical_scope": "FULL",
                "max_traversal_depth": 3,
                "max_cases": 50,
                "workspace_context": {
                    "investigator_id": "OFFICER_102",
                    "station_id": "PS_BBSR_SYN1",
                    "role": "INVESTIGATOR"
                }
            }
        }
    )


class MultiHopPathHop(BaseModel):
    """Individual node or edge hop representation within a multi-hop structural path."""
    step: int = Field(..., description="1-based step index along the structural path")
    from_node_id: str = Field(..., description="Source node ID or alias")
    from_node_type: str = Field(..., description="Source node category: Case, Person, Vehicle, Phone, Location")
    from_node_label: str = Field(..., description="Human readable label or alias")
    relationship_type: str = Field(..., description="Connecting graph relationship e.g. LINKED_TO, ASSOCIATED_WITH")
    to_node_id: str = Field(..., description="Destination node ID or alias")
    to_node_type: str = Field(..., description="Destination node category")
    to_node_label: str = Field(..., description="Destination label or alias")
    confidence_score: Optional[float] = Field(default=None, description="Relationship confidence score if applicable")


class MultiHopPathInfo(BaseModel):
    """Complete multi-hop path representation connecting cases across graph entities."""
    path_id: str = Field(..., description="Unique structural path identifier")
    start_case_alias: str = Field(..., description="Origin case identifier")
    end_case_alias: str = Field(..., description="Destination case identifier")
    total_hops: int = Field(..., description="Number of edges traversed in path")
    path_summary: str = Field(..., description="Human-readable path summary description")
    hops: List[MultiHopPathHop] = Field(default_factory=list, description="Ordered hops forming the structural path")


class IntelligenceAnalyticalMetadata(BaseModel):
    """Execution metrics and metadata for Central Intelligence analysis."""
    cases_evaluated_count: int = Field(..., description="Number of cases evaluated")
    stations_involved_count: int = Field(..., description="Number of police stations involved")
    patterns_detected_count: int = Field(..., description="Number of patterns detected")
    communities_detected_count: int = Field(..., description="Number of graph communities detected")
    multi_hop_paths_count: int = Field(..., description="Number of multi-hop structural paths discovered")
    traversal_depth_used: int = Field(..., description="Graph traversal depth executed")
    execution_time_ms: float = Field(..., description="Pipeline execution wall-clock time in milliseconds")
    scope_applied: str = Field(..., description="Scope filter applied")
    authorization_context_applied: bool = Field(..., description="Whether workspace context was supplied")


class IntelligenceAnalysisResponse(BaseModel):
    """Unified API response returned by POST /api/v1/intelligence/analyze."""
    report: Any = Field(
        ...,
        description="Police-facing intelligence report containing sanitized and back-mapped findings"
    )
    analytical_metadata: IntelligenceAnalyticalMetadata = Field(
        ...,
        description="Execution metrics and metadata for the analytical pipeline run"
    )
    multi_hop_paths: List[MultiHopPathInfo] = Field(
        default_factory=list,
        description="Discovered multi-hop structural paths across cases and graph entities"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report": {
                    "reasoning_id": "reasoning_998877",
                    "status": "SUCCESS",
                    "provider_used": "groq",
                    "summary": "Cross-station structural analysis revealed repeated suspect and vehicle associations.",
                    "key_observations": [
                        {
                            "statement": "Synthetic Person 1 (Debendra Swain) was identified across Saheed Nagar PS and Cuttack City PS cases.",
                            "source_case_aliases": ["FIR/2026/SYN_001", "FIR/2026/SYN_004"]
                        }
                    ],
                    "recommended_followups": [
                        {
                            "statement": "Investigating officers may verify vehicle timelines for OD02SYN1111."
                        }
                    ],
                    "limitations": [
                        "Analytical findings represent empirical structural observations."
                    ]
                },
                "analytical_metadata": {
                    "cases_evaluated_count": 5,
                    "stations_involved_count": 2,
                    "patterns_detected_count": 4,
                    "communities_detected_count": 1,
                    "multi_hop_paths_count": 2,
                    "traversal_depth_used": 3,
                    "execution_time_ms": 142.5,
                    "scope_applied": "FULL",
                    "authorization_context_applied": True
                },
                "multi_hop_paths": [
                    {
                        "path_id": "path_001",
                        "start_case_alias": "FIR/2026/SYN_001",
                        "end_case_alias": "FIR/2026/SYN_004",
                        "total_hops": 4,
                        "path_summary": "FIR/2026/SYN_001 -> Person 1 -> OD02SYN1111 -> FIR/2026/SYN_004",
                        "hops": []
                    }
                ]
            }
        }
    )
