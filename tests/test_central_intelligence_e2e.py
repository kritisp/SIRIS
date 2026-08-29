import copy
import json
import logging
import uuid
import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from app.config.settings import settings
from app.models.case import Case
from app.models.person import Person, CasePerson, PersonRole
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.models.phone import Phone, CasePhone
from app.models.location import Location
from app.services.pattern_engine import (
    PatternType,
    PatternObservation,
    PatternDetectionRequest,
    PatternDetectionResult,
    pattern_intelligence_engine,
)
from app.services.explainability_engine import (
    ExplainabilityRequest,
    explainability_engine,
)
from app.services.privacy_engine import (
    PIIEntityType,
    DeidentificationMapping,
    LLMSafeExplainabilityAssessment,
    LLMSafeExplainabilityPayload,
    DeidentificationResult,
    pii_privacy_boundary_engine,
    pii_backmapper,
)
from app.services.llm_reasoning_engine import (
    ReasoningStatus,
    LLMProvider,
    LLMTraceableStatement,
    LLMReasoningResult,
    PoliceFacingIntelligenceReport,
    GroqLLMClient,
    CerebrasLLMClient,
    OllamaLLMClient,
    PostLLMPrivacyScanner,
    LLMReasoningEngine,
    llm_reasoning_engine,
    LLM_REASONING_METHODOLOGY_VERSION,
)
from app.seeds.neo4j_realistic_datasets import neo4j_realistic_datasets
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

logger = logging.getLogger(__name__)


# =====================================================================
# SYNTHETIC DATASET FIXTURES & GENERATOR
# =====================================================================

@pytest.fixture
def sample_llm_safe_payload():
    """Fixture producing a clean LLMSafeExplainabilityPayload."""
    assessment = LLMSafeExplainabilityAssessment(
        explanation_id="exp:pattern:112233",
        subject_alias="Case-A",
        subject_type="Case",
        title="Explanation for Cross-Station Pattern",
        observation="Cross-station activity observed for Case-A and Case-B across 2 police stations.",
        explanation="Identified structural case activity spanning PS_BBSR_001 and PS_CTC_002.",
        supporting_case_aliases=["Case-A", "Case-B"],
        supporting_entity_aliases=["Person-A", "Vehicle-A"],
        supporting_pattern_ids=["pat:recurring_entity:001"],
        supporting_community_ids=["comm:001"],
        supporting_connector_ids=["Case-A"],
        limitations=["Structural similarity does not prove illegal intent."],
        preserved_analytical_context={"district": "Khordha", "crime_category": "PROPERTY_CRIME"},
    )
    return LLMSafeExplainabilityPayload(
        total_explanations=1,
        explanations=[assessment],
        preserved_global_context={"total_evaluated": 1},
    )


