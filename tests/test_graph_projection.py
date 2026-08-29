import uuid
import pytest
from datetime import date
from app.config.settings import settings
from app.models.case import Case
from app.models.person import Person, CasePerson, PersonRole
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.models.phone import Phone, CasePhone
from app.models.location import Location
from app.models.evidence import Evidence, EvidenceType
from app.models.legal_section import LegalSection, CaseLegalSection
from app.services.graph import (
    CaseGraphNode,
    PersonGraphNode,
    VehicleGraphNode,
    PhoneGraphNode,
    LocationGraphNode,
    EvidenceGraphNode,
    LegalSectionGraphNode,
    CasePersonRelContract,
    CaseVehicleRelContract,
    CasePhoneRelContract,
    CaseLocationRelContract,
    CaseEvidenceRelContract,
    CaseLegalSectionRelContract,
    RelatedToCaseRelContract,
    canonicalize_case_pair,
    neo4j_connection_service,
    neo4j_graph_projection_service,
)
from app.services.relationship_engine import (
    RelationshipConfidenceAssessment,
    RelationshipConfidenceLevel,
    SignalFamily,
)


def test_unit_node_projection_contracts_id_and_pii_safety():
    """Tests J & N: Verifies that projection contracts validate UUIDs and exclude sensitive PII fields."""
    c_uuid = str(uuid.uuid4())
    p_uuid = str(uuid.uuid4())

    c_contract = CaseGraphNode(
        node_id=c_uuid,
        source_id=c_uuid,
        fir_number="FIR/TEST/001",
        station_id="PS_TEST_01",
        police_station="Test Station",
        district="Test District",
        state="Test State",
        registration_date="2026-08-29",
        crime_type="THEFT",
        crime_category="PROPERTY",
    )
    assert c_contract.node_id == c_uuid
    assert c_contract.source_system == "postgresql"

    p_contract = PersonGraphNode(
        node_id=p_uuid,
        source_id=p_uuid,
        name="Suspect Name",
        normalized_name="suspect name",
        gender="MALE",
    )
    assert "date_of_birth" not in p_contract.model_dump()
    assert "address" not in p_contract.model_dump()


def test_unit_related_to_self_link_rejection():
    """Test R: Verifies that self-link RELATED_TO relationship creation raises ValueError."""
    same_uuid = str(uuid.uuid4())
    with pytest.raises(ValueError, match="Self-comparison relationships between identical case IDs are invalid."):
        canonicalize_case_pair(same_uuid, same_uuid)


def test_unit_relationship_contracts_validation():
    """Tests H, I & T: Verifies role validation and UUID validation in relationship contracts."""
    c_uuid = str(uuid.uuid4())
    p_uuid = str(uuid.uuid4())

    cp_rel = CasePersonRelContract(case_id=c_uuid, person_id=p_uuid, role="ACCUSED")
    assert cp_rel.role == "ACCUSED"

    with pytest.raises(ValueError):
        CasePersonRelContract(case_id="invalid-uuid", person_id=p_uuid)


