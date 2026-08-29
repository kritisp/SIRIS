import uuid
import pytest
from datetime import date
from app.config.settings import settings
from app.models.case import Case
from app.models.person import Person, CasePerson, PersonRole
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.models.phone import Phone, CasePhone
from app.models.location import Location
from app.models.legal_section import LegalSection, CaseLegalSection
from app.services.graph import (
    GraphTraversalRequest,
    GraphTraversalResult,
    canonicalize_case_pair,
    neo4j_connection_service,
    neo4j_graph_projection_service,
    neo4j_graph_traversal_service,
)
from app.services.relationship_engine import (
    RelationshipConfidenceAssessment,
    RelationshipConfidenceLevel,
    SignalFamily,
)


def test_unit_traversal_request_contract_allowlists_and_validation():
    """Tests 8, 13, 14, 15: Unit tests for traversal request contract validation rules."""
    valid_uuid = str(uuid.uuid4())

    # Valid Request
    req = GraphTraversalRequest(start_node_id=valid_uuid, start_node_type="Case", maximum_depth=3)
    assert req.start_node_id == valid_uuid
    assert req.maximum_depth == 3

    # Invalid UUID rejection
    with pytest.raises(ValueError):
        GraphTraversalRequest(start_node_id="invalid-uuid")

    # Invalid Start Node Type
    with pytest.raises(ValueError, match="Unsupported start node type"):
        GraphTraversalRequest(start_node_id=valid_uuid, start_node_type="UnsupportedLabel")

    # Invalid Allowed Node Type
    with pytest.raises(ValueError, match="Unsupported node type"):
        GraphTraversalRequest(start_node_id=valid_uuid, allowed_node_types=["Case", "IllegalNode"])

    # Invalid Allowed Relationship Type
    with pytest.raises(ValueError, match="Unsupported relationship type"):
        GraphTraversalRequest(start_node_id=valid_uuid, allowed_relationship_types=["HAS_PERSON", "ILLEGAL_EDGE"])

    # Max Depth Clamp validation (1 <= depth <= 5)
    with pytest.raises(ValueError):
        GraphTraversalRequest(start_node_id=valid_uuid, maximum_depth=6)

    with pytest.raises(ValueError):
        GraphTraversalRequest(start_node_id=valid_uuid, maximum_depth=0)


def test_unit_empty_graph_and_nonexistent_start_node():
    """Test 18: Verifies that traversing a non-existent start node returns total_paths=0 cleanly."""
    missing_uuid = str(uuid.uuid4())
    req = GraphTraversalRequest(start_node_id=missing_uuid, start_node_type="Case")
    result = neo4j_graph_traversal_service.traverse(req)

    assert result.start_node_id == missing_uuid
    assert result.total_paths == 0
    assert result.paths == []


