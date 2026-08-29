import time
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import date

from app.models.case import Case
from app.models.person import Person, CasePerson, PersonRole
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.models.phone import Phone, CasePhone
from app.models.location import Location
from app.schemas.intelligence import (
    IntelligenceAnalysisRequest,
    IntelligenceAnalysisResponse,
    IntelligenceAnalyticalMetadata,
    MultiHopPathInfo,
    MultiHopPathHop,
)
from app.services.graph import (
    canonicalize_case_pair,
    neo4j_connection_service,
    neo4j_graph_projection_service,
    GraphTraversalRequest,
    neo4j_graph_traversal_service,
    NetworkAnalyticsRequest,
    neo4j_network_analytics_service,
    CommunityDetectionRequest,
    neo4j_community_detection_service,
)
from app.services.relationship_engine import (
    RelationshipConfidenceAssessment,
    RelationshipConfidenceLevel,
    SignalFamily,
)
from app.services.pattern_engine import (
    PatternDetectionRequest,
    pattern_intelligence_engine,
)
from app.services.explainability_engine import (
    ExplainabilityRequest,
    explainability_engine,
)
from app.services.privacy_engine import (
    pii_privacy_boundary_engine,
    pii_backmapper,
)
from app.services.llm_reasoning_engine import (
    llm_reasoning_engine,
    ReasoningStatus,
)

logger = logging.getLogger(__name__)


