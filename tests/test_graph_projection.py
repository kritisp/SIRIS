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


def test_live_controlled_graph_projection_and_idempotency():
    """Tests A-G, H-L, Q, S: Live integration test projecting a controlled test case graph, verifying counts and MERGE idempotency."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live projection integration test.")

    # 1. Create a controlled test Case graph object structure (without saving to PostgreSQL)
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
        # 2. Run initial projection
        counts1 = neo4j_graph_projection_service.project_case_graph(test_case)
        assert counts1["cases"] == 1
        assert counts1["persons"] == 1
        assert counts1["vehicles"] == 1
        assert counts1["phones"] == 1
        assert counts1["locations"] == 1
        assert counts1["evidences"] == 1
        assert counts1["legal_sections"] == 1
        assert counts1["relationships"] == 6

        # 3. Run second projection (MERGE Idempotency check)
        counts2 = neo4j_graph_projection_service.project_case_graph(test_case)
        assert counts2["cases"] == 1

        # 4. Verify graph state in Neo4j
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            c_res = session.run("MATCH (c:Case {node_id: $id}) RETURN count(c) AS c", {"id": str(case_id)})
            assert c_res.single()["c"] == 1

            p_res = session.run("MATCH (p:Person {node_id: $id}) RETURN count(p) AS c", {"id": str(person_id)})
            assert p_res.single()["c"] == 1

            rel_res = session.run("MATCH (c:Case {node_id: $id})-[r]->() RETURN count(r) AS c", {"id": str(case_id)})
            assert rel_res.single()["c"] == 6

        # 5. Project Step 5B Assessment (RELATED_TO relationship)
        other_case_id = uuid.uuid4()
        other_case = Case(
            id=other_case_id,
            fir_number=f"FIR/TEST/{other_case_id.hex[:6]}",
            station_id="PS_BBSR_002",
            police_station="Khandagiri PS",
            district="Khordha",
            state="Odisha",
            registration_date=date(2026, 8, 29),
            crime_type="THEFT",
            crime_category="PROPERTY_CRIME",
            status="UNDER_INVESTIGATION",
        )
        neo4j_graph_projection_service.project_case_graph(other_case)

        assessment = RelationshipConfidenceAssessment(
            source_case_id=str(case_id),
            target_case_id=str(other_case_id),
            canonical_relationship_key=f"{min(str(case_id), str(other_case_id))}:{max(str(case_id), str(other_case_id))}:RELATED_TO",
            confidence_score=0.88,
            confidence_level=RelationshipConfidenceLevel.HIGH,
            contributing_families=[SignalFamily.VEHICLE],
            evidence_summary="HIGH confidence due to shared suspect vehicle.",
            explanation="Shared vehicle OD02AB1234 between both theft cases.",
            uncertainty_notes=[],
        )
        assert neo4j_graph_projection_service.project_relationship_assessment(assessment) is True

        # Re-run assessment projection (Idempotency)
        assert neo4j_graph_projection_service.project_relationship_assessment(assessment) is True

    finally:
        # Clean up ONLY test-created nodes
        driver = neo4j_connection_service.get_driver()
        test_ids = [str(case_id), str(person_id), str(vehicle_id), str(phone_id), str(loc_id), str(evidence_id), str(legal_id), str(other_case_id)]
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("MATCH (n) WHERE n.node_id IN $ids DETACH DELETE n", {"ids": test_ids})