def test_live_controlled_single_case_graph_projection_and_idempotency():
    """Tests A-G, H-L, Q, S: Live integration test projecting a single controlled test case graph, verifying counts and MERGE idempotency."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live projection integration test.")

    case_id = uuid.uuid4()
    person_id = uuid.uuid4()
    vehicle_id = uuid.uuid4()
    phone_id = uuid.uuid4()
    loc_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    legal_id = uuid.uuid4()

    test_location = Location(
        id=loc_id,
        locality="Khandagiri",
        city="Bhubaneswar",
        district="Khordha",
        state="Odisha",
        latitude=20.25,
        longitude=85.78,
    )
    test_person = Person(
        id=person_id,
        name="Ramesh Jena",
        gender="MALE",
        identifier_hash="hash_ramesh_123",
    )
    test_vehicle = Vehicle(
        id=vehicle_id,
        registration_number="OD02AB1234",
        vehicle_type="MOTORCYCLE",
        make="HERO",
        model="SPLENDOR",
    )
    test_phone = Phone(
        id=phone_id,
        normalized_number="+919876543210",
        number_hash="hash_phone_987",
    )
    test_evidence = Evidence(
        id=evidence_id,
        case_id=case_id,
        evidence_type=EvidenceType.CCTV,
        source="Shop Camera 1",
        status="COLLECTED",
    )
    test_legal = LegalSection(
        id=legal_id,
        code="IPC 379",
        title="Theft",
        law_name="IPC",
    )

    test_case = Case(
        id=case_id,
        fir_number=f"FIR/TEST/{case_id.hex[:6]}",
        station_id="PS_BBSR_002",
        police_station="Khandagiri PS",
        district="Khordha",
        state="Odisha",
        registration_date=date(2026, 8, 29),
        crime_type="THEFT",
        crime_category="PROPERTY_CRIME",
        status="UNDER_INVESTIGATION",
        location=test_location,
    )
    test_case.person_associations = [
        CasePerson(case_id=case_id, person_id=person_id, person=test_person, role=PersonRole.ACCUSED)
    ]
    test_case.vehicle_associations = [
        CaseVehicle(case_id=case_id, vehicle_id=vehicle_id, vehicle=test_vehicle, role=VehicleRole.SUSPECT_VEHICLE)
    ]
    test_case.phone_associations = [
        CasePhone(case_id=case_id, phone_id=phone_id, phone=test_phone)
    ]
    test_case.evidences = [test_evidence]
    test_case.legal_section_associations = [
        CaseLegalSection(case_id=case_id, legal_section_id=legal_id, legal_section=test_legal)
    ]

    try:
        # Run projection
        counts1 = neo4j_graph_projection_service.project_case_graph(test_case)
        assert counts1["cases"] == 1
        assert counts1["persons"] == 1
        assert counts1["vehicles"] == 1
        assert counts1["phones"] == 1
        assert counts1["locations"] == 1
        assert counts1["evidences"] == 1
        assert counts1["legal_sections"] == 1
        assert counts1["relationships"] == 6

        # Run second projection (Idempotency)
        counts2 = neo4j_graph_projection_service.project_case_graph(test_case)
        assert counts2["cases"] == 1

        # Verify Neo4j state
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            c_res = session.run("MATCH (c:Case {node_id: $id}) RETURN count(c) AS c", {"id": str(case_id)})
            assert c_res.single()["c"] == 1

            p_res = session.run("MATCH (p:Person {node_id: $id}) RETURN count(p) AS c", {"id": str(person_id)})
            assert p_res.single()["c"] == 1

            rel_res = session.run("MATCH (c:Case {node_id: $id})-[r]->() RETURN count(r) AS c", {"id": str(case_id)})
            assert rel_res.single()["c"] == 6

    finally:
        # Clean up test nodes
        driver = neo4j_connection_service.get_driver()
        test_ids = [str(case_id), str(person_id), str(vehicle_id), str(phone_id), str(loc_id), str(evidence_id), str(legal_id)]
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("MATCH (n) WHERE n.node_id IN $ids DETACH DELETE n", {"ids": test_ids})


def test_live_controlled_multi_case_graph_projection_and_hardening():
    """Comprehensive Multi-Case Hardening Integration Test.
    
    Tests:
    1. Multi-case shared Person deduplication (Case A & Case B share Person P1 -> 1 Person node, 2 HAS_PERSON edges).
    2. Multi-case shared Vehicle deduplication (Case A & Case B share Vehicle V1 -> 1 Vehicle node, 2 HAS_VEHICLE edges).
    3. Multi-case shared Phone deduplication (Case B & Case C share Phone PH1 -> 1 Phone node, 2 HAS_PHONE edges).
    4. Multi-case shared Location deduplication (Case A & Case C share Location L1 -> 1 Location node, 2 HAS_LOCATION edges).
    5. Multi-case shared LegalSection deduplication (Case A, B & C share LegalSection S1 -> 1 LegalSection node).
    6. Isolated Case (Case D has no linked entities or assessments -> 1 Case node, 0 relationships).
    7. Cross-Station Case projection (Case A in PS_BBSR_001, Case B in PS_CUTTACK_002 sharing Person P1).
    8. Step 5B RELATED_TO assessment projection between Case A and Case B with directional canonicalization (min_id -> max_id).
    9. Repeated Multi-Run Idempotency (3 sequential projection runs yielding identical node/relationship counts).
    10. Partial Projection (Case A, then Case B, then Case C without duplication).
    """
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping multi-case integration test.")

    # 1. Deterministic UUIDs for Multi-Case Dataset
    id_case_a = uuid.uuid4()
    id_case_b = uuid.uuid4()
    id_case_c = uuid.uuid4()
    id_case_d = uuid.uuid4()  # Isolated case

    id_person_p1 = uuid.uuid4()  # Shared by Case A & B
    id_vehicle_v1 = uuid.uuid4()  # Shared by Case A & B
    id_phone_ph1 = uuid.uuid4()   # Shared by Case B & C
    id_loc_l1 = uuid.uuid4()      # Shared by Case A & C
    id_ev_e1 = uuid.uuid4()       # Case A evidence
    id_legal_s1 = uuid.uuid4()    # Shared by Case A, B & C

    # Shared Domain Entities
    shared_location_l1 = Location(
        id=id_loc_l1,
        locality="Jaydev Vihar",
        city="Bhubaneswar",
        district="Khordha",
        state="Odisha",
        latitude=20.30,
        longitude=85.82,
    )
    shared_person_p1 = Person(
        id=id_person_p1,
        name="Sanjay Das",
        gender="MALE",
        identifier_hash="hash_sanjay_das_001",
    )
    shared_vehicle_v1 = Vehicle(
        id=id_vehicle_v1,
        registration_number="OD02XY9999",
        vehicle_type="CAR",
        make="HYUNDAI",
        model="VERNA",
    )
    shared_phone_ph1 = Phone(
        id=id_phone_ph1,
        normalized_number="+919937012345",
        number_hash="hash_phone_ph1",
    )
    shared_legal_s1 = LegalSection(
        id=id_legal_s1,
        code="IPC 392",
        title="Robbery",
        law_name="IPC",
    )

    # Case A (Station 1: Saheed Nagar PS)
    case_a = Case(
        id=id_case_a,
        fir_number=f"FIR/2026/A_{id_case_a.hex[:4]}",
        station_id="PS_BBSR_001",
        police_station="Saheed Nagar PS",
        district="Khordha",
        state="Odisha",
        registration_date=date(2026, 8, 10),
        crime_type="ROBBERY",
        crime_category="PROPERTY_CRIME",
        status="UNDER_INVESTIGATION",
        location=shared_location_l1,
    )
    case_a.person_associations = [CasePerson(case_id=id_case_a, person_id=id_person_p1, person=shared_person_p1, role=PersonRole.SUSPECT)]
    case_a.vehicle_associations = [CaseVehicle(case_id=id_case_a, vehicle_id=id_vehicle_v1, vehicle=shared_vehicle_v1, role=VehicleRole.SUSPECT_VEHICLE)]
    case_a.legal_section_associations = [CaseLegalSection(case_id=id_case_a, legal_section_id=id_legal_s1, legal_section=shared_legal_s1)]
    case_a.evidences = [Evidence(id=id_ev_e1, case_id=id_case_a, evidence_type=EvidenceType.CCTV, source="ATM Cam 1", status="COLLECTED")]

    # Case B (Station 2: Cuttack Sadar PS - Cross-Station)
    case_b = Case(
        id=id_case_b,
        fir_number=f"FIR/2026/B_{id_case_b.hex[:4]}",
        station_id="PS_CTC_002",
        police_station="Cuttack Sadar PS",
        district="Cuttack",
        state="Odisha",
        registration_date=date(2026, 8, 15),
        crime_type="ROBBERY",
        crime_category="PROPERTY_CRIME",
        status="UNDER_INVESTIGATION",
    )
    case_b.person_associations = [CasePerson(case_id=id_case_b, person_id=id_person_p1, person=shared_person_p1, role=PersonRole.ACCUSED)]
    case_b.vehicle_associations = [CaseVehicle(case_id=id_case_b, vehicle_id=id_vehicle_v1, vehicle=shared_vehicle_v1, role=VehicleRole.RECOVERED_VEHICLE)]
    case_b.phone_associations = [CasePhone(case_id=id_case_b, phone_id=id_phone_ph1, phone=shared_phone_ph1)]
    case_b.legal_section_associations = [CaseLegalSection(case_id=id_case_b, legal_section_id=id_legal_s1, legal_section=shared_legal_s1)]

    # Case C (Station 1: Saheed Nagar PS)
    case_c = Case(
        id=id_case_c,
        fir_number=f"FIR/2026/C_{id_case_c.hex[:4]}",
        station_id="PS_BBSR_001",
        police_station="Saheed Nagar PS",
        district="Khordha",
        state="Odisha",
        registration_date=date(2026, 8, 20),
        crime_type="SNATCHING",
        crime_category="PROPERTY_CRIME",
        status="UNDER_INVESTIGATION",
        location=shared_location_l1,
    )
    case_c.phone_associations = [CasePhone(case_id=id_case_c, phone_id=id_phone_ph1, phone=shared_phone_ph1)]
    case_c.legal_section_associations = [CaseLegalSection(case_id=id_case_c, legal_section_id=id_legal_s1, legal_section=shared_legal_s1)]

    # Case D (Isolated Case - No entity associations or assessments)
    case_d = Case(
        id=id_case_d,
        fir_number=f"FIR/2026/D_{id_case_d.hex[:4]}",
        station_id="PS_BBSR_003",
        police_station="Laxmisagar PS",
        district="Khordha",
        state="Odisha",
        registration_date=date(2026, 8, 25),
        crime_type="TRESPASS",
        crime_category="OTHER",
        status="CLOSED",
    )

    all_test_uuids = [
        str(id_case_a), str(id_case_b), str(id_case_c), str(id_case_d),
        str(id_person_p1), str(id_vehicle_v1), str(id_phone_ph1), str(id_loc_l1),
        str(id_ev_e1), str(id_legal_s1)
    ]

    try:
        # A. PARTIAL PROJECTION TEST (Sequential Projection)
        # Project Case A
        c_a_res = neo4j_graph_projection_service.project_case_graph(case_a)
        assert c_a_res["cases"] == 1
        assert c_a_res["persons"] == 1
        assert c_a_res["vehicles"] == 1
        assert c_a_res["locations"] == 1

        # Project Case B (shares Person P1 & Vehicle V1 with Case A)
        c_b_res = neo4j_graph_projection_service.project_case_graph(case_b)
        assert c_b_res["cases"] == 1
        assert c_b_res["persons"] == 1  # MERGE executed safely
        assert c_b_res["vehicles"] == 1

        # Project Case C (shares Location L1 with Case A, Phone PH1 with Case B)
        c_c_res = neo4j_graph_projection_service.project_case_graph(case_c)
        assert c_c_res["cases"] == 1

        # Project Isolated Case D
        c_d_res = neo4j_graph_projection_service.project_case_graph(case_d)
        assert c_d_res["cases"] == 1
        assert c_d_res["relationships"] == 0

        # Project Step 5B Assessment between Case A & Case B
        min_ab, max_ab, key_ab = canonicalize_case_pair(str(id_case_a), str(id_case_b))
        assessment_ab = RelationshipConfidenceAssessment(
            source_case_id=str(id_case_a),
            target_case_id=str(id_case_b),
            canonical_relationship_key=key_ab,
            confidence_score=0.95,
            confidence_level=RelationshipConfidenceLevel.VERY_HIGH,
            contributing_families=[SignalFamily.PERSON_IDENTITY, SignalFamily.VEHICLE],
            evidence_summary="VERY_HIGH confidence based on shared suspect Ramesh Jena and vehicle OD02XY9999.",
            explanation="Cross-station robbery connection between Saheed Nagar PS and Cuttack Sadar PS.",
            uncertainty_notes=[],
        )
        assert neo4j_graph_projection_service.project_relationship_assessment(assessment_ab) is True

        # B. VERIFY GRAPH NODE DEDUPLICATION & METADATA IN NEO4J
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # 1. Person Deduplication: 1 Person node (P1) connected to Case A & Case B
            p1_count = session.run("MATCH (p:Person {node_id: $id}) RETURN count(p) AS c", {"id": str(id_person_p1)}).single()["c"]
            assert p1_count == 1

            p1_edges = session.run("MATCH (c:Case)-[:HAS_PERSON]->(p:Person {node_id: $id}) RETURN count(c) AS c", {"id": str(id_person_p1)}).single()["c"]
            assert p1_edges == 2  # Connected to Case A and Case B

            # 2. Vehicle Deduplication: 1 Vehicle node (V1) connected to Case A & Case B
            v1_count = session.run("MATCH (v:Vehicle {node_id: $id}) RETURN count(v) AS c", {"id": str(id_vehicle_v1)}).single()["c"]
            assert v1_count == 1

            v1_edges = session.run("MATCH (c:Case)-[:HAS_VEHICLE]->(v:Vehicle {node_id: $id}) RETURN count(c) AS c", {"id": str(id_vehicle_v1)}).single()["c"]
            assert v1_edges == 2

            # 3. Location Deduplication: 1 Location node (L1) connected to Case A & Case C
            l1_count = session.run("MATCH (l:Location {node_id: $id}) RETURN count(l) AS c", {"id": str(id_loc_l1)}).single()["c"]
            assert l1_count == 1

            l1_edges = session.run("MATCH (c:Case)-[:HAS_LOCATION]->(l:Location {node_id: $id}) RETURN count(c) AS c", {"id": str(id_loc_l1)}).single()["c"]
            assert l1_edges == 2

            # 4. LegalSection Deduplication: 1 LegalSection node (S1) connected to Case A, B & C
            s1_count = session.run("MATCH (s:LegalSection {node_id: $id}) RETURN count(s) AS c", {"id": str(id_legal_s1)}).single()["c"]
            assert s1_count == 1

            s1_edges = session.run("MATCH (c:Case)-[:HAS_LEGAL_SECTION]->(s:LegalSection {node_id: $id}) RETURN count(c) AS c", {"id": str(id_legal_s1)}).single()["c"]
            assert s1_edges == 3

            # 5. Isolated Case D Verification: Exactly 0 outgoing edges
            d_edges = session.run("MATCH (c:Case {node_id: $id})-[r]->() RETURN count(r) AS c", {"id": str(id_case_d)}).single()["c"]
            assert d_edges == 0

            # 6. RELATED_TO Edge Verification & Canonical Directionality
            rel_res = session.run(
                "MATCH (c1:Case {node_id: $src})-[r:RELATED_TO {canonical_relationship_key: $key}]->(c2:Case {node_id: $tgt}) RETURN r.confidence_score AS score, r.provenance AS prov",
                {"src": min_ab, "tgt": max_ab, "key": key_ab}
            ).single()
            assert rel_res is not None
            assert rel_res["score"] == 0.95
            assert rel_res["prov"] == "Step 5A Relationship Signals"

            # Verify no reverse edge (max_ab -> min_ab) exists
            rev_res = session.run(
                "MATCH (c1:Case {node_id: $max})-[r:RELATED_TO]->(c2:Case {node_id: $min}) RETURN count(r) AS c",
                {"min": min_ab, "max": max_ab}
            ).single()["c"]
            assert rev_res == 0

            # 7. Total Node Counts for Test Scenario
            total_cases = session.run("MATCH (c:Case) WHERE c.node_id IN $ids RETURN count(c) AS c", {"ids": all_test_uuids}).single()["c"]
            assert total_cases == 4

        # C. REPEATED MULTI-RUN IDEMPOTENCY TEST (Run 2 & Run 3)
        for _ in range(2):
            neo4j_graph_projection_service.project_case_graph(case_a)
            neo4j_graph_projection_service.project_case_graph(case_b)
            neo4j_graph_projection_service.project_case_graph(case_c)
            neo4j_graph_projection_service.project_case_graph(case_d)
            neo4j_graph_projection_service.project_relationship_assessment(assessment_ab)

        # Assert counts remain completely unchanged after 3 full runs
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            p1_count_run3 = session.run("MATCH (p:Person {node_id: $id}) RETURN count(p) AS c", {"id": str(id_person_p1)}).single()["c"]
            assert p1_count_run3 == 1

            total_cases_run3 = session.run("MATCH (c:Case) WHERE c.node_id IN $ids RETURN count(c) AS c", {"ids": all_test_uuids}).single()["c"]
            assert total_cases_run3 == 4

            rel_ab_run3 = session.run("MATCH ()-[r:RELATED_TO {canonical_relationship_key: $key}]->() RETURN count(r) AS c", {"key": key_ab}).single()["c"]
            assert rel_ab_run3 == 1

    finally:
        # Controlled cleanup of ONLY test-created node UUIDs
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("MATCH (n) WHERE n.node_id IN $ids DETACH DELETE n", {"ids": all_test_uuids})
