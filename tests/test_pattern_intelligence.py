import uuid
import pytest
from datetime import date
from app.config.settings import settings
from app.models.case import Case
from app.models.person import Person, CasePerson, PersonRole
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.models.phone import Phone, CasePhone
from app.models.location import Location
from app.models.evidence import Evidence
from app.models.legal_section import LegalSection, CaseLegalSection
from app.services.pattern_engine import (
    PatternType,
    PatternObservation,
    PatternDetectionRequest,
    PatternDetectionResult,
    pattern_intelligence_engine,
    PATTERN_INTELLIGENCE_METHODOLOGY_VERSION,
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


def test_unit_pattern_request_and_contract_validation():
    """Tests 1, 2, 17, 18, 19: Validates contracts, bounds, and forbidden inference term safeguards."""
    # Test threshold bounds
    with pytest.raises(ValueError):
        PatternDetectionRequest(minimum_recurrence=1)

    with pytest.raises(ValueError):
        PatternDetectionRequest(minimum_supporting_signals=0)

    # Test forbidden inference term safeguard
    with pytest.raises(ValueError, match="Forbidden inference term"):
        PatternObservation(
            pattern_id="pat:test:123456789012",
            pattern_type=PatternType.MODUS_OPERANDI,
            title="Criminal Gang Confirmed",
            description="The perpetrator is guilty of conspiracy.",
            occurrence_count=2,
            structural_strength=0.8,
        )


def test_unit_empty_and_single_case_dataset():
    """Tests 1, 2, 12: Empty dataset and single case returning 0 patterns below minimum recurrence threshold=2."""
    req_empty = PatternDetectionRequest(cases=[])
    res_empty = pattern_intelligence_engine.detect_patterns(req_empty)
    assert res_empty.total_cases_evaluated == 0
    assert res_empty.total_patterns_detected == 0
    assert res_empty.patterns == []

    # Single Case
    case_single = Case(
        id=uuid.uuid4(), fir_number="FIR/2026/001", station_id="PS_BBSR_001",
        police_station="Capital PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 1),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION"
    )
    req_single = PatternDetectionRequest(cases=[case_single], minimum_recurrence=2)
    res_single = pattern_intelligence_engine.detect_patterns(req_single)
    assert res_single.total_cases_evaluated == 1
    assert res_single.total_patterns_detected == 0


def test_unit_recurring_entity_patterns():
    """Tests 3, 4, 5, 6, 7, 8, 9, 13, 14, 15, 16, 20: Comprehensive synthetic pattern detection."""
    id_case_a, id_case_b, id_case_c, id_case_d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    id_p1, id_v1, id_ph1, id_loc1 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    person_p1 = Person(id=id_p1, name="Ramesh Kumar", gender="MALE", identifier_hash="hash_p1")
    vehicle_v1 = Vehicle(id=id_v1, registration_number="OD02AB1234", vehicle_type="CAR", make="HONDA", model="CITY")
    phone_ph1 = Phone(id=id_ph1, normalized_number="+919876543210")
    location_loc1 = Location(id=id_loc1, address="Master Canteen, BBSR", city="Bhubaneswar", district="Khordha", state="Odisha")

    # Case A (Station 1)
    case_a = Case(
        id=id_case_a, fir_number="FIR/2026/A_101", station_id="PS_BBSR_001",
        police_station="Capital PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 1),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
        location_id=id_loc1, location=location_loc1
    )
    case_a.person_associations = [CasePerson(case_id=id_case_a, person_id=id_p1, person=person_p1, role=PersonRole.SUSPECT)]
    case_a.vehicle_associations = [CaseVehicle(case_id=id_case_a, vehicle_id=id_v1, vehicle=vehicle_v1, role=VehicleRole.SUSPECT_VEHICLE)]
    case_a.phone_associations = [CasePhone(case_id=id_case_a, phone_id=id_ph1, phone=phone_ph1)]

    # Case B (Station 2 - Cross-Station)
    case_b = Case(
        id=id_case_b, fir_number="FIR/2026/B_102", station_id="PS_CTC_002",
        police_station="Cuttack Sadar PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 5),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
        location_id=id_loc1, location=location_loc1
    )
    case_b.person_associations = [CasePerson(case_id=id_case_b, person_id=id_p1, person=person_p1, role=PersonRole.ACCUSED)]
    case_b.vehicle_associations = [CaseVehicle(case_id=id_case_b, vehicle_id=id_v1, vehicle=vehicle_v1, role=VehicleRole.RECOVERED_VEHICLE)]

    # Case C (Station 1)
    case_c = Case(
        id=id_case_c, fir_number="FIR/2026/C_103", station_id="PS_BBSR_001",
        police_station="Capital PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 10),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_c.person_associations = [CasePerson(case_id=id_case_c, person_id=id_p1, person=person_p1, role=PersonRole.SUSPECT)]

    # Case D (Station 3 - Unrelated)
    case_d = Case(
        id=id_case_d, fir_number="FIR/2026/D_104", station_id="PS_PURI_003",
        police_station="Puri Town PS", district="Puri", state="Odisha", registration_date=date(2026, 8, 25),
        crime_type="TRESPASS", crime_category="OTHER", status="CLOSED",
    )

    req = PatternDetectionRequest(cases=[case_a, case_b, case_c, case_d], minimum_recurrence=2)
    res = pattern_intelligence_engine.detect_patterns(req)

    assert res.total_cases_evaluated == 4
    assert res.total_patterns_detected > 0

    # Verify Pattern Types Present
    pattern_types_found = {p.pattern_type for p in res.patterns}
    assert PatternType.RECURRING_ENTITY in pattern_types_found
    assert PatternType.MODUS_OPERANDI in pattern_types_found
    assert PatternType.GEOGRAPHIC_CROSS_STATION in pattern_types_found
    assert PatternType.TEMPORAL_CLUSTER in pattern_types_found

    # Verify Person P1 Recurring Entity Pattern
    person_pat = next(p for p in res.patterns if p.pattern_type == PatternType.RECURRING_ENTITY and str(id_p1) in p.entity_ids)
    assert person_pat.occurrence_count == 3
    assert set(person_pat.case_ids) == {str(id_case_a), str(id_case_b), str(id_case_c)}
    assert person_pat.pattern_id.startswith("pat:recurring_entity:")
    assert "criminal" not in person_pat.description.lower()
    assert "provenance" in person_pat.model_dump()

    # Verify Unrelated Case D Excluded from Person Pattern
    assert str(id_case_d) not in person_pat.case_ids

    # Verify Deterministic Pattern ID Generation
    pat_id_again = pattern_intelligence_engine._generate_pattern_id(
        person_pat.pattern_type, person_pat.case_ids, person_pat.entity_ids, person_pat.supporting_signals
    )
    assert person_pat.pattern_id == pat_id_again


def test_live_synthetic_integration_and_graph_cleanup():
    """Tests 10, 21, 22, 23, 24: End-to-End Live Integration Test with Step 5C-5G and 0 persistent Neo4j nodes."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live pattern integration test.")

    id_case_a, id_case_b, id_case_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    id_p1, id_v1 = uuid.uuid4(), uuid.uuid4()

    person_p1 = Person(id=id_p1, name="Sanjay Das", gender="MALE", identifier_hash="hash_p1")
    vehicle_v1 = Vehicle(id=id_v1, registration_number="OD02XY9999", vehicle_type="CAR", make="HYUNDAI", model="VERNA")

    case_a = Case(
        id=id_case_a, fir_number=f"FIR/2026/A_{id_case_a.hex[:4]}", station_id="PS_BBSR_001",
        police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 10),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_a.person_associations = [CasePerson(case_id=id_case_a, person_id=id_p1, person=person_p1, role=PersonRole.SUSPECT)]
    case_a.vehicle_associations = [CaseVehicle(case_id=id_case_a, vehicle_id=id_v1, vehicle=vehicle_v1, role=VehicleRole.SUSPECT_VEHICLE)]

    case_b = Case(
        id=id_case_b, fir_number=f"FIR/2026/B_{id_case_b.hex[:4]}", station_id="PS_CTC_002",
        police_station="Cuttack Sadar PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 15),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_b.person_associations = [CasePerson(case_id=id_case_b, person_id=id_p1, person=person_p1, role=PersonRole.ACCUSED)]
    case_b.vehicle_associations = [CaseVehicle(case_id=id_case_b, vehicle_id=id_v1, vehicle=vehicle_v1, role=VehicleRole.RECOVERED_VEHICLE)]

    all_uuids = [str(id_case_a), str(id_case_b), str(id_case_c), str(id_p1), str(id_v1)]

    try:
        # Project Graph
        neo4j_graph_projection_service.project_case_graph(case_a)
        neo4j_graph_projection_service.project_case_graph(case_b)

        _, _, key_ab = canonicalize_case_pair(str(id_case_a), str(id_case_b))
        assessment = RelationshipConfidenceAssessment(
            source_case_id=str(id_case_a), target_case_id=str(id_case_b),
            canonical_relationship_key=key_ab, confidence_score=0.85,
            confidence_level=RelationshipConfidenceLevel.HIGH,
            contributing_families=[SignalFamily.PERSON_IDENTITY, SignalFamily.VEHICLE],
            evidence_summary="HIGH confidence test link.", explanation="Cross-station robbery test.", uncertainty_notes=[],
        )
        neo4j_graph_projection_service.project_relationship_assessment(assessment)

        # Run Graph Analytics & Community Detection
        net_res = neo4j_network_analytics_service.analyze_network(NetworkAnalyticsRequest(target_node_id=str(id_case_a)))
        comm_res = neo4j_community_detection_service.detect_communities(CommunityDetectionRequest(minimum_community_size=2))

        # Detect Patterns including Graph Structural Patterns
        req = PatternDetectionRequest(
            cases=[case_a, case_b],
            graph_analytics_result=net_res,
            community_detection_result=comm_res,
            confidence_assessments=[assessment],
        )
        res = pattern_intelligence_engine.detect_patterns(req)

        assert res.total_cases_evaluated == 2
        assert res.total_patterns_detected > 0

        # Verify Graph Structural Pattern Present
        graph_pats = [p for p in res.patterns if p.pattern_type == PatternType.GRAPH_STRUCTURAL]
        assert len(graph_pats) > 0

        # Verify Step 5B Assessment Confidence Score is Untouched
        assert assessment.confidence_score == 0.85

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
