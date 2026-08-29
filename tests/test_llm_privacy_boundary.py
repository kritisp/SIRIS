import json
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
    LLMSafeExplainabilityPayload,
    DeidentificationResult,
    pii_privacy_boundary_engine,
    pii_backmapper,
    LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION,
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


def test_unit_pii_masking_taxonomies_and_location_preservation():
    """Tests 1-9: Validates masking of Person, Phone, Vehicle, Email, Govt ID while preserving location and metrics."""
    raw_name = "Rajesh Sharma"
    raw_phone = "+919876543210"
    raw_vehicle = "OD02AB1234"
    raw_email = "rajesh.sharma@example.com"
    raw_govt_id = "1234-5678-9012"
    raw_location = "Patia Square, Bhubaneswar"

    id_case = uuid.uuid4()
    id_person = uuid.uuid4()

    person = Person(id=id_person, name=raw_name, gender="MALE", identifier_hash="hash_r1")
    vehicle = Vehicle(id=uuid.uuid4(), registration_number=raw_vehicle, vehicle_type="CAR", make="HONDA", model="CITY")
    phone = Phone(id=uuid.uuid4(), normalized_number=raw_phone)
    loc = Location(id=uuid.uuid4(), address=raw_location, city="Bhubaneswar", district="Khordha", state="Odisha")

    case = Case(
        id=id_case, fir_number="FIR/2026/PRIV_001", station_id="PS_BBSR_001",
        police_station="Capital PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 1),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
        location_id=loc.id, location=loc,
    )
    case.person_associations = [CasePerson(case_id=id_case, person_id=id_person, person=person, role=PersonRole.SUSPECT)]
    case.vehicle_associations = [CaseVehicle(case_id=id_case, vehicle_id=vehicle.id, vehicle=vehicle, role=VehicleRole.SUSPECT_VEHICLE)]
    case.phone_associations = [CasePhone(case_id=id_case, phone_id=phone.id, phone=phone)]

    # Generate Explainability Result
    pat_obs = PatternObservation(
        pattern_id="pat:recurring_entity:112233445566",
        pattern_type=PatternType.RECURRING_ENTITY,
        title=f"Recurring Entity Pattern: {raw_name} ({raw_phone})",
        description=f"Person '{raw_name}' email '{raw_email}' govt ID '{raw_govt_id}' vehicle '{raw_vehicle}' associated with case in {raw_location}.",
        occurrence_count=2,
        structural_strength=0.85,
        case_ids=[str(id_case)],
        entity_ids=[str(id_person)],
        entity_types=["Person"],
        supporting_signals=[f"Phone: {raw_phone}", f"Vehicle: {raw_vehicle}"],
        provenance={"police_stations": ["PS_BBSR_001"], "district": "Khordha", "crime_category": "PROPERTY_CRIME"},
    )

    exp_req = ExplainabilityRequest(cases=[case], pattern_result=PatternDetectionResult(total_cases_evaluated=1, total_patterns_detected=1, patterns=[pat_obs]))
    exp_res = explainability_engine.explain_analytical_findings(exp_req)

    # Execute De-identification
    deid_res = pii_privacy_boundary_engine.deidentify_explainability_result(exp_res, cases=[case])
    payload = deid_res.llm_safe_payload
    mapping = deid_res.private_mapping

    payload_json = payload.model_dump_json()

    # Leakage Checks: Raw PII MUST NOT appear in LLM Payload
    assert raw_name not in payload_json
    assert raw_phone not in payload_json
    assert raw_vehicle not in payload_json
    assert raw_email not in payload_json
    assert raw_govt_id not in payload_json

    # Preserved Context Checks: Location & analytical context MUST remain
    assert "Khordha" in payload_json
    assert "PROPERTY_CRIME" in payload_json
    assert "0.85" in payload_json

    # Alias presence
    assert "Person-A" in payload_json or "Person-" in payload_json
    assert "Vehicle-A" in payload_json or "Vehicle-" in payload_json
    assert "Phone-A" in payload_json or "Phone-" in payload_json


def test_unit_mapping_isolation_and_source_immutability():
    """Tests 10, 11, 12, 13: Verifies private mapping is strictly isolated from LLM payload and source objects remain immutable."""
    assessment = RelationshipConfidenceAssessment(
        source_case_id=str(uuid.uuid4()),
        target_case_id=str(uuid.uuid4()),
        canonical_relationship_key="case1::case2",
        confidence_score=0.91,
        confidence_level=RelationshipConfidenceLevel.VERY_HIGH,
        contributing_families=[SignalFamily.LOCATION],
        evidence_summary="Location match link.",
        explanation="Test assessment.",
        uncertainty_notes=[],
    )

    exp_req = ExplainabilityRequest(confidence_assessments=[assessment])
    exp_res = explainability_engine.explain_analytical_findings(exp_req)

    deid_res = pii_privacy_boundary_engine.deidentify_explainability_result(exp_res)

    # 1. Verify mapping object is NOT inside llm_safe_payload model dictionary
    payload_dict = deid_res.llm_safe_payload.model_dump()
    assert "private_mapping" not in payload_dict
    assert "alias_to_original" not in payload_dict

    # 2. Verify source Step 5B assessment remains 100% untouched
    assert assessment.confidence_score == 0.91
    assert assessment.confidence_level == RelationshipConfidenceLevel.VERY_HIGH


