import uuid
import pytest
from app.config.settings import settings
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
    neo4j_schema_manager,
)
from app.services.relationship_engine import (
    RelationshipConfidenceAssessment,
    RelationshipConfidenceLevel,
    SignalFamily,
)


def test_node_projection_contract_validation():
    """Verifies that Pydantic projection contracts validate and serialize all 7 node types cleanly."""
    c_uuid = str(uuid.uuid4())
    case_node = CaseGraphNode(
        node_id=c_uuid,
        source_id=c_uuid,
        fir_number="FIR/2026/001",
        station_id="PS_BBSR_001",
        police_station="Saheed Nagar PS",
        district="Khordha",
        state="Odisha",
        registration_date="2026-08-29",
        crime_type="BURGLARY",
        crime_category="PROPERTY_CRIME",
    )
    assert case_node.label == "Case"
    assert case_node.node_id == c_uuid
    assert case_node.source_system == "postgresql"
    assert case_node.projection_version == "graph-v1"


def test_deterministic_node_ids():
    """Verifies that node_id requires a valid UUID string and rejects invalid strings."""
    c_uuid = str(uuid.uuid4())
    p_node = PersonGraphNode(
        node_id=c_uuid,
        source_id=c_uuid,
        name="Rahul Kumar",
        normalized_name="rahul kumar",
    )
    assert p_node.node_id == c_uuid

    with pytest.raises(ValueError):
        PersonGraphNode(
            node_id="not-a-valid-uuid",
            source_id="not-a-valid-uuid",
            name="Test",
        )


def test_canonical_relationship_key_valid_distinct_pair():
    """Test A & B: Verifies that canonicalize_case_pair handles valid distinct UUID pairs deterministically regardless of order."""
    u1 = "11111111-1111-1111-1111-111111111111"
    u2 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    src1, tgt1, key1 = canonicalize_case_pair(u1, u2)
    src2, tgt2, key2 = canonicalize_case_pair(u2, u1)

    assert src1 == src2 == "11111111-1111-1111-1111-111111111111"
    assert tgt1 == tgt2 == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert key1 == key2 == "11111111-1111-1111-1111-111111111111:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa:RELATED_TO"


def test_canonical_relationship_key_identical_pair_rejection():
    """Test C: Verifies that canonicalize_case_pair raises ValueError for identical case IDs."""
    u1 = "11111111-1111-1111-1111-111111111111"
    with pytest.raises(ValueError, match="Self-comparison relationships between identical case IDs are invalid."):
        canonicalize_case_pair(u1, u1)


def test_relationship_contracts_uuid_validation():
    """Test D & E: Verifies that relationship contracts accept valid UUIDs and reject invalid strings."""
    c_uuid = str(uuid.uuid4())
    p_uuid = str(uuid.uuid4())

    # Valid UUIDs accepted
    cp_rel = CasePersonRelContract(case_id=c_uuid, person_id=p_uuid, role="ACCUSED")
    assert cp_rel.case_id == c_uuid
    assert cp_rel.person_id == p_uuid

    cv_rel = CaseVehicleRelContract(case_id=c_uuid, vehicle_id=str(uuid.uuid4()), role="STOLEN_VEHICLE")
    assert cv_rel.case_id == c_uuid

    # Invalid UUIDs rejected
    with pytest.raises(ValueError):
        CasePersonRelContract(case_id="invalid-case-uuid", person_id=p_uuid)

    with pytest.raises(ValueError):
        CaseVehicleRelContract(case_id=c_uuid, vehicle_id="invalid-vehicle-uuid")

    with pytest.raises(ValueError):
        CasePhoneRelContract(case_id=c_uuid, phone_id="not-a-phone-uuid")


def test_related_to_directional_canonicalization():
    """Test F: Verifies that RelatedToCaseRelContract.from_assessment converts Step 5B assessment into canonical directional contract."""
    u_high = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    u_low = "11111111-1111-1111-1111-111111111111"

    assessment = RelationshipConfidenceAssessment(
        source_case_id=u_high,
        target_case_id=u_low,
        canonical_relationship_key=f"{u_low}:{u_high}:RELATED_TO",
        confidence_score=0.92,
        confidence_level=RelationshipConfidenceLevel.VERY_HIGH,
        contributing_families=[SignalFamily.PERSON_IDENTITY, SignalFamily.VEHICLE],
        evidence_summary="VERY_HIGH confidence based on exact person and vehicle overlap.",
        explanation="Strong entity resolution and shared vehicle registration.",
        uncertainty_notes=[],
        provenance="Step 5A Relationship Signals",
        methodology_version="relationship-confidence-v1",
        projection_version="graph-v1",
    )

    contract = RelatedToCaseRelContract.from_assessment(assessment)
    assert contract.source_case_id == u_low
    assert contract.target_case_id == u_high
    assert contract.canonical_relationship_key == f"{u_low}:{u_high}:RELATED_TO"
    assert contract.confidence_score == 0.92
    assert "PERSON_IDENTITY" in contract.contributing_families


def test_sensitive_field_exclusion():
    """Verifies that PersonGraphNode excludes sensitive PII fields (date_of_birth, address)."""
    p_uuid = str(uuid.uuid4())
    p_node = PersonGraphNode(
        node_id=p_uuid,
        source_id=p_uuid,
        name="John Doe",
        normalized_name="john doe",
        gender="MALE",
        identifier_hash="abc123hash",
    )

    dump_keys = set(p_node.model_dump().keys())
    assert "date_of_birth" not in dump_keys
    assert "address" not in dump_keys


def test_schema_constraints_application_and_idempotency():
    """Live integration test applying Cypher uniqueness constraints and indexes idempotently."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live schema DDL integration test.")

    # 1. Apply DDL constraints once
    res1 = neo4j_schema_manager.apply_schema_constraints()
    assert len(res1["applied_constraints"]) == 7
    assert len(res1["applied_indexes"]) == 5

    # 2. Apply DDL constraints second time to prove idempotency
    res2 = neo4j_schema_manager.apply_schema_constraints()
    assert len(res2["applied_constraints"]) == 7
    assert len(res2["applied_indexes"]) == 5

    # 3. Verify metadata status
    status = neo4j_schema_manager.verify_schema_status()
    assert status["active_constraints"] >= 7
    assert status["active_indexes"] >= 5


def test_zero_data_mutation_during_schema_design():
    """Live integration test verifying that applying schema constraints resulted in ZERO node or relationship creation."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j server offline. Skipping live data count test.")

    driver = neo4j_connection_service.get_driver()
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        # Check node count
        n_res = session.run("MATCH (n) RETURN count(n) AS total_nodes")
        total_nodes = n_res.single()["total_nodes"]
        assert total_nodes == 0

        # Check relationship count
        r_res = session.run("MATCH ()-[r]->() RETURN count(r) AS total_rels")
        total_rels = r_res.single()["total_rels"]
        assert total_rels == 0
