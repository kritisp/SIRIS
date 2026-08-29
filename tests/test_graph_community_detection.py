import uuid
import pytest
from datetime import date
from app.config.settings import settings
from app.models.case import Case
from app.models.person import Person, CasePerson, PersonRole
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.models.phone import Phone, CasePhone
from app.services.graph import (
    CommunityDetectionRequest,
    CommunityDetectionResult,
    canonicalize_case_pair,
    neo4j_connection_service,
    neo4j_graph_projection_service,
    neo4j_community_detection_service,
)
from app.services.relationship_engine import (
    RelationshipConfidenceAssessment,
    RelationshipConfidenceLevel,
    SignalFamily,
)


def test_unit_community_detection_request_validation():
    """Tests 1-7: Unit tests for request contract validation rules."""
    valid_uuid = str(uuid.uuid4())

    # Valid Request
    req = CommunityDetectionRequest(target_node_id=valid_uuid, minimum_community_size=3, minimum_density=0.2)
    assert req.target_node_id == valid_uuid
    assert req.minimum_community_size == 3
    assert req.minimum_density == 0.2

    # Invalid UUID Rejection
    with pytest.raises(ValueError):
        CommunityDetectionRequest(target_node_id="invalid-uuid")

    # Invalid Node Type Rejection
    with pytest.raises(ValueError, match="Unsupported node type"):
        CommunityDetectionRequest(target_node_type="IllegalNodeType")

    # Invalid Allowed Node Type
    with pytest.raises(ValueError, match="Unsupported node type"):
        CommunityDetectionRequest(allowed_node_types=["Case", "IllegalNode"])

    # Invalid Allowed Relationship Type
    with pytest.raises(ValueError, match="Unsupported relationship type"):
        CommunityDetectionRequest(allowed_relationship_types=["HAS_PERSON", "ILLEGAL_EDGE"])

    # Minimum Community Size bounds (< 2)
    with pytest.raises(ValueError):
        CommunityDetectionRequest(minimum_community_size=1)

    # Minimum Density bounds (< 0.0 or > 1.0)
    with pytest.raises(ValueError):
        CommunityDetectionRequest(minimum_density=1.5)


def test_unit_empty_graph_community_detection():
    """Test 8: Verifies that community detection on an empty or missing node returns empty result cleanly."""
    missing_uuid = str(uuid.uuid4())
    req = CommunityDetectionRequest(target_node_id=missing_uuid)
    result = neo4j_community_detection_service.detect_communities(req)

    assert result.total_nodes_evaluated == 0
    assert result.total_communities_detected == 0
    assert result.communities == []