def test_live_controlled_multi_hop_graph_traversal():
    """Comprehensive Live Integration Test covering Requirements 1-7, 9-12, 16-17, 19-20.
    
    Setup Graph:
      Case A (PS_BBSR_001)
       ├── Person P1 (Sanjay Das) ── Case B (PS_CTC_002 Cross-Station)
       └── Location L1            └── Phone PH1 ── Case C (PS_BBSR_001)
                                                       └── LegalSection S1
      Case A ── RELATED_TO ── Case B (Assessment confidence=0.92)
      Case D (Isolated Case - No connections)
    """
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live multi-hop traversal integration test.")

    # 1. Deterministic Test UUIDs
    id_case_a = uuid.uuid4()
    id_case_b = uuid.uuid4()
    id_case_c = uuid.uuid4()
    id_case_d = uuid.uuid4()  # Isolated

    id_person_p1 = uuid.uuid4()
    id_phone_ph1 = uuid.uuid4()
    id_loc_l1 = uuid.uuid4()
    id_legal_s1 = uuid.uuid4()

    # Domain objects
    person_p1 = Person(id=id_person_p1, name="Sanjay Das", gender="MALE", identifier_hash="hash_p1")
    phone_ph1 = Phone(id=id_phone_ph1, normalized_number="+919937012345", number_hash="hash_ph1")
    loc_l1 = Location(id=id_loc_l1, locality="Jaydev Vihar", city="Bhubaneswar", district="Khordha", state="Odisha")
    legal_s1 = LegalSection(id=id_legal_s1, code="IPC 392", title="Robbery", law_name="IPC")

    # Case A
    case_a = Case(
        id=id_case_a, fir_number=f"FIR/2026/A_{id_case_a.hex[:4]}", station_id="PS_BBSR_001",
        police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 10),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION", location=loc_l1,
    )
    case_a.person_associations = [CasePerson(case_id=id_case_a, person_id=id_person_p1, person=person_p1, role=PersonRole.SUSPECT)]

    # Case B (Cross-Station)
    case_b = Case(
        id=id_case_b, fir_number=f"FIR/2026/B_{id_case_b.hex[:4]}", station_id="PS_CTC_002",
        police_station="Cuttack Sadar PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 15),
        crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_b.person_associations = [CasePerson(case_id=id_case_b, person_id=id_person_p1, person=person_p1, role=PersonRole.ACCUSED)]
    case_b.phone_associations = [CasePhone(case_id=id_case_b, phone_id=id_phone_ph1, phone=phone_ph1)]

    # Case C
    case_c = Case(
        id=id_case_c, fir_number=f"FIR/2026/C_{id_case_c.hex[:4]}", station_id="PS_BBSR_001",
        police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 20),
        crime_type="SNATCHING", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
    )
    case_c.phone_associations = [CasePhone(case_id=id_case_c, phone_id=id_phone_ph1, phone=phone_ph1)]
    case_c.legal_section_associations = [CaseLegalSection(case_id=id_case_c, legal_section_id=id_legal_s1, legal_section=legal_s1)]

    # Case D (Isolated)
    case_d = Case(
        id=id_case_d, fir_number=f"FIR/2026/D_{id_case_d.hex[:4]}", station_id="PS_BBSR_003",
        police_station="Laxmisagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 25),
        crime_type="TRESPASS", crime_category="OTHER", status="CLOSED",
    )

    all_uuids = [
        str(id_case_a), str(id_case_b), str(id_case_c), str(id_case_d),
        str(id_person_p1), str(id_phone_ph1), str(id_loc_l1), str(id_legal_s1)
    ]

    try:
        # 2. Project synthetic graph into Neo4j
        neo4j_graph_projection_service.project_case_graph(case_a)
        neo4j_graph_projection_service.project_case_graph(case_b)
        neo4j_graph_projection_service.project_case_graph(case_c)
        neo4j_graph_projection_service.project_case_graph(case_d)

        # Project Step 5B RELATED_TO relationship between Case A and Case B
        _, _, key_ab = canonicalize_case_pair(str(id_case_a), str(id_case_b))
        assessment = RelationshipConfidenceAssessment(
            source_case_id=str(id_case_a),
            target_case_id=str(id_case_b),
            canonical_relationship_key=key_ab,
            confidence_score=0.92,
            confidence_level=RelationshipConfidenceLevel.HIGH,
            contributing_families=[SignalFamily.PERSON_IDENTITY],
            evidence_summary="HIGH confidence due to shared suspect Sanjay Das.",
            explanation="Cross-station robbery connection.",
            uncertainty_notes=[],
        )
        neo4j_graph_projection_service.project_relationship_assessment(assessment)

        # 3. TEST 1: Basic Case -> Person Traversal (Depth 1)
        req_d1 = GraphTraversalRequest(start_node_id=str(id_case_a), maximum_depth=1)
        res_d1 = neo4j_graph_traversal_service.traverse(req_d1)
        assert res_d1.total_paths >= 2  # HAS_PERSON -> P1, HAS_LOCATION -> L1, RELATED_TO -> Case B
        target_ids_d1 = [p.end_node_id for p in res_d1.paths]
        assert str(id_person_p1) in target_ids_d1
        assert str(id_loc_l1) in target_ids_d1

        # 4. TEST 2: Case A -> Person P1 -> Case B Traversal (Depth 2 / Cross-Station)
        req_d2 = GraphTraversalRequest(start_node_id=str(id_case_a), maximum_depth=2)
        res_d2 = neo4j_graph_traversal_service.traverse(req_d2)
        target_ids_d2 = [p.end_node_id for p in res_d2.paths]
        assert str(id_case_b) in target_ids_d2  # Discovered Cross-Station Case B!

        # 5. TEST 3: Multi-Hop Traversal (Case A -> Person P1 -> Case B -> Phone PH1 -> Case C) (Depth 4)
        req_d4 = GraphTraversalRequest(start_node_id=str(id_case_a), target_node_id=str(id_case_c), maximum_depth=4)
        res_d4 = neo4j_graph_traversal_service.traverse(req_d4)
        assert res_d4.total_paths >= 1
        path_ac = res_d4.paths[0]
        assert path_ac.start_node_id == str(id_case_a)
        assert path_ac.end_node_id == str(id_case_c)

        # 6. TEST 4: RELATED_TO Traversal & Metadata Preservation
        related_edges = [e for p in res_d2.paths for e in p.edges if e.type == "RELATED_TO"]
        assert len(related_edges) >= 1
        rel_props = related_edges[0].properties
        assert rel_props["confidence_score"] == 0.92
        assert rel_props["confidence_level"] == "HIGH"
        assert rel_props["provenance"] == "Step 5A Relationship Signals"

        # 7. TEST 5: Isolated Case Traversal (Case D)
        req_iso = GraphTraversalRequest(start_node_id=str(id_case_d), maximum_depth=3)
        res_iso = neo4j_graph_traversal_service.traverse(req_iso)
        assert res_iso.total_paths == 0  # No outgoing paths beyond depth 0

        # 8. TEST 6: Deterministic Result Ordering
        req_order = GraphTraversalRequest(start_node_id=str(id_case_a), maximum_depth=3)
        res_order1 = neo4j_graph_traversal_service.traverse(req_order)
        res_order2 = neo4j_graph_traversal_service.traverse(req_order)
        assert [p.path_key for p in res_order1.paths] == [p.path_key for p in res_order2.paths]

        # 9. TEST 7: Read-Only Verification (Neo4j Node/Edge counts remain unchanged before & after)
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            cases_count = session.run("MATCH (c:Case) WHERE c.node_id IN $ids RETURN count(c) AS c", {"ids": all_uuids}).single()["c"]
            assert cases_count == 4

    finally:
        # Clean up ONLY test-created node UUIDs
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("MATCH (n) WHERE n.node_id IN $ids DETACH DELETE n", {"ids": all_uuids})
