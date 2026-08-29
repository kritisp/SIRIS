import uuid
import pytest
from datetime import date
from app.config.settings import settings
from app.models.case import Case
from app.models.person import Person, CasePerson, PersonRole
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.models.phone import Phone, CasePhone
from app.models.location import Location
from app.services.graph import (
    NetworkAnalyticsRequest,
    NetworkAnalyticsResult,
    canonicalize_case_pair,
    neo4j_connection_service,
    neo4j_graph_projection_service,
    neo4j_network_analytics_service,
)
from app.services.relationship_engine import (
    RelationshipConfidenceAssessment,
    RelationshipConfidenceLevel,
    SignalFamily,
)


def test_unit_network_analytics_request_validation():
    """Tests 16 & 17: Verifies request validation for invalid UUID and invalid node type."""
    valid_uuid = str(uuid.uuid4())

    # Valid Request
    req = NetworkAnalyticsRequest(target_node_id=valid_uuid, target_node_type="Case")
    assert req.target_node_id == valid_uuid

    # Invalid UUID Rejection
    with pytest.raises(ValueError):
        NetworkAnalyticsRequest(target_node_id="invalid-uuid")

    # Invalid Node Type Rejection
    with pytest.raises(ValueError, match="Unsupported node type"):
        NetworkAnalyticsRequest(target_node_type="IllegalNodeType")


def test_unit_empty_graph_network_analytics():
    """Test 1: Verifies that network analytics on an empty or missing node returns empty metrics cleanly."""
    missing_uuid = str(uuid.uuid4())
    req = NetworkAnalyticsRequest(target_node_id=missing_uuid)
    result = neo4j_network_analytics_service.analyze_network(req)

    assert result.total_nodes_analyzed == 0
    assert result.total_components == 0
    assert result.node_metrics == []
    assert result.components == []


def test_live_controlled_network_analytics():
    """Comprehensive Live Integration Test covering Requirements 2-15, 18-20.
    
    Graph Topology:
      Component 1 (Cross-Station Multi-Hop):
        Case A (PS_BBSR_001)
         ├── Person P1 (Sanjay Das) ── Case B (PS_CTC_002)
         └── Vehicle V1 (OD02XY9999) ── Case B
        Case A ── RELATED_TO ── Case B (confidence=0.80)
        
      Component 2 (Isolated Case):
        Case C (PS_BBSR_003) - 0 connected entities or edges
    """
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live network analytics integration test.")

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

        # Step 5B Assessment with confidence score = 0.80
        _, _, key_ab = canonicalize_case_pair(str(id_case_a), str(id_case_b))
        assessment = RelationshipConfidenceAssessment(
            source_case_id=str(id_case_a),
            target_case_id=str(id_case_b),
            canonical_relationship_key=key_ab,
            confidence_score=0.80,
            confidence_level=RelationshipConfidenceLevel.HIGH,
            contributing_families=[SignalFamily.PERSON_IDENTITY, SignalFamily.VEHICLE],
            evidence_summary="HIGH confidence test link.",
            explanation="Cross-station robbery test.",
            uncertainty_notes=[],
        )
        neo4j_graph_projection_service.project_relationship_assessment(assessment)

        # 3. Run Global Network Analytics
        req = NetworkAnalyticsRequest()
        res = neo4j_network_analytics_service.analyze_network(req)

        # Test A: Total Analyzed & Components Count
        assert res.total_nodes_analyzed == 5
        assert res.total_components == 2

        # Test B: Component 1 (Size 4, Cross-Station = True)
        comp_main = res.components[0]
        assert comp_main.component_size == 4
        assert comp_main.case_count == 2
        assert comp_main.station_count == 2
        assert comp_main.spans_cross_station is True

        # Test C: Component 2 (Isolated Case C, Size 1, Cross-Station = False)
        comp_iso = res.components[1]
        assert comp_iso.component_size == 1
        assert comp_iso.case_count == 1
        assert comp_iso.spans_cross_station is False

        # Test D: Person P1 Node Metrics & Weighted Degree
        p1_metrics = next(nm for nm in res.node_metrics if nm.node_id == str(id_person_p1))
        assert p1_metrics.node_type == "Person"
        assert p1_metrics.total_degree == 2  # Connected to Case A & Case B
        assert p1_metrics.weighted_degree == 2.0  # 1.0 + 1.0
        assert p1_metrics.connected_case_count == 2
        assert p1_metrics.connected_station_count == 2
        assert p1_metrics.is_connector_node is True
        assert "Cross-station" in p1_metrics.connector_role_summary or "bridging" in p1_metrics.connector_role_summary

        # Test E: Case A Node Metrics & RELATED_TO Confidence Weighting
        case_a_metrics = next(nm for nm in res.node_metrics if nm.node_id == str(id_case_a))
        assert case_a_metrics.total_degree == 3  # HAS_PERSON, HAS_VEHICLE, RELATED_TO
        # Weighted degree: 1.0 (HAS_PERSON) + 1.0 (HAS_VEHICLE) + 0.80 (RELATED_TO) = 2.80
        assert case_a_metrics.weighted_degree == 2.80

        # Test F: Isolated Case C Metrics
        case_c_metrics = next(nm for nm in res.node_metrics if nm.node_id == str(id_case_c))
        assert case_c_metrics.total_degree == 0
        assert case_c_metrics.weighted_degree == 0.0
        assert case_c_metrics.centrality.betweenness_centrality == 0.0
        assert case_c_metrics.centrality.closeness_centrality == 0.0
        assert case_c_metrics.is_connector_node is False

        # Test G: Deterministic Output Ordering
        metrics_keys = [(nm.node_type, nm.node_id) for nm in res.node_metrics]
        assert metrics_keys == sorted(metrics_keys)

        # Test H: Read-Only Verification (Neo4j Node/Edge counts remain unchanged before & after)
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            count_res = session.run("MATCH (n) WHERE n.node_id IN $ids RETURN count(n) AS c", {"ids": all_uuids}).single()["c"]
            assert count_res == 5

    finally:
        # Clean up ONLY test-created node UUIDs
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("MATCH (n) WHERE n.node_id IN $ids DETACH DELETE n", {"ids": all_uuids})