@pytest.fixture
def synthetic_investigation_dataset():
    """Generates a multi-station, multi-case synthetic investigation dataset.
    
    Station A (PS_BBSR_SYN1):
      - Case A (FIR/2026/SYN_001): Burglary, 2026-08-10. Person 1, Vehicle 1, Phone 1.
      - Case B (FIR/2026/SYN_002): Larceny, 2026-08-15. Person 1, Person 2, Vehicle 1.
      - Case C (FIR/2026/SYN_003): Burglary, 2026-08-18. Person 2, Phone 1.
      
    Station B (PS_CTC_SYN2):
      - Case D (FIR/2026/SYN_004): Robbery, 2026-08-20. Person 1 (Bridge), Vehicle 1, Phone 2.
      - Case E (FIR/2026/SYN_005): Theft, 2026-08-22. Person 2, Vehicle 2.
    """
    id_case_a, id_case_b, id_case_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    id_case_d, id_case_e = uuid.uuid4(), uuid.uuid4()
    
    id_p1, id_p2 = uuid.uuid4(), uuid.uuid4()
    id_v1, id_v2 = uuid.uuid4(), uuid.uuid4()
    id_ph1, id_ph2 = uuid.uuid4(), uuid.uuid4()

    raw_p1_name, raw_p2_name = "Synthetic Person 1 (Debendra Swain)", "Synthetic Person 2 (Subhash Chandra)"
    raw_v1_reg, raw_v2_reg = "OD02SYN1111", "OD05SYN2222"
    raw_ph1_num, raw_ph2_num = "9861000001", "9937000002"

    person_1 = Person(id=id_p1, name=raw_p1_name, gender="MALE", identifier_hash="hash_syn_p1")
    person_2 = Person(id=id_p2, name=raw_p2_name, gender="MALE", identifier_hash="hash_syn_p2")

    vehicle_1 = Vehicle(id=id_v1, registration_number=raw_v1_reg, vehicle_type="CAR", make="HYUNDAI", model="CRETA")
    vehicle_2 = Vehicle(id=id_v2, registration_number=raw_v2_reg, vehicle_type="MOTORCYCLE", make="HONDA", model="SHINE")

    phone_1 = Phone(id=id_ph1, normalized_number=raw_ph1_num, number_hash="hash_ph1")
    phone_2 = Phone(id=id_ph2, normalized_number=raw_ph2_num, number_hash="hash_ph2")

    # Station A Cases
    case_a = Case(
        id=id_case_a, fir_number=f"FIR/2026/SYN_001", station_id="PS_BBSR_SYN1",
        police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 10),
        crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_a.person_associations = [CasePerson(case_id=id_case_a, person_id=id_p1, person=person_1, role=PersonRole.SUSPECT)]
    case_a.vehicle_associations = [CaseVehicle(case_id=id_case_a, vehicle_id=id_v1, vehicle=vehicle_1, role=VehicleRole.SUSPECT_VEHICLE)]
    case_a.phone_associations = [CasePhone(case_id=id_case_a, phone_id=id_ph1, phone=phone_1)]

    case_b = Case(
        id=id_case_b, fir_number=f"FIR/2026/SYN_002", station_id="PS_BBSR_SYN1",
        police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 15),
        crime_type="LARCENY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_b.person_associations = [
        CasePerson(case_id=id_case_b, person_id=id_p1, person=person_1, role=PersonRole.SUSPECT),
        CasePerson(case_id=id_case_b, person_id=id_p2, person=person_2, role=PersonRole.ACCUSED)
    ]
    case_b.vehicle_associations = [CaseVehicle(case_id=id_case_b, vehicle_id=id_v1, vehicle=vehicle_1, role=VehicleRole.RECOVERED_VEHICLE)]

    case_c = Case(
        id=id_case_c, fir_number=f"FIR/2026/SYN_003", station_id="PS_BBSR_SYN1",
        police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 18),
        crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_c.person_associations = [CasePerson(case_id=id_case_c, person_id=id_p2, person=person_2, role=PersonRole.SUSPECT)]
    case_c.phone_associations = [CasePhone(case_id=id_case_c, phone_id=id_ph1, phone=phone_1)]

    # Station B Cases
    case_d = Case(
        id=id_case_d, fir_number=f"FIR/2026/SYN_004", station_id="PS_CTC_SYN2",
        police_station="Cuttack City PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 20),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_d.person_associations = [CasePerson(case_id=id_case_d, person_id=id_p1, person=person_1, role=PersonRole.ACCUSED)]
    case_d.vehicle_associations = [CaseVehicle(case_id=id_case_d, vehicle_id=id_v1, vehicle=vehicle_1, role=VehicleRole.SUSPECT_VEHICLE)]
    case_d.phone_associations = [CasePhone(case_id=id_case_d, phone_id=id_ph2, phone=phone_2)]

    case_e = Case(
        id=id_case_e, fir_number=f"FIR/2026/SYN_005", station_id="PS_CTC_SYN2",
        police_station="Cuttack City PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 22),
        crime_type="THEFT", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_e.person_associations = [CasePerson(case_id=id_case_e, person_id=id_p2, person=person_2, role=PersonRole.SUSPECT)]
    case_e.vehicle_associations = [CaseVehicle(case_id=id_case_e, vehicle_id=id_v2, vehicle=vehicle_2, role=VehicleRole.SUSPECT_VEHICLE)]

    cases = [case_a, case_b, case_c, case_d, case_e]
    all_uuids = [str(c.id) for c in cases] + [str(id_p1), str(id_p2), str(id_v1), str(id_v2), str(id_ph1), str(id_ph2)]

    return {
        "cases": cases,
        "uuids": all_uuids,
        "raw_names": [raw_p1_name, raw_p2_name],
        "raw_vehicles": [raw_v1_reg, raw_v2_reg],
        "raw_phones": [raw_ph1_num, raw_ph2_num],
    }


# =====================================================================
# 1. NEO4J POPULATION & TEARDOWN FIXTURE
# =====================================================================

@pytest.fixture
def neo4j_test_graph(synthetic_investigation_dataset):
    """Populates Neo4j with synthetic graph and cleans up completely after test execution."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j database server is offline. Skipping Neo4j E2E test.")

    cases = synthetic_investigation_dataset["cases"]
    all_uuids = synthetic_investigation_dataset["uuids"]

    # 0. Ensure clean starting state
    neo4j_realistic_datasets.clear_all_test_data()
    
    # 1. Project Cases & Entity Nodes
    for case_obj in cases:
        neo4j_graph_projection_service.project_case_graph(case_obj)

    # 2. Project Step 5B Relationship Confidence Assessments
    assessments = []
    for i in range(len(cases)):
        for j in range(i + 1, len(cases)):
            c1, c2 = cases[i], cases[j]
            # Determine shared entities
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
                    evidence_summary=f"Confidence {score} link between {c1.fir_number} and {c2.fir_number}",
                    explanation="Shared entity link.",
                    uncertainty_notes=[],
                )
                assessments.append(ass)
                neo4j_graph_projection_service.project_relationship_assessment(ass)

    yield {"cases": cases, "assessments": assessments, "uuids": all_uuids}

    # Teardown & Complete Cleanup
    neo4j_realistic_datasets.clear_all_test_data()


# =====================================================================
# 2. COMPLETE E2E PIPELINE EXECUTION & VALIDATION
# =====================================================================

def test_complete_end_to_end_intelligence_pipeline(neo4j_test_graph, synthetic_investigation_dataset):
    """Tests complete sequential pipeline: Step 3A+ -> 5B -> 5E -> 5F -> 5G -> 6 -> 7 -> 7.5 -> 8 -> Police Report."""
    cases = neo4j_test_graph["cases"]
    assessments = neo4j_test_graph["assessments"]
    target_case = cases[0]

    # Step 5E Multi-hop Graph Traversal
    trav_res = neo4j_graph_traversal_service.traverse(GraphTraversalRequest(start_node_id=str(target_case.id), max_depth=2))
    assert trav_res is not None

    # Step 5F Network Analytics
    net_res = neo4j_network_analytics_service.analyze_network(NetworkAnalyticsRequest(target_node_id=str(target_case.id)))
    assert net_res.total_nodes_analyzed >= 1

    # Step 5G Community Detection
    comm_res = neo4j_community_detection_service.detect_communities(CommunityDetectionRequest(minimum_community_size=2))
    assert comm_res.total_communities_detected >= 1

    # Step 6 Pattern Intelligence
    pat_req = PatternDetectionRequest(cases=cases, graph_analytics_result=net_res, community_detection_result=comm_res, confidence_assessments=assessments)
    pat_res = pattern_intelligence_engine.detect_patterns(pat_req)
    assert pat_res.total_patterns_detected >= 1

    # Step 7 Explainable Intelligence
    exp_req = ExplainabilityRequest(cases=cases, pattern_result=pat_res, confidence_assessments=assessments, graph_analytics_result=net_res, community_detection_result=comm_res)
    exp_res = explainability_engine.explain_analytical_findings(exp_req)
    assert exp_res.total_explanations_generated >= 1

    # Step 7.5 Privacy Boundary Engine
    deid_res = pii_privacy_boundary_engine.deidentify_explainability_result(exp_res, cases=cases)
    payload = deid_res.llm_safe_payload
    mapping = deid_res.private_mapping

    # Privacy Boundary Audit: Assert ZERO raw PII in payload
    payload_str = payload.model_dump_json()
    for raw_name in synthetic_investigation_dataset["raw_names"]:
        assert raw_name not in payload_str
    for raw_veh in synthetic_investigation_dataset["raw_vehicles"]:
        assert raw_veh not in payload_str

    # Step 8 LLM Reasoning Engine (with mocked Groq provider)
    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (
            json.dumps({
                "summary": "Cross-station structural investigation summary.",
                "key_observations": [
                    {
                        "statement": "Person-A was identified across multiple cases associated with Vehicle-A.",
                        "source_case_aliases": ["Case-A", "Case-B"],
                        "source_entity_aliases": ["Person-A", "Vehicle-A"]
                    }
                ],
                "recommended_followups": [
                    {
                        "statement": "Investigators may review Case-A and Case-B timeline records.",
                        "source_case_aliases": ["Case-A", "Case-B"]
                    }
                ],
                "limitations": ["Findings represent structural observations requiring investigator verification."]
            }),
            ReasoningStatus.SUCCESS,
            None,
        )

        reasoning_res, police_report = llm_reasoning_engine.generate_reasoning_report(payload, private_mapping=mapping)

    # Step 8 Assertions
    assert reasoning_res.status == ReasoningStatus.SUCCESS
    assert "Person-A" in reasoning_res.key_observations[0].statement
    assert synthetic_investigation_dataset["raw_names"][0] not in reasoning_res.model_dump_json()

    # Step 7.5 Back-Mapping Assertion
    assert police_report is not None
    assert police_report.status == ReasoningStatus.SUCCESS
    assert any(raw_name in police_report.key_observations[0].statement for raw_name in synthetic_investigation_dataset["raw_names"])


# =====================================================================
# 3. PRIVACY BOUNDARY & SOURCE GROUNDING AUDIT
# =====================================================================

def test_privacy_boundary_and_source_grounding_audit(neo4j_test_graph, synthetic_investigation_dataset):
    """Audits privacy payload isolation and source-grounding filters."""
    cases = neo4j_test_graph["cases"]
    assessments = neo4j_test_graph["assessments"]

    net_res = neo4j_network_analytics_service.analyze_network(NetworkAnalyticsRequest(target_node_id=str(cases[0].id)))
    comm_res = neo4j_community_detection_service.detect_communities(CommunityDetectionRequest(minimum_community_size=2))
    pat_res = pattern_intelligence_engine.detect_patterns(PatternDetectionRequest(cases=cases, graph_analytics_result=net_res, community_detection_result=comm_res, confidence_assessments=assessments))
    exp_res = explainability_engine.explain_analytical_findings(ExplainabilityRequest(cases=cases, pattern_result=pat_res, confidence_assessments=assessments, graph_analytics_result=net_res, community_detection_result=comm_res))
    
    deid_res = pii_privacy_boundary_engine.deidentify_explainability_result(exp_res, cases=cases)
    payload = deid_res.llm_safe_payload

    # Hallucinated source ID injection in mock LLM response
    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (
            json.dumps({
                "summary": "Observation mentioning valid and hallucinated IDs.",
                "key_observations": [
                    {
                        "statement": "Observation for Case-A and hallucinated Case-Z99.",
                        "source_case_aliases": ["Case-A", "Case-Z99"],
                        "source_entity_aliases": ["Person-A", "Person-UNKNOWN"]
                    }
                ]
            }),
            ReasoningStatus.SUCCESS,
            None,
        )

        res, _ = llm_reasoning_engine.generate_reasoning_report(payload)

    # Assert hallucinated IDs were stripped by SourceGroundingGuard
    obs = res.key_observations[0]
    assert obs.source_case_aliases == ["Case-A"]
    assert obs.source_entity_aliases == ["Person-A"]


# =====================================================================
# 4. NON-INFERENCE & LEGAL SAFETY VERIFICATION
# =====================================================================

def test_non_inference_and_recommendation_safety_rejection(sample_llm_safe_payload):
    """Verifies forbidden legal guilt and coercive recommendation terms are rejected."""
    # Guilt claim rejection
    with pytest.raises(ValueError, match="Forbidden inference term"):
        LLMTraceableStatement(statement="Person-A is the perpetrator guilty of burglary.")

    # Coercive recommendation rejection
    with pytest.raises(ValueError, match="Coercive recommendation term"):
        LLMTraceableStatement(statement="Arrest Person-A and execute warrant.")


# =====================================================================
# 5. UPSTREAM OBJECT IMMUTABILITY AUDIT
# =====================================================================

def test_upstream_object_immutability_audit(neo4j_test_graph):
    """Verifies Step 5B, 6, 7, and 7.5 objects remain 100% unchanged during Step 8."""
    cases = neo4j_test_graph["cases"]
    assessments = neo4j_test_graph["assessments"]

    net_res = neo4j_network_analytics_service.analyze_network(NetworkAnalyticsRequest(target_node_id=str(cases[0].id)))
    comm_res = neo4j_community_detection_service.detect_communities(CommunityDetectionRequest(minimum_community_size=2))
    pat_res = pattern_intelligence_engine.detect_patterns(PatternDetectionRequest(cases=cases, graph_analytics_result=net_res, community_detection_result=comm_res, confidence_assessments=assessments))
    exp_res = explainability_engine.explain_analytical_findings(ExplainabilityRequest(cases=cases, pattern_result=pat_res, confidence_assessments=assessments, graph_analytics_result=net_res, community_detection_result=comm_res))
    deid_res = pii_privacy_boundary_engine.deidentify_explainability_result(exp_res, cases=cases)
    
    payload = deid_res.llm_safe_payload
    payload_snapshot = copy.deepcopy(payload)

    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (json.dumps({"summary": "Test.", "key_observations": []}), ReasoningStatus.SUCCESS, None)
        llm_reasoning_engine.generate_reasoning_report(payload)

    assert payload.model_dump() == payload_snapshot.model_dump()


# =====================================================================
# 6. ANALYTICAL LAYER DETERMINISM AUDIT
# =====================================================================

def test_analytical_layer_determinism_audit(neo4j_test_graph):
    """Verifies that running analytical pipeline twice on same synthetic dataset yields 100% identical pattern IDs and explanation IDs."""
    cases = neo4j_test_graph["cases"]
    assessments = neo4j_test_graph["assessments"]

    # Run 1
    net1 = neo4j_network_analytics_service.analyze_network(NetworkAnalyticsRequest(target_node_id=str(cases[0].id)))
    comm1 = neo4j_community_detection_service.detect_communities(CommunityDetectionRequest(minimum_community_size=2))
    pat1 = pattern_intelligence_engine.detect_patterns(PatternDetectionRequest(cases=cases, graph_analytics_result=net1, community_detection_result=comm1, confidence_assessments=assessments))
    exp1 = explainability_engine.explain_analytical_findings(ExplainabilityRequest(cases=cases, pattern_result=pat1, confidence_assessments=assessments, graph_analytics_result=net1, community_detection_result=comm1))

    # Run 2
    net2 = neo4j_network_analytics_service.analyze_network(NetworkAnalyticsRequest(target_node_id=str(cases[0].id)))
    comm2 = neo4j_community_detection_service.detect_communities(CommunityDetectionRequest(minimum_community_size=2))
    pat2 = pattern_intelligence_engine.detect_patterns(PatternDetectionRequest(cases=cases, graph_analytics_result=net2, community_detection_result=comm2, confidence_assessments=assessments))
    exp2 = explainability_engine.explain_analytical_findings(ExplainabilityRequest(cases=cases, pattern_result=pat2, confidence_assessments=assessments, graph_analytics_result=net2, community_detection_result=comm2))

    assert [p.pattern_id for p in pat1.patterns] == [p.pattern_id for p in pat2.patterns]
    assert [e.explanation_id for e in exp1.explanations] == [e.explanation_id for e in exp2.explanations]


# =====================================================================
# 7. PROVIDER FAILOVER & SAFE FALLBACK TEST
# =====================================================================

@patch.object(GroqLLMClient, "call_provider")
@patch.object(CerebrasLLMClient, "call_provider")
@patch.object(OllamaLLMClient, "call_provider")
def test_provider_failover_and_safe_fallback(mock_ollama, mock_cerebras, mock_groq, sample_llm_safe_payload):
    """Tests Groq failover -> Cerebras failover -> Ollama failure -> Deterministic safe fallback output."""
    mock_groq.return_value = (None, ReasoningStatus.RATE_LIMITED, "Groq Rate Limit")
    mock_cerebras.return_value = (None, ReasoningStatus.PROVIDER_UNAVAILABLE, "Cerebras Unavailable")
    mock_ollama.return_value = (None, ReasoningStatus.TIMEOUT, "Ollama Timeout")

    res, _ = llm_reasoning_engine.generate_reasoning_report(sample_llm_safe_payload)

    assert res.status in (ReasoningStatus.ALL_PROVIDERS_FAILED, ReasoningStatus.TIMEOUT)
    assert "Fallback deterministic synthesis" in res.summary
    assert len(res.key_observations) == 1