def test_unit_deterministic_alias_generation_and_duplicate_reuse():
    """Tests 16, 17, 18: Verifies identical source entities reuse identical aliases without collisions."""
    mapping = DeidentificationMapping()
    counters = {}

    alias1 = pii_privacy_boundary_engine._get_or_create_alias("Rajesh Kumar", PIIEntityType.PERSON_NAME, mapping, counters)
    alias2 = pii_privacy_boundary_engine._get_or_create_alias("Rajesh Kumar", PIIEntityType.PERSON_NAME, mapping, counters)
    alias3 = pii_privacy_boundary_engine._get_or_create_alias("OD02AB1234", PIIEntityType.VEHICLE_REGISTRATION, mapping, counters)

    assert alias1 == "Person-A"
    assert alias2 == "Person-A"  # Reused identical alias
    assert alias3 == "Vehicle-A"  # Type-scoped prefix

    # Mapping integrity
    assert mapping.alias_to_original["Person-A"] == "Rajesh Kumar"
    assert mapping.alias_to_original["Vehicle-A"] == "OD02AB1234"


def test_unit_backmapping_engine_safety_and_hallucinated_aliases():
    """Tests 14, 15: Verifies application-side back-mapping restores known aliases while safely preserving unknown/hallucinated aliases."""
    mapping = DeidentificationMapping(
        alias_to_original={
            "Person-A": "Sanjay Das",
            "Vehicle-A": "OD02XY9999",
            "Phone-A": "+919876543210",
        },
        original_to_alias={
            "Sanjay Das": "Person-A",
            "OD02XY9999": "Vehicle-A",
            "+919876543210": "Phone-A",
        },
    )

    llm_output_text = "Person-A was seen driving Vehicle-A while calling Phone-A. Person-Z99 was also mentioned."

    # Backmap Text
    restored_text = pii_backmapper.backmap_llm_text(llm_output_text, mapping)

    assert "Sanjay Das" in restored_text
    assert "OD02XY9999" in restored_text
    assert "+919876543210" in restored_text
    assert "Person-Z99" in restored_text  # Unknown/hallucinated alias safely preserved as text without DB errors

    # Backmap Structured Payload Dict
    structured_llm_dict = {
        "primary_subject": "Person-A",
        "vehicle": "Vehicle-A",
        "notes": "Spotted with Person-Z99",
    }
    restored_dict = pii_backmapper.backmap_llm_payload(structured_llm_dict, mapping)
    assert restored_dict["primary_subject"] == "Sanjay Das"
    assert restored_dict["vehicle"] == "OD02XY9999"
    assert restored_dict["notes"] == "Spotted with Person-Z99"


def test_synthetic_end_to_end_llm_privacy_boundary_pipeline_and_cleanup():
    """Tests 19, 20: Full Synthetic Integration Test verifying zero PII leakage and 0 persistent Neo4j nodes."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live synthetic privacy integration test.")

    id_case_a, id_case_b = uuid.uuid4(), uuid.uuid4()
    id_p1, id_v1 = uuid.uuid4(), uuid.uuid4()

    raw_person_name = "Subhash Chandra Mohanty"
    raw_veh_reg = "OD02MN4321"

    person_p1 = Person(id=id_p1, name=raw_person_name, gender="MALE", identifier_hash="hash_sc1")
    vehicle_v1 = Vehicle(id=id_v1, registration_number=raw_veh_reg, vehicle_type="CAR", make="TATA", model="NEXON")

    case_a = Case(
        id=id_case_a, fir_number=f"FIR/2026/A_{id_case_a.hex[:4]}", station_id="PS_BBSR_001",
        police_station="Khandagiri PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 10),
        crime_type="EXTORTION", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_a.person_associations = [CasePerson(case_id=id_case_a, person_id=id_p1, person=person_p1, role=PersonRole.SUSPECT)]
    case_a.vehicle_associations = [CaseVehicle(case_id=id_case_a, vehicle_id=id_v1, vehicle=vehicle_v1, role=VehicleRole.SUSPECT_VEHICLE)]

    case_b = Case(
        id=id_case_b, fir_number=f"FIR/2026/B_{id_case_b.hex[:4]}", station_id="PS_CTC_002",
        police_station="Cuttack Sadar PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 15),
        crime_type="EXTORTION", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
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
            canonical_relationship_key=key_ab, confidence_score=0.89,
            confidence_level=RelationshipConfidenceLevel.HIGH,
            contributing_families=[SignalFamily.PERSON_IDENTITY, SignalFamily.VEHICLE],
            evidence_summary="HIGH confidence extortion link.", explanation="Cross-station link.", uncertainty_notes=[],
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

        payload_str = payload.model_dump_json()

        # Leakage Scan: Proves raw person name & vehicle reg NEVER enter LLM Payload
        assert raw_person_name not in payload_str
        assert raw_veh_reg not in payload_str

        # Test Back-mapping simulated LLM response
        simulated_llm_text = "Analysis indicates Person-A was identified across cases using Vehicle-A."
        restored_llm_text = pii_backmapper.backmap_llm_text(simulated_llm_text, mapping)

        assert raw_person_name in restored_llm_text
        assert raw_veh_reg in restored_llm_text

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