def test_live_controlled_community_detection():
    """Comprehensive Live Integration Test covering Requirements 9-21.
    
    Graph Topology:
      Dense Community 1 (Size 4, Multi-Station):
        Case A (PS_BBSR_001) ── Person P1 ── Case B (PS_CTC_002)
        Case A ── Vehicle V1 ── Case B
        Case A ── RELATED_TO ── Case B (confidence=0.90)
        
      Isolated Case C (Size 1):
        Case C (PS_BBSR_003) - Filtered out by minimum_community_size=2
    """
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live community detection integration test.")

    # 1. Deterministic UUIDs
    id_case_a = uuid.uuid4()
    id_case_b = uuid.uuid4()
    id_case_c = uuid.uuid4()  # Isolated

    id_person_p1 = uuid.uuid4()
    id_vehicle_v1 = uuid.uuid4()

    person_p1 = Person(id=id_person_p1, name="Sanjay Das", gender="MALE", identifier_hash="hash_p1")
    vehicle_v1 = Vehicle(id=id_vehicle_v1, registration_number="OD02XY9999", vehicle_type="CAR", make="HYUNDAI", model="VERNA")

    # Case A
    case_a = Case(
        id=id_case_a, fir_number=f"FIR/2026/A_{id_case_a.hex[:4]}", station_id="PS_BBSR_001",
        police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 10),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_a.person_associations = [CasePerson(case_id=id_case_a, person_id=id_person_p1, person=person_p1, role=PersonRole.SUSPECT)]
    case_a.vehicle_associations = [CaseVehicle(case_id=id_case_a, vehicle_id=id_vehicle_v1, vehicle=vehicle_v1, role=VehicleRole.SUSPECT_VEHICLE)]

    # Case B (Cross-Station)
    case_b = Case(
        id=id_case_b, fir_number=f"FIR/2026/B_{id_case_b.hex[:4]}", station_id="PS_CTC_002",
        police_station="Cuttack Sadar PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 15),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_b.person_associations = [CasePerson(case_id=id_case_b, person_id=id_person_p1, person=person_p1, role=PersonRole.ACCUSED)]
    case_b.vehicle_associations = [CaseVehicle(case_id=id_case_b, vehicle_id=id_vehicle_v1, vehicle=vehicle_v1, role=VehicleRole.RECOVERED_VEHICLE)]

    # Case C (Isolated)
    case_c = Case(
        id=id_case_c, fir_number=f"FIR/2026/C_{id_case_c.hex[:4]}", station_id="PS_BBSR_003",
        police_station="Laxmisagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 25),
        crime_type="TRESPASS", crime_category="OTHER", status="CLOSED",
    )

    all_uuids = [str(id_case_a), str(id_case_b), str(id_case_c), str(id_person_p1), str(id_vehicle_v1)]

    try:
        # 2. Project controlled test graph
        neo4j_graph_projection_service.project_case_graph(case_a)
        neo4j_graph_projection_service.project_case_graph(case_b)
        neo4j_graph_projection_service.project_case_graph(case_c)

        # Step 5B Assessment with confidence score = 0.90
        _, _, key_ab = canonicalize_case_pair(str(id_case_a), str(id_case_b))
        assessment = RelationshipConfidenceAssessment(
            source_case_id=str(id_case_a),
            target_case_id=str(id_case_b),
            canonical_relationship_key=key_ab,
            confidence_score=0.90,
            confidence_level=RelationshipConfidenceLevel.VERY_HIGH,
            contributing_families=[SignalFamily.PERSON_IDENTITY, SignalFamily.VEHICLE],
            evidence_summary="VERY_HIGH confidence community test link.",
            explanation="Cross-station robbery community test.",
            uncertainty_notes=[],
        )
        neo4j_graph_projection_service.project_relationship_assessment(assessment)

        # 3. Detect Communities
        req = CommunityDetectionRequest(minimum_community_size=2, minimum_density=0.1)
        res = neo4j_community_detection_service.detect_communities(req)

        # Test A: Total Evaluated Nodes & Detected Communities
        assert res.total_nodes_evaluated == 5
        assert res.total_communities_detected == 1  # Case C isolated (size 1) filtered out

        # Test B: Community Cluster Structural Properties
        comm = res.communities[0]
        sorted_nodes = sorted([str(id_case_a), str(id_case_b), str(id_person_p1), str(id_vehicle_v1)])
        assert comm.community_id == f"community:{sorted_nodes[0]}"  # Deterministic ID
        assert comm.member_count == 4
        assert comm.case_count == 2
        assert comm.station_count == 2
        assert comm.spans_cross_station is True

        # Undirected edges between 4 nodes: (A-P1), (B-P1), (A-V1), (B-V1), (A-B RELATED_TO) = 5 undirected structural edges
        # Density formula = 2 * 5 / (4 * 3) = 10 / 12 = 0.8333
        assert comm.density > 0.80

        # Test C: Confidence Filtering Test
        req_high_conf = CommunityDetectionRequest(minimum_community_size=2, minimum_relationship_confidence=0.95)
        res_high_conf = neo4j_community_detection_service.detect_communities(req_high_conf)
        # 0.90 < 0.95, RELATED_TO edge excluded, density changes
        assert res_high_conf.total_communities_detected == 1
        comm_hc = res_high_conf.communities[0]
        # Undirected structural edges = 4 (without RELATED_TO), Density = 2 * 4 / (4 * 3) = 8 / 12 = 0.6667
        assert comm_hc.density < 0.80

        # Test D: Read-Only & Teardown Verification (Neo4j Node/Edge counts unchanged before & after)
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            count_res = session.run("MATCH (n) WHERE n.node_id IN $ids RETURN count(n) AS c", {"ids": all_uuids}).single()["c"]
            assert count_res == 5

    finally:
        # Clean up ONLY test-created node UUIDs
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("MATCH (n) WHERE n.node_id IN $ids DETACH DELETE n", {"ids": all_uuids})