class IntelligenceOrchestrationService:
    """Orchestrates Steps 3A–8 of the S.I.R.I.S. Central Intelligence Engine for API callers."""

    def analyze(
        self,
        request: IntelligenceAnalysisRequest,
        provided_cases: Optional[List[Case]] = None,
        db_session=None,
    ) -> IntelligenceAnalysisResponse:
        """Executes the full intelligence pipeline and returns structured Pydantic response."""
        start_time = time.perf_counter()

        # 1. Scope & Limit Validation
        max_cases = min(request.max_cases, 100) if request else 50
        max_depth = min(request.max_traversal_depth, 5) if request else 3

        # 2. Case Gathering (Use provided cases or load from DB/Memory)
        cases = provided_cases or []
        if not cases and request.target_case_ids and db_session:
            # Query PostgreSQL for cases by FIR or UUID
            from app.repositories.case_repository import CaseRepository
            repo = CaseRepository(db_session)
            found_cases = []
            for identifier in request.target_case_ids[:max_cases]:
                try:
                    case_uuid = uuid.UUID(identifier)
                    c = repo.get_by_id(case_uuid)
                except ValueError:
                    c = repo.get_by_fir_number(identifier)
                if c:
                    found_cases.append(c)
            cases = found_cases

        if not cases:
            # Safe Fallback when no cases matched target parameters
            return self._build_empty_response(request, start_time)

        # Truncate cases to max_cases limit
        cases = cases[:max_cases]
        stations_involved = set(c.station_id for c in cases if c.station_id)

        # 3. Step 5B Relationship Confidence Assessment
        assessments = self._compute_relationship_confidence(cases)

        # 4. Steps 5C–5D Neo4j Projection
        is_neo4j_healthy = False
        try:
            health = neo4j_connection_service.check_health()
            if health.status == "UP":
                is_neo4j_healthy = True
                for case_obj in cases:
                    neo4j_graph_projection_service.project_case_graph(case_obj)
                for ass in assessments:
                    neo4j_graph_projection_service.project_relationship_assessment(ass)
        except Exception as err:
            logger.warning(f"Neo4j projection skipped due to connection status: {err}")

        # 5. Step 5E Multi-hop Graph Traversal & Path Extraction
        multi_hop_paths = []
        if is_neo4j_healthy and cases:
            multi_hop_paths = self._extract_multi_hop_paths(cases[0], max_depth)

        # 6. Step 5F Network Analytics & Step 5G Community Detection
        net_res = None
        comm_res = None
        if is_neo4j_healthy and cases:
            try:
                net_res = neo4j_network_analytics_service.analyze_network(
                    NetworkAnalyticsRequest(target_node_id=str(cases[0].id))
                )
                comm_res = neo4j_community_detection_service.detect_communities(
                    CommunityDetectionRequest(minimum_community_size=2)
                )
            except Exception as err:
                logger.warning(f"Graph analytics evaluation fallback: {err}")

        # 7. Step 6 Pattern Intelligence
        pat_req = PatternDetectionRequest(
            cases=cases,
            graph_analytics_result=net_res,
            community_detection_result=comm_res,
            confidence_assessments=assessments,
        )
        pat_res = pattern_intelligence_engine.detect_patterns(pat_req)

        # 8. Step 7 Explainable Intelligence Findings
        exp_req = ExplainabilityRequest(
            cases=cases,
            pattern_result=pat_res,
            confidence_assessments=assessments,
            graph_analytics_result=net_res,
            community_detection_result=comm_res,
        )
        exp_res = explainability_engine.explain_analytical_findings(exp_req)

        # 9. Step 7.5 PII Privacy Boundary Engine
        deid_res = pii_privacy_boundary_engine.deidentify_explainability_result(exp_res, cases=cases)
        payload = deid_res.llm_safe_payload
        mapping = deid_res.private_mapping

        # 10. Step 8 LLM Reasoning Engine & Post-LLM Security Guards
        reasoning_res, police_report = llm_reasoning_engine.generate_reasoning_report(
            payload, private_mapping=mapping
        )

        # Ensure police_report is generated
        if not police_report:
            police_report = pii_backmapper.backmap_reasoning_result(reasoning_res, mapping)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        metadata = IntelligenceAnalyticalMetadata(
            cases_evaluated_count=len(cases),
            stations_involved_count=len(stations_involved),
            patterns_detected_count=pat_res.total_patterns_detected,
            communities_detected_count=comm_res.total_communities_detected if comm_res else 0,
            multi_hop_paths_count=len(multi_hop_paths),
            traversal_depth_used=max_depth,
            execution_time_ms=round(elapsed_ms, 2),
            scope_applied=request.analytical_scope if request else "FULL",
            authorization_context_applied=(request.workspace_context is not None) if request else False,
        )

        return IntelligenceAnalysisResponse(
            report=police_report,
            analytical_metadata=metadata,
            multi_hop_paths=multi_hop_paths,
        )

    def _compute_relationship_confidence(self, cases: List[Case]) -> List[RelationshipConfidenceAssessment]:
        """Calculates Step 5B pairwise relationship confidence assessments."""
        assessments = []
        for i in range(len(cases)):
            for j in range(i + 1, len(cases)):
                c1, c2 = cases[i], cases[j]
                shared_p = bool(set(p.person_id for p in c1.person_associations) & set(p.person_id for p in c2.person_associations))
                shared_v = bool(set(v.vehicle_id for v in c1.vehicle_associations) & set(v.vehicle_id for v in c2.vehicle_associations))
                shared_ph = bool(set(ph.phone_id for ph in c1.phone_associations) & set(ph.phone_id for ph in c2.phone_associations))

                if shared_p or shared_v or shared_ph:
                    score = 0.95 if (shared_p and shared_v) else (0.85 if shared_p else 0.70)
                    level = RelationshipConfidenceLevel.VERY_HIGH if score >= 0.85 else RelationshipConfidenceLevel.HIGH
                    _, _, rel_key = canonicalize_case_pair(str(c1.id), str(c2.id))

                    ass = RelationshipConfidenceAssessment(
                        source_case_id=str(c1.id),
                        target_case_id=str(c2.id),
                        canonical_relationship_key=rel_key,
                        confidence_score=score,
                        confidence_level=level,
                        contributing_families=[SignalFamily.PERSON_IDENTITY] if shared_p else [SignalFamily.VEHICLE],
                        evidence_summary=f"Pairwise confidence {score} link between {c1.fir_number} and {c2.fir_number}",
                        explanation="Shared entity link across case records.",
                        uncertainty_notes=[],
                    )
                    assessments.append(ass)
        return assessments

    def _extract_multi_hop_paths(self, target_case: Case, max_depth: int) -> List[MultiHopPathInfo]:
        """Traverses graph using Step 5E service and extracts multi-hop path visualizations."""
        paths: List[MultiHopPathInfo] = []
        try:
            trav_res = neo4j_graph_traversal_service.traverse(
                GraphTraversalRequest(start_node_id=str(target_case.id), max_depth=max_depth)
            )
            for idx, p_item in enumerate(trav_res.paths[:5]):
                path_hops = []
                for step_idx, hop in enumerate(p_item.hops):
                    path_hops.append(
                        MultiHopPathHop(
                            step=step_idx + 1,
                            from_node_id=hop.start_node_id,
                            from_node_type=hop.start_node_type or "Entity",
                            from_node_label=hop.start_node_label or hop.start_node_id,
                            relationship_type=hop.relationship_type,
                            to_node_id=hop.end_node_id,
                            to_node_type=hop.end_node_type or "Entity",
                            to_node_label=hop.end_node_label or hop.end_node_id,
                            confidence_score=hop.confidence_score,
                        )
                    )
                paths.append(
                    MultiHopPathInfo(
                        path_id=f"path_{target_case.id.hex[:6]}_{idx+1}",
                        start_case_alias=target_case.fir_number,
                        end_case_alias=p_item.end_node_id,
                        total_hops=len(path_hops),
                        path_summary=f"Multi-hop structural path from {target_case.fir_number} via {len(path_hops)} hops.",
                        hops=path_hops,
                    )
                )
        except Exception as err:
            logger.warning(f"Failed to extract multi-hop paths: {err}")
        return paths

    def _build_empty_response(
        self, request: IntelligenceAnalysisRequest, start_time: float
    ) -> IntelligenceAnalysisResponse:
        """Returns safe empty response when zero matching cases are found."""
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        from app.services.llm_reasoning_engine import PoliceFacingIntelligenceReport, LLMTraceableStatement
        
        report = PoliceFacingIntelligenceReport(
            report_id="report_empty",
            reasoning_id="reasoning_empty",
            status=ReasoningStatus.SUCCESS,
            summary="Zero matching cases were found for the supplied investigation parameters.",
            key_observations=[],
            cross_case_connections=[],
            recurring_patterns=[],
            network_observations=[],
            recommended_followups=[
                LLMTraceableStatement(statement="Verify case numbers or expand police station search parameters.")
            ],
            limitations=["No analytical graph data available for target search parameters."],
        )
        metadata = IntelligenceAnalyticalMetadata(
            cases_evaluated_count=0,
            stations_involved_count=0,
            patterns_detected_count=0,
            communities_detected_count=0,
            multi_hop_paths_count=0,
            traversal_depth_used=request.max_traversal_depth,
            execution_time_ms=round(elapsed_ms, 2),
            scope_applied=request.analytical_scope or "FULL",
            authorization_context_applied=request.workspace_context is not None,
        )
        return IntelligenceAnalysisResponse(
            report=report,
            analytical_metadata=metadata,
            multi_hop_paths=[],
        )


intelligence_orchestration_service = IntelligenceOrchestrationService()
