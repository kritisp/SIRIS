import hashlib
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.case import Case
from app.services.graph.analytics import NetworkAnalyticsResult
from app.services.graph.community import CommunityDetectionResult
from app.services.graph.traversal import GraphTraversalResult
from app.services.pattern_engine import PatternDetectionResult, PatternObservation
from app.services.relationship_engine import RelationshipConfidenceAssessment

logger = logging.getLogger(__name__)

EXPLAINABLE_INTELLIGENCE_METHODOLOGY_VERSION = "explainable-intelligence-v1"

# Explicit non-inference safeguards against legal/guilt conclusions
FORBIDDEN_INFERENCE_TERMS: Set[str] = {
    "guilty",
    "culprit",
    "perpetrator",
    "mastermind",
    "accomplice",
    "conspiracy",
    "criminal network",
    "offender",
    "criminal organization",
    "definitely committed",
    "certainly committed",
}


# =====================================================================
# 1. EVIDENCE CLASSIFICATION & CONTRACTS
# =====================================================================

class EvidenceCategory(str, Enum):
    """Classification taxonomy for explainable analytical evidence."""

    DIRECT_OBSERVATION = "DIRECT_OBSERVATION"
    STRUCTURED_ENTITY_ASSOCIATION = "STRUCTURED_ENTITY_ASSOCIATION"
    RELATIONSHIP_EVIDENCE = "RELATIONSHIP_EVIDENCE"
    GRAPH_STRUCTURAL_SIGNAL = "GRAPH_STRUCTURAL_SIGNAL"
    PATTERN_SIGNAL = "PATTERN_SIGNAL"
    ANALYTICAL_DERIVATION = "ANALYTICAL_DERIVATION"
    LIMITATION = "LIMITATION"


class ExplainabilitySignal(BaseModel):
    """Individual analytical signal contributing to an explanation."""

    signal_id: str
    category: EvidenceCategory
    source_component: str
    signal_summary: str
    weight_or_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class ExplainabilityEvidence(BaseModel):
    """Structured evidence item supporting an explanation."""

    evidence_id: str
    category: EvidenceCategory
    title: str
    description: str
    source_type: str
    source_id: str
    supporting_signals: List[ExplainabilitySignal] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class ExplainabilityAssessment(BaseModel):
    """Top-level structured, evidence-grounded explanation payload."""

    explanation_id: str
    subject_id: str
    subject_type: str
    title: str
    observation: str
    explanation: str
    supporting_case_ids: List[str] = Field(default_factory=list)
    supporting_entity_ids: List[str] = Field(default_factory=list)
    supporting_relationship_ids: List[str] = Field(default_factory=list)
    supporting_pattern_ids: List[str] = Field(default_factory=list)
    supporting_community_ids: List[str] = Field(default_factory=list)
    supporting_connector_ids: List[str] = Field(default_factory=list)
    evidence_items: List[ExplainabilityEvidence] = Field(default_factory=list)
    contributing_signals: List[ExplainabilitySignal] = Field(default_factory=list)
    confidence_reference: Optional[Dict[str, Any]] = None
    limitations: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    methodology_version: str = EXPLAINABLE_INTELLIGENCE_METHODOLOGY_VERSION

    @field_validator("title", "observation", "explanation")
    def validate_non_inference_language(cls, v: str) -> str:
        lower_v = v.lower()
        for term in FORBIDDEN_INFERENCE_TERMS:
            if term in lower_v:
                raise ValueError(
                    f"Forbidden inference term '{term}' detected in explainability output. Explainable Intelligence must remain neutral, observation-based, and non-judgmental."
                )
        return v

    @field_validator("limitations")
    def validate_limitations_language(cls, v: List[str]) -> List[str]:
        for lim in v:
            lower_lim = lim.lower()
            for term in FORBIDDEN_INFERENCE_TERMS:
                if term in lower_lim:
                    raise ValueError(
                        f"Forbidden inference term '{term}' detected in limitation string. Explainable Intelligence must remain non-judgmental."
                    )
        return v


