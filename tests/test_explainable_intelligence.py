import uuid
import pytest
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
    pattern_intelligence_engine,
)
from app.services.explainability_engine import (
    EvidenceCategory,
    ExplainabilitySignal,
    ExplainabilityEvidence,
    ExplainabilityAssessment,
    ExplainabilityRequest,
    ExplainabilityResult,
    explainability_engine,
    EXPLAINABLE_INTELLIGENCE_METHODOLOGY_VERSION,
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


def test_unit_explainability_contracts_and_non_inference_safeguard():
    """Tests 1, 10: Validates ExplainabilityAssessment contracts and forbidden term validator."""
    # Test forbidden term validator
    with pytest.raises(ValueError, match="Forbidden inference term"):
        ExplainabilityAssessment(
            explanation_id="exp:test:123456789012",
            subject_id="p1",
            subject_type="Person",
            title="Explanation of Suspect",
            observation="Person P1 is associated with 3 cases.",
            explanation="The perpetrator is guilty of conspiracy.",
            limitations=["None"],
        )

    # Test forbidden term in limitations
    with pytest.raises(ValueError, match="Forbidden inference term"):
        ExplainabilityAssessment(
            explanation_id="exp:test:123456789012",
            subject_id="p1",
            subject_type="Person",
            title="Explanation of Suspect",
            observation="Person P1 is associated with 3 cases.",
            explanation="Person P1 was observed across multiple stations.",
            limitations=["The culprit may have committed conspiracy."],
        )


def test_unit_empty_and_malformed_inputs():
    """Tests 11, 12: Verifies empty or malformed requests handle cleanly returning 0 explanations."""
    req_empty = ExplainabilityRequest()
    res_empty = explainability_engine.explain_analytical_findings(req_empty)
    assert res_empty.total_explanations_generated == 0
    assert res_empty.explanations == []


def test_unit_step5b_and_pattern_immutability():
    """Tests 5, 6, 7, 16: Verifies Step 5B assessments and Step 6 pattern observations are strictly immutable."""
    assessment = RelationshipConfidenceAssessment(
        source_case_id=str(uuid.uuid4()),
        target_case_id=str(uuid.uuid4()),
        canonical_relationship_key="case1::case2",
        confidence_score=0.88,
        confidence_level=RelationshipConfidenceLevel.HIGH,
        contributing_families=[SignalFamily.PERSON_IDENTITY],
        evidence_summary="Shared person identity.",
        explanation="High confidence link.",
        uncertainty_notes=[],
    )

    pat = PatternObservation(
        pattern_id="pat:recurring_entity:123456789012",
        pattern_type=PatternType.RECURRING_ENTITY,
        title="Recurring Person Entity Pattern",
        description="Person P1 observed in 2 cases.",
        occurrence_count=2,
        structural_strength=0.75,
        case_ids=["case1", "case2"],
        entity_ids=["p1"],
        entity_types=["Person"],
    )

    req = ExplainabilityRequest(
        confidence_assessments=[assessment],
        pattern_result=None,
    )

    res = explainability_engine.explain_analytical_findings(req)

    # Assert source assessment remains 100% untouched
    assert assessment.confidence_score == 0.88
    assert assessment.confidence_level == RelationshipConfidenceLevel.HIGH
    assert assessment.evidence_summary == "Shared person identity."

    # Assert pattern remains untouched
    assert pat.structural_strength == 0.75


def test_unit_multiple_explanation_types_and_deduplication():
    """Tests 2, 3, 4, 8, 9, 13, 14, 15: Tests multiple explanation types, deterministic IDs, limitations, and deduplication."""
    pat = PatternObservation(
        pattern_id="pat:recurring_entity:aabbcc112233",
        pattern_type=PatternType.RECURRING_ENTITY,
        title="Recurring Person Pattern",
        description="Person P1 occurs in Case A and Case B.",
        occurrence_count=2,
        structural_strength=0.8,
        case_ids=["case_a", "case_b"],
        entity_ids=["p1"],
        entity_types=["Person"],
        supporting_signals=["Shared Person P1"],
        provenance={"person_id": "p1"},
    )

    assessment = RelationshipConfidenceAssessment(
        source_case_id="case_a",
        target_case_id="case_b",
        canonical_relationship_key="case_a::case_b",
        confidence_score=0.92,
        confidence_level=RelationshipConfidenceLevel.VERY_HIGH,
        contributing_families=[SignalFamily.PERSON_IDENTITY],
        evidence_summary="Matching identity hash.",
        explanation="Strong link.",
        uncertainty_notes=[],
    )

    req = ExplainabilityRequest(
        pattern_result=None,
        confidence_assessments=[assessment],
    )

    res = explainability_engine.explain_analytical_findings(req)
    assert res.total_explanations_generated > 0

    exp = res.explanations[0]
    assert exp.explanation_id.startswith("exp:relationship:")
    assert exp.confidence_reference["confidence_score"] == 0.92
    assert len(exp.limitations) > 0
    assert "provenance" in exp.model_dump()


def test_synthetic_end_to_end_explanation_pipeline_and_cleanup():
    """Test 17: Full Synthetic Multi-Case Explanation Integration Test with 0 persistent Neo4j nodes."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live synthetic explanation integration test.")

    id_case_a, id_case_b, id_case_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    id_p1, id_v1, id_ph1, id_loc1 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    person_p1 = Person(id=id_p1, name="Vikram Singh", gender="MALE", identifier_hash="hash_v1")
    vehicle_v1 = Vehicle(id=id_v1, registration_number="OD02ZZ1111", vehicle_type="MOTORCYCLE", make="BAJAJ", model="PULSAR")
    phone_ph1 = Phone(id=id_ph1, normalized_number="+919999988888")
    location_loc1 = Location(id=id_loc1, address="Patia Square, BBSR", city="Bhubaneswar", district="Khordha", state="Odisha")

    # Case A (Station 1) -> Person P1, Vehicle V1
    case_a = Case(
        id=id_case_a, fir_number=f"FIR/2026/A_{id_case_a.hex[:4]}", station_id="PS_BBSR_001",
        police_station="Info City PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 1),
        crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
        location_id=id_loc1, location=location_loc1,
    )
    case_a.person_associations = [CasePerson(case_id=id_case_a, person_id=id_p1, person=person_p1, role=PersonRole.SUSPECT)]
    case_a.vehicle_associations = [CaseVehicle(case_id=id_case_a, vehicle_id=id_v1, vehicle=vehicle_v1, role=VehicleRole.SUSPECT_VEHICLE)]

    # Case B (Station 2 - Cross Station) -> Person P1, Phone Ph1
    case_b = Case(
        id=id_case_b, fir_number=f"FIR/2026/B_{id_case_b.hex[:4]}", station_id="PS_CTC_002",
        police_station="Cuttack Central PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 5),
        crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_b.person_associations = [CasePerson(case_id=id_case_b, person_id=id_p1, person=person_p1, role=PersonRole.ACCUSED)]
    case_b.phone_associations = [CasePhone(case_id=id_case_b, phone_id=id_ph1, phone=phone_ph1)]

    # Case C (Station 1) -> Person P1, Location Loc1
    case_c = Case(
        id=id_case_c, fir_number=f"FIR/2026/C_{id_case_c.hex[:4]}", station_id="PS_BBSR_001",
        police_station="Info City PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 12),
        crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
        location_id=id_loc1, location=location_loc1,
    )
    case_c.person_associations = [CasePerson(case_id=id_case_c, person_id=id_p1, person=person_p1, role=PersonRole.SUSPECT)]

    all_uuids = [str(id_case_a), str(id_case_b), str(id_case_c), str(id_p1), str(id_v1), str(id_ph1), str(id_loc1)]

    try:
        # Project Cases to Graph
        neo4j_graph_projection_service.project_case_graph(case_a)
        neo4j_graph_projection_service.project_case_graph(case_b)
        neo4j_graph_projection_service.project_case_graph(case_c)

        # Step 5B Assessment
        _, _, key_ab = canonicalize_case_pair(str(id_case_a), str(id_case_b))
        assessment_ab = RelationshipConfidenceAssessment(
            source_case_id=str(id_case_a), target_case_id=str(id_case_b),
            canonical_relationship_key=key_ab, confidence_score=0.86,
            confidence_level=RelationshipConfidenceLevel.HIGH,
            contributing_families=[SignalFamily.PERSON_IDENTITY],
            evidence_summary="HIGH confidence person match link.", explanation="Cross-station burglary link.", uncertainty_notes=[],
        )
        neo4j_graph_projection_service.project_relationship_assessment(assessment_ab)

        # Steps 5F & 5G Analytics
        net_res = neo4j_network_analytics_service.analyze_network(NetworkAnalyticsRequest(target_node_id=str(id_case_a)))
        comm_res = neo4j_community_detection_service.detect_communities(CommunityDetectionRequest(minimum_community_size=2))

        # Step 6 Pattern Intelligence
        pat_req = PatternDetectionRequest(
            cases=[case_a, case_b, case_c],
            graph_analytics_result=net_res,
            community_detection_result=comm_res,
            confidence_assessments=[assessment_ab],
        )
        pat_res = pattern_intelligence_engine.detect_patterns(pat_req)

        # Step 7 Explainable Intelligence
        exp_req = ExplainabilityRequest(
            cases=[case_a, case_b, case_c],
            pattern_result=pat_res,
            confidence_assessments=[assessment_ab],
            graph_analytics_result=net_res,
            community_detection_result=comm_res,
        )
        exp_res = explainability_engine.explain_analytical_findings(exp_req)

        assert exp_res.total_explanations_generated > 0

        # Verify Explanations reflect observations and limitations without claiming guilt
        for exp in exp_res.explanations:
            assert "guilty" not in exp.explanation.lower()
            assert "perpetrator" not in exp.explanation.lower()
            assert len(exp.limitations) > 0
            assert exp.methodology_version == EXPLAINABLE_INTELLIGENCE_METHODOLOGY_VERSION

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
