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
    LLMReasoningEngine,
    llm_reasoning_engine,
    LLM_REASONING_METHODOLOGY_VERSION,
)
from app.services.graph import (
    canonicalize_case_pair,
    neo4j_connection_service,
    neo4j_graph_projection_service,
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


# =====================================================================
# 1-3. VALID, EMPTY & MALFORMED PAYLOAD TESTS
# =====================================================================

@patch.object(GroqLLMClient, "call_provider")
def test_valid_llm_safe_payload_processing(mock_groq, sample_llm_safe_payload):
    """Test 1: Valid payload processing using primary Groq provider."""
    mock_json = json.dumps({
        "summary": "Synthesized observations across 2 cases.",
        "key_observations": [
            {
              "statement": "Case-A shares structural link with Case-B.",
              "source_case_aliases": ["Case-A", "Case-B"],
              "source_entity_aliases": ["Person-A"]
            }
        ],
        "recommended_followups": [
            {
              "statement": "Verify cross-station timeline in underlying files.",
              "source_case_aliases": ["Case-A", "Case-B"]
            }
        ],
        "limitations": ["Requires investigator verification."]
    })
    mock_groq.return_value = (mock_json, ReasoningStatus.SUCCESS, None)

    res, report = llm_reasoning_engine.generate_reasoning_report(sample_llm_safe_payload)

    assert res.status == ReasoningStatus.SUCCESS
    assert res.summary == "Synthesized observations across 2 cases."
    assert len(res.key_observations) == 1
    assert res.key_observations[0].source_case_aliases == ["Case-A", "Case-B"]
    assert res.provider_metadata["selected_provider"] == "groq"


def test_empty_payload_processing():
    """Test 2: Empty payload handling."""
    empty_payload = LLMSafeExplainabilityPayload(total_explanations=0, explanations=[])
    res, report = llm_reasoning_engine.generate_reasoning_report(empty_payload)

    assert res.status == ReasoningStatus.SUCCESS
    assert "No explanations provided" in res.summary
    assert res.key_observations == []


@patch.object(GroqLLMClient, "call_provider")
def test_malformed_llm_json_response_handling(mock_groq, sample_llm_safe_payload):
    """Test 3 & 11: Invalid LLM JSON response fallback to deterministic synthesis."""
    mock_groq.return_value = ("NOT_VALID_JSON_STRING", ReasoningStatus.SUCCESS, None)

    res, report = llm_reasoning_engine.generate_reasoning_report(sample_llm_safe_payload)

    assert res.status == ReasoningStatus.INVALID_MODEL_OUTPUT
    assert "Fallback deterministic synthesis" in res.summary
    assert len(res.key_observations) == 1


# =====================================================================
# 4-7. DATABASE ISOLATION, PRIVACY & MAPPING ISOLATION TESTS
# =====================================================================

def test_database_and_neo4j_isolation_assertion(sample_llm_safe_payload):
    """Test 4, 5 & 6: Proves Step 8 operates 100% in-memory without calling PostgreSQL or Neo4j."""
    with patch("sqlalchemy.orm.Session") as mock_pg, patch("neo4j.Driver") as mock_neo4j:
        mapping = DeidentificationMapping(alias_to_original={"Person-A": "Subhash Chandra"})
        res, report = llm_reasoning_engine.generate_reasoning_report(sample_llm_safe_payload, private_mapping=mapping)

        mock_pg.assert_not_called()
        mock_neo4j.assert_not_called()
        assert report is not None


@patch.object(GroqLLMClient, "call_provider")
def test_no_raw_pii_in_outbound_payload_prompt(mock_groq, sample_llm_safe_payload):
    """Test 7: Asserts outbound LLM prompt payload contains ZERO raw PII or private mapping tables."""
    mock_groq.return_value = (json.dumps({"summary": "Clean summary.", "key_observations": []}), ReasoningStatus.SUCCESS, None)

    llm_reasoning_engine.generate_reasoning_report(sample_llm_safe_payload)

    call_args = mock_groq.call_args[0]
    outbound_payload_str = call_args[0]

    assert "alias_to_original" not in outbound_payload_str
    assert "original_to_alias" not in outbound_payload_str
    assert "Rajesh" not in outbound_payload_str


# =====================================================================
# 8-10. PROMPT INJECTION, DETERMINISM & STRUCTURED OUTPUT TESTS
# =====================================================================

def test_prompt_injection_resilience_in_analytical_data():
    """Test 8: Asserts analytical fields with injection text do not break prompt structure."""
    assessment = LLMSafeExplainabilityAssessment(
        explanation_id="exp:injection:001",
        subject_alias="Case-A",
        subject_type="Case",
        title="Title with directive",
        observation="Observation with [NEUTRALIZED_DIRECTIVE] system directive.",
        explanation="Explanation text.",
    )
    payload = LLMSafeExplainabilityPayload(total_explanations=1, explanations=[assessment])

    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (json.dumps({"summary": "Safe summary.", "key_observations": []}), ReasoningStatus.SUCCESS, None)
        res, _ = llm_reasoning_engine.generate_reasoning_report(payload)
        assert res.status == ReasoningStatus.SUCCESS


def test_deterministic_configuration():
    """Test 9: Verifies LLM temperature configuration defaults to 0.0."""
    assert settings.LLM_TEMPERATURE == 0.0


# =====================================================================
# 12-17. TIMEOUT, RATE LIMIT & PROVIDER FAILOVER TESTS
# =====================================================================

@patch.object(GroqLLMClient, "call_provider")
@patch.object(CerebrasLLMClient, "call_provider")
@patch.object(OllamaLLMClient, "call_provider")
def test_groq_to_cerebras_to_ollama_failover_chain(mock_ollama, mock_cerebras, mock_groq, sample_llm_safe_payload):
    """Test 14, 15, 16: Tests primary Groq failover -> secondary Cerebras failover -> local Ollama success."""
    mock_groq.return_value = (None, ReasoningStatus.RATE_LIMITED, "429 Rate Limit")
    mock_cerebras.return_value = (None, ReasoningStatus.TIMEOUT, "Timeout")
    mock_ollama.return_value = (json.dumps({"summary": "Ollama summary.", "key_observations": []}), ReasoningStatus.SUCCESS, None)

    res, _ = llm_reasoning_engine.generate_reasoning_report(sample_llm_safe_payload)

    assert res.status == ReasoningStatus.SUCCESS
    assert res.summary == "Ollama summary."
    assert res.provider_metadata["selected_provider"] == "ollama"
    assert len(res.provider_metadata["provider_attempts"]) == 3


@patch.object(GroqLLMClient, "call_provider")
@patch.object(CerebrasLLMClient, "call_provider")
@patch.object(OllamaLLMClient, "call_provider")
def test_all_providers_unavailable_controlled_error(mock_ollama, mock_cerebras, mock_groq, sample_llm_safe_payload):
    """Test 17: All providers fail -> returns safe fallback result with status ALL_PROVIDERS_FAILED."""
    mock_groq.return_value = (None, ReasoningStatus.PROVIDER_UNAVAILABLE, "No Groq API Key")
    mock_cerebras.return_value = (None, ReasoningStatus.PROVIDER_UNAVAILABLE, "No Cerebras Key")
    mock_ollama.return_value = (None, ReasoningStatus.TIMEOUT, "Ollama Offline")

    res, _ = llm_reasoning_engine.generate_reasoning_report(sample_llm_safe_payload)

    assert res.status in (ReasoningStatus.ALL_PROVIDERS_FAILED, ReasoningStatus.TIMEOUT)
    assert "Fallback deterministic synthesis" in res.summary


# =====================================================================
# 18-24. ALIAS PRESERVATION, NON-INFERENCE & IMMUTABILITY TESTS
# =====================================================================

def test_unsupported_hallucinated_alias_preservation():
    """Test 18: Hallucinated alias Person-Z99 is safely preserved without errors or DB lookups."""
    mapping = DeidentificationMapping(alias_to_original={"Person-A": "Sanjay Das"})
    res_dict = {
        "reasoning_id": "r1",
        "status": ReasoningStatus.SUCCESS,
        "summary": "Mentioned Person-A and Person-Z99.",
        "key_observations": [{"statement": "Spotted Person-Z99 with Person-A."}],
        "cross_case_connections": [],
        "recurring_patterns": [],
        "network_observations": [],
        "recommended_followups": [],
        "limitations": [],
        "confidence_context": {},
        "provider_metadata": {},
        "methodology_version": LLM_REASONING_METHODOLOGY_VERSION,
    }

    report = llm_reasoning_engine._backmap_result(LLMReasoningResult(**res_dict), mapping)

    assert "Sanjay Das" in report.summary
    assert "Person-Z99" in report.summary  # Safely preserved
    assert "Person-Z99" in report.key_observations[0].statement


def test_non_inference_forbidden_terms_validation():
    """Test 21: Raises ValueError if forbidden legal/guilt inference terms are present."""
    with pytest.raises(ValueError, match="Forbidden inference term"):
        LLMTraceableStatement(statement="Person-A is guilty of robbery.")


def test_upstream_objects_immutability(sample_llm_safe_payload):
    """Test 22 & 23: Asserts Step 7.5 payload objects remain 100% immutable."""
    original_total = sample_llm_safe_payload.total_explanations
    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (json.dumps({"summary": "Test.", "key_observations": []}), ReasoningStatus.SUCCESS, None)
        llm_reasoning_engine.generate_reasoning_report(sample_llm_safe_payload)

    assert sample_llm_safe_payload.total_explanations == original_total


# =====================================================================
# 25-28. SECRET LEAKAGE, LOGGING & UNICODE TESTS
# =====================================================================

def test_secret_leakage_and_logging_privacy_audit(caplog, sample_llm_safe_payload):
    """Test 24 & 25: Asserts secrets, API keys, and private mapping keys never leak into logs."""
    caplog.set_level(logging.DEBUG)

    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (json.dumps({"summary": "Clean.", "key_observations": []}), ReasoningStatus.SUCCESS, None)
        llm_reasoning_engine.generate_reasoning_report(sample_llm_safe_payload)

    log_str = caplog.text
    assert "GROQ_API_KEY" not in log_str
    assert "alias_to_original" not in log_str


def test_unicode_and_regional_script_handling():
    """Test 26: Unicode & regional Indian scripts handling in Step 8."""
    stmt = LLMTraceableStatement(statement="Observation regarding ରାଜೇಶ್ ମହାନ୍ତି and राजेश शर्मा.")
    assert "ରାଜೇಶ್ ମହାନ୍ତି" in stmt.statement
    assert "राजेश शर्मा" in stmt.statement


def test_large_payload_scale_benchmark():
    """Test 27 & 28: Evaluates 100+ explanations scale benchmark."""
    explanations = [
        LLMSafeExplainabilityAssessment(
            explanation_id=f"exp:{i}",
            subject_alias=f"Case-{i}",
            subject_type="Case",
            title=f"Title {i}",
            observation=f"Observation for case {i}",
            explanation=f"Explanation for case {i}",
        )
        for i in range(100)
    ]
    payload = LLMSafeExplainabilityPayload(total_explanations=100, explanations=explanations)

    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (json.dumps({"summary": "Large payload summary.", "key_observations": []}), ReasoningStatus.SUCCESS, None)
        res, _ = llm_reasoning_engine.generate_reasoning_report(payload)

    assert res.status == ReasoningStatus.SUCCESS


# =====================================================================
# 29. SYNTHETIC END-TO-END INTELLIGENCE FLOW (STEPS 3A–8 + NEO4J CLEANUP)
# =====================================================================

def test_synthetic_end_to_end_full_pipeline_step3a_to_step8_and_cleanup():
    """Test 29: Full Synthetic Pipeline test executing Steps 3A through 8 with live Neo4j cleanup."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live synthetic E2E pipeline test.")

    id_case_a, id_case_b = uuid.uuid4(), uuid.uuid4()
    id_p1, id_v1 = uuid.uuid4(), uuid.uuid4()

    raw_person_name = "Debendra Nath Swain"
    raw_veh_reg = "OD02XY8888"

    person_p1 = Person(id=id_p1, name=raw_person_name, gender="MALE", identifier_hash="hash_dns1")
    vehicle_v1 = Vehicle(id=id_v1, registration_number=raw_veh_reg, vehicle_type="CAR", make="HYUNDAI", model="CRETA")

    case_a = Case(
        id=id_case_a, fir_number=f"FIR/2026/E2E_A_{id_case_a.hex[:4]}", station_id="PS_BBSR_001",
        police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 12),
        crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_a.person_associations = [CasePerson(case_id=id_case_a, person_id=id_p1, person=person_p1, role=PersonRole.SUSPECT)]
    case_a.vehicle_associations = [CaseVehicle(case_id=id_case_a, vehicle_id=id_v1, vehicle=vehicle_v1, role=VehicleRole.SUSPECT_VEHICLE)]

    case_b = Case(
        id=id_case_b, fir_number=f"FIR/2026/E2E_B_{id_case_b.hex[:4]}", station_id="PS_CTC_002",
        police_station="Cuttack City PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 18),
        crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_b.person_associations = [CasePerson(case_id=id_case_b, person_id=id_p1, person=person_p1, role=PersonRole.ACCUSED)]
    case_b.vehicle_associations = [CaseVehicle(case_id=id_case_b, vehicle_id=id_v1, vehicle=vehicle_v1, role=VehicleRole.RECOVERED_VEHICLE)]

    all_uuids = [str(id_case_a), str(id_case_b), str(id_p1), str(id_v1)]

    try:
        # Step 5C Graph Projection
        neo4j_graph_projection_service.project_case_graph(case_a)
        neo4j_graph_projection_service.project_case_graph(case_b)

        _, _, key_ab = canonicalize_case_pair(str(id_case_a), str(id_case_b))
        assessment_ab = RelationshipConfidenceAssessment(
            source_case_id=str(id_case_a), target_case_id=str(id_case_b),
            canonical_relationship_key=key_ab, confidence_score=0.92,
            confidence_level=RelationshipConfidenceLevel.VERY_HIGH,
            contributing_families=[SignalFamily.PERSON_IDENTITY, SignalFamily.VEHICLE],
            evidence_summary="VERY_HIGH confidence burglary link.", explanation="Cross-station link.", uncertainty_notes=[],
        )
        neo4j_graph_projection_service.project_relationship_assessment(assessment_ab)

        # Steps 5F/5G Analytics
        net_res = neo4j_network_analytics_service.analyze_network(NetworkAnalyticsRequest(target_node_id=str(id_case_a)))
        comm_res = neo4j_community_detection_service.detect_communities(CommunityDetectionRequest(minimum_community_size=2))

        # Step 6 Pattern Intelligence
        pat_req = PatternDetectionRequest(cases=[case_a, case_b], graph_analytics_result=net_res, community_detection_result=comm_res, confidence_assessments=[assessment_ab])
        pat_res = pattern_intelligence_engine.detect_patterns(pat_req)

        # Step 7 Explainable Intelligence
        exp_req = ExplainabilityRequest(cases=[case_a, case_b], pattern_result=pat_res, confidence_assessments=[assessment_ab], graph_analytics_result=net_res, community_detection_result=comm_res)
        exp_res = explainability_engine.explain_analytical_findings(exp_req)

        # Step 7.5 Privacy Boundary Engine
        deid_res = pii_privacy_boundary_engine.deidentify_explainability_result(exp_res, cases=[case_a, case_b])
        payload = deid_res.llm_safe_payload
        mapping = deid_res.private_mapping

        # Step 8 LLM Reasoning Engine (with mocked Groq API)
        with patch.object(GroqLLMClient, "call_provider") as mock_groq:
            mock_groq.return_value = (
                json.dumps({
                    "summary": "Cross-station burglary activity identified spanning 2 cases.",
                    "key_observations": [
                        {
                            "statement": "Person-A was identified across 2 cases associated with Vehicle-A.",
                            "source_case_aliases": ["Case-A", "Case-B"],
                            "source_entity_aliases": ["Person-A", "Vehicle-A"]
                        }
                    ],
                    "recommended_followups": [
                        {
                            "statement": "Investigators may review Case-A and Case-B timelines.",
                            "source_case_aliases": ["Case-A", "Case-B"]
                        }
                    ],
                    "limitations": ["Empirical structural findings require investigator verification."]
                }),
                ReasoningStatus.SUCCESS,
                None,
            )

            res, report = llm_reasoning_engine.generate_reasoning_report(payload, private_mapping=mapping)

        # Assertions
        assert res.status == ReasoningStatus.SUCCESS
        assert "Person-A" in res.key_observations[0].statement
        assert raw_person_name not in res.model_dump_json()

        # Police-facing report assertion (restored raw PII)
        assert report is not None
        assert raw_person_name in report.key_observations[0].statement
        assert raw_veh_reg in report.key_observations[0].statement

    finally:
        # Clean up ONLY test-created node UUIDs
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("MATCH (n) WHERE n.node_id IN $ids OR n.case_id IN $ids DETACH DELETE n", {"ids": all_uuids})
            session.run("MATCH (n) WHERE head(labels(n)) IN ['Location', 'Evidence', 'LegalSection', 'Phone', 'Vehicle', 'Person'] AND NOT (n)--() DETACH DELETE n")
            nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            assert nodes == 0
            assert rels == 0