class ExplainabilityRequest(BaseModel):
    """Input contract requesting analytical explanations."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cases: List[Case] = Field(default_factory=list)
    pattern_result: Optional[PatternDetectionResult] = None
    confidence_assessments: Optional[List[RelationshipConfidenceAssessment]] = None
    graph_analytics_result: Optional[NetworkAnalyticsResult] = None
    community_detection_result: Optional[CommunityDetectionResult] = None
    traversal_results: Optional[List[GraphTraversalResult]] = None
    target_subject_id: Optional[str] = None
    methodology_version: str = EXPLAINABLE_INTELLIGENCE_METHODOLOGY_VERSION


class ExplainabilityResult(BaseModel):
    """Output contract containing generated explainability assessments."""

    total_explanations_generated: int
    explanation_distribution: Dict[str, int] = Field(default_factory=dict)
    explanations: List[ExplainabilityAssessment] = Field(default_factory=list)
    methodology_version: str = EXPLAINABLE_INTELLIGENCE_METHODOLOGY_VERSION


# =====================================================================
# 2. EXPLAINABILITY ENGINE SERVICE
# =====================================================================

class ExplainabilityEngine:
    """Deterministic, read-only Explainable Intelligence Engine transforming analytical outputs into structured, evidence-backed explanations."""

    def explain_analytical_findings(self, request: ExplainabilityRequest) -> ExplainabilityResult:
        """Evaluates input cases, patterns, assessments, and graph analytical results to produce structured explanations."""
        explanations: List[ExplainabilityAssessment] = []

        # 1. Explain Pattern Observations (Step 6)
        if request.pattern_result and request.pattern_result.patterns:
            for pat in request.pattern_result.patterns:
                if not request.target_subject_id or request.target_subject_id in pat.case_ids or request.target_subject_id in pat.entity_ids or request.target_subject_id == pat.pattern_id:
                    explanations.append(self._explain_pattern_observation(pat, request))

        # 2. Explain Step 5B Relationship Confidence Assessments
        if request.confidence_assessments:
            for assessment in request.confidence_assessments:
                if not request.target_subject_id or request.target_subject_id in (assessment.source_case_id, assessment.target_case_id, assessment.canonical_relationship_key):
                    explanations.append(self._explain_relationship_assessment(assessment, request))

        # 3. Explain Community Clusters (Step 5G)
        if request.community_detection_result and request.community_detection_result.communities:
            for comm in request.community_detection_result.communities:
                member_ids = [m.node_id for m in comm.members]
                if not request.target_subject_id or request.target_subject_id in member_ids or request.target_subject_id == comm.community_id:
                    explanations.append(self._explain_community_cluster(comm, request))

        # 4. Explain Network Connectors (Step 5F)
        if request.graph_analytics_result and request.graph_analytics_result.node_metrics:
            connectors = [nm for nm in request.graph_analytics_result.node_metrics if nm.is_connector_node]
            for conn in connectors:
                if not request.target_subject_id or request.target_subject_id == conn.node_id:
                    explanations.append(self._explain_network_connector(conn, request))

        # Deduplicate explanations by deterministic explanation_id
        dedup_map: Dict[str, ExplainabilityAssessment] = {}
        for exp in explanations:
            if exp.explanation_id not in dedup_map:
                dedup_map[exp.explanation_id] = exp

        filtered_explanations = list(dedup_map.values())

        # Sort deterministically: 1. supporting_cases count desc, 2. subject_type asc, 3. explanation_id asc
        filtered_explanations.sort(
            key=lambda e: (-len(e.supporting_case_ids), e.subject_type, e.explanation_id)
        )

        # Compute summary distribution
        dist: Dict[str, int] = {}
        for e in filtered_explanations:
            dist[e.subject_type] = dist.get(e.subject_type, 0) + 1

        return ExplainabilityResult(
            total_explanations_generated=len(filtered_explanations),
            explanation_distribution=dict(sorted(dist.items())),
            explanations=filtered_explanations,
            methodology_version=request.methodology_version,
        )

    # =====================================================================
    # PRIVATE EXPLANATION GENERATORS
    # =====================================================================

    def _explain_pattern_observation(self, pat: PatternObservation, request: ExplainabilityRequest) -> ExplainabilityAssessment:
        subject_id = pat.entity_ids[0] if pat.entity_ids else (pat.case_ids[0] if pat.case_ids else pat.pattern_id)
        subject_type = pat.entity_types[0] if pat.entity_types else ("Case" if pat.case_ids else "Pattern")

        obs_text = f"Pattern observation '{pat.title}' was detected with structural strength {pat.structural_strength} across {pat.occurrence_count} occurrences."
        exp_text = f"The analytical pattern was derived because {pat.description} Supporting signals include: {', '.join(pat.supporting_signals)}."

        signals = [
            ExplainabilitySignal(
                signal_id=self._generate_id("sig", [pat.pattern_id, s]),
                category=EvidenceCategory.PATTERN_SIGNAL,
                source_component="Step 6 Pattern Intelligence Engine",
                signal_summary=s,
                weight_or_confidence=pat.structural_strength,
                provenance={"pattern_id": pat.pattern_id},
            )
            for s in pat.supporting_signals
        ]

        evidence = [
            ExplainabilityEvidence(
                evidence_id=self._generate_id("ev", [pat.pattern_id, "pattern_source"]),
                category=EvidenceCategory.PATTERN_SIGNAL,
                title=pat.title,
                description=pat.description,
                source_type="PatternObservation",
                source_id=pat.pattern_id,
                supporting_signals=signals,
                provenance=pat.provenance,
            )
        ]

        limitations = [
            "Shared pattern observations reflect empirical structural recurrence across cases.",
            "Pattern recurrence does not establish common criminal intent, legal guilt, or single-actor responsibility.",
        ]
        if pat.pattern_type.value == "MODUS_OPERANDI":
            limitations.append("Case similarity and operational crime characteristics do not prove that the same person or entity committed all associated cases.")

        exp_id = self._generate_id("exp:pattern", [pat.pattern_id, subject_id])

        return ExplainabilityAssessment(
            explanation_id=exp_id,
            subject_id=subject_id,
            subject_type=subject_type,
            title=f"Explanation for {pat.title}",
            observation=obs_text,
            explanation=exp_text,
            supporting_case_ids=pat.case_ids,
            supporting_entity_ids=pat.entity_ids,
            supporting_relationship_ids=[],
            supporting_pattern_ids=[pat.pattern_id],
            supporting_community_ids=[pat.provenance["community_id"]] if "community_id" in pat.provenance else [],
            supporting_connector_ids=[pat.provenance["connector_node_id"]] if "connector_node_id" in pat.provenance else [],
            evidence_items=evidence,
            contributing_signals=signals,
            confidence_reference=None,
            limitations=limitations,
            provenance={
                "pattern_id": pat.pattern_id,
                "source_cases": pat.case_ids,
                "source_entities": pat.entity_ids,
                "methodology": request.methodology_version,
            },
            methodology_version=request.methodology_version,
        )

    def _explain_relationship_assessment(
        self, assessment: RelationshipConfidenceAssessment, request: ExplainabilityRequest
    ) -> ExplainabilityAssessment:
        subject_id = assessment.canonical_relationship_key
        obs_text = f"Relationship link between Case {assessment.source_case_id} and Case {assessment.target_case_id} evaluated with {assessment.confidence_level.value} confidence (score: {assessment.confidence_score})."
        exp_text = f"Step 5B Confidence Assessment: {assessment.evidence_summary} {assessment.explanation}"

        signals = [
            ExplainabilitySignal(
                signal_id=self._generate_id("sig", [assessment.canonical_relationship_key, fam.value]),
                category=EvidenceCategory.RELATIONSHIP_EVIDENCE,
                source_component="Step 5B Relationship Confidence Engine",
                signal_summary=f"Contributing Signal Family: {fam.value}",
                weight_or_confidence=assessment.confidence_score,
                provenance={"canonical_key": assessment.canonical_relationship_key},
            )
            for fam in assessment.contributing_families
        ]

        evidence = [
            ExplainabilityEvidence(
                evidence_id=self._generate_id("ev", [assessment.canonical_relationship_key, "5b_confidence"]),
                category=EvidenceCategory.RELATIONSHIP_EVIDENCE,
                title=f"Step 5B Assessment ({assessment.confidence_level.value})",
                description=assessment.evidence_summary,
                source_type="RelationshipConfidenceAssessment",
                source_id=assessment.canonical_relationship_key,
                supporting_signals=signals,
                provenance={
                    "source_case_id": assessment.source_case_id,
                    "target_case_id": assessment.target_case_id,
                    "confidence_score": assessment.confidence_score,
                },
            )
        ]

        limitations = [
            "Step 5B confidence scores measure analytical relationship strength based on shared entity attributes and signals.",
            "Relationship confidence does not establish joint illegal intent or legal liability.",
        ]
        if assessment.uncertainty_notes:
            limitations.extend(assessment.uncertainty_notes)

        exp_id = self._generate_id("exp:relationship", [assessment.canonical_relationship_key])

        return ExplainabilityAssessment(
            explanation_id=exp_id,
            subject_id=subject_id,
            subject_type="CasePair",
            title=f"Explanation for Relationship Link ({assessment.confidence_level.value})",
            observation=obs_text,
            explanation=exp_text,
            supporting_case_ids=sorted([assessment.source_case_id, assessment.target_case_id]),
            supporting_entity_ids=[],
            supporting_relationship_ids=[assessment.canonical_relationship_key],
            supporting_pattern_ids=[],
            supporting_community_ids=[],
            supporting_connector_ids=[],
            evidence_items=evidence,
            contributing_signals=signals,
            confidence_reference={
                "confidence_score": assessment.confidence_score,
                "confidence_level": assessment.confidence_level.value,
                "authority": "Step 5B Relationship Confidence Engine",
            },
            limitations=limitations,
            provenance={
                "canonical_relationship_key": assessment.canonical_relationship_key,
                "source_case_id": assessment.source_case_id,
                "target_case_id": assessment.target_case_id,
                "methodology": request.methodology_version,
            },
            methodology_version=request.methodology_version,
        )

    def _explain_community_cluster(self, comm: Any, request: ExplainabilityRequest) -> ExplainabilityAssessment:
        subject_id = comm.community_id
        case_ids = sorted([m.node_id for m in comm.members if m.node_type == "Case"])
        entity_ids = sorted([m.node_id for m in comm.members if m.node_type != "Case"])

        obs_text = f"Graph structural community '{comm.community_id}' identified with {comm.member_count} member nodes and density {comm.density}."
        exp_text = f"Community cluster derived from graph structural modularity. Spans multiple police stations: {comm.spans_cross_station}. Total station count: {comm.station_count}."

        signals = [
            ExplainabilitySignal(
                signal_id=self._generate_id("sig", [comm.community_id, "density"]),
                category=EvidenceCategory.GRAPH_STRUCTURAL_SIGNAL,
                source_component="Step 5G Community Detection Engine",
                signal_summary=f"Community Structural Density: {comm.density}",
                weight_or_confidence=round(comm.density, 4),
                provenance={"community_id": comm.community_id},
            )
        ]

        evidence = [
            ExplainabilityEvidence(
                evidence_id=self._generate_id("ev", [comm.community_id, "graph_cluster"]),
                category=EvidenceCategory.GRAPH_STRUCTURAL_SIGNAL,
                title=f"Graph Structural Community ({comm.community_id})",
                description=obs_text,
                source_type="CommunityCluster",
                source_id=comm.community_id,
                supporting_signals=signals,
                provenance={"community_id": comm.community_id, "member_count": comm.member_count},
            )
        ]

        limitations = [
            "Community membership reflects graph structural connectivity under configured algorithmic criteria.",
            "Graph structural clustering does not establish joint illegal activity or organized group membership.",
        ]

        exp_id = self._generate_id("exp:community", [comm.community_id])

        return ExplainabilityAssessment(
            explanation_id=exp_id,
            subject_id=subject_id,
            subject_type="Community",
            title=f"Explanation for Graph Community ({comm.community_id})",
            observation=obs_text,
            explanation=exp_text,
            supporting_case_ids=case_ids,
            supporting_entity_ids=entity_ids,
            supporting_relationship_ids=[],
            supporting_pattern_ids=[],
            supporting_community_ids=[comm.community_id],
            supporting_connector_ids=[],
            evidence_items=evidence,
            contributing_signals=signals,
            confidence_reference=None,
            limitations=limitations,
            provenance={
                "community_id": comm.community_id,
                "member_count": comm.member_count,
                "density": comm.density,
                "methodology": request.methodology_version,
            },
            methodology_version=request.methodology_version,
        )

    def _explain_network_connector(self, conn: Any, request: ExplainabilityRequest) -> ExplainabilityAssessment:
        subject_id = conn.node_id
        betweenness = conn.centrality.betweenness_centrality if getattr(conn, "centrality", None) else 0.0

        obs_text = f"Network node '{conn.node_id}' ({conn.label}) identified as high-centrality connector node connecting {conn.connected_case_count} cases."
        exp_text = f"High structural centrality detected with total degree {conn.total_degree} and betweenness centrality {betweenness:.4f}. Role summary: {conn.connector_role_summary or 'Bridge Node'}."

        signals = [
            ExplainabilitySignal(
                signal_id=self._generate_id("sig", [conn.node_id, "betweenness"]),
                category=EvidenceCategory.GRAPH_STRUCTURAL_SIGNAL,
                source_component="Step 5F Network Analytics Engine",
                signal_summary=f"Betweenness Centrality: {betweenness:.4f}",
                weight_or_confidence=round(betweenness, 4),
                provenance={"node_id": conn.node_id},
            )
        ]

        evidence = [
            ExplainabilityEvidence(
                evidence_id=self._generate_id("ev", [conn.node_id, "connector_metric"]),
                category=EvidenceCategory.GRAPH_STRUCTURAL_SIGNAL,
                title=f"Network Connector Metric ({conn.label})",
                description=obs_text,
                source_type="NetworkNodeMetrics",
                source_id=conn.node_id,
                supporting_signals=signals,
                provenance={"node_id": conn.node_id, "total_degree": conn.total_degree},
            )
        ]

        limitations = [
            "High structural centrality indicates topological network position across analytical graph paths.",
            "Network centrality does not imply leadership, criminal responsibility, or operational intent.",
        ]

        exp_id = self._generate_id("exp:connector", [conn.node_id])

        return ExplainabilityAssessment(
            explanation_id=exp_id,
            subject_id=subject_id,
            subject_type=conn.label,
            title=f"Explanation for Network Connector Node ({conn.label}:{conn.node_id})",
            observation=obs_text,
            explanation=exp_text,
            supporting_case_ids=[],
            supporting_entity_ids=[conn.node_id],
            supporting_relationship_ids=[],
            supporting_pattern_ids=[],
            supporting_community_ids=[],
            supporting_connector_ids=[conn.node_id],
            evidence_items=evidence,
            contributing_signals=signals,
            confidence_reference=None,
            limitations=limitations,
            provenance={
                "node_id": conn.node_id,
                "label": conn.label,
                "betweenness": betweenness,
                "methodology": request.methodology_version,
            },
            methodology_version=request.methodology_version,
        )

    # =====================================================================
    # DETERMINISTIC ID HELPER
    # =====================================================================

    def _generate_id(self, prefix: str, items: List[str]) -> str:
        canonical_str = prefix + ":" + "|".join(sorted(items))
        digest = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}:{digest}"


explainability_engine = ExplainabilityEngine()
