import datetime
import pytest
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

# Requirement 1: SQLAlchemy models import correctly
from app.models import (
    Base,
    Case,
    Person,
    CasePerson,
    PersonRole,
    Vehicle,
    CaseVehicle,
    VehicleRole,
    Phone,
    PersonPhone,
    CasePhone,
    Location,
    Evidence,
    EvidenceType,
    Chargesheet,
    InvestigationEvent,
    InvestigationEventType,
    LegalSection,
    CaseLegalSection,
)
from app.repositories import (
    CaseRepository,
    PersonRepository,
    VehicleRepository,
    EvidenceRepository,
    InvestigationEventRepository,
)
from app.graph import check_neo4j_connection, GraphNodeLabel, GraphRelationshipType
from app.main import app


def test_models_and_repositories_import():
    """Requirement 1: Verify all SQLAlchemy models, repositories, and interfaces import cleanly."""
    assert Base is not None
    assert Case is not None
    assert Person is not None
    assert Vehicle is not None
    assert Phone is not None
    assert Location is not None
    assert Evidence is not None
    assert Chargesheet is not None
    assert InvestigationEvent is not None
    assert LegalSection is not None
    assert GraphNodeLabel.CASE.value == "Case"
    assert GraphRelationshipType.INVOLVED_IN.value == "INVOLVED_IN"


def test_tables_and_foreign_keys(db_session):
    """Requirements 3 & 4: Tables created successfully and Foreign-Key relationships work."""
    location = Location(address="District Courts Compound", district="Gurugram", state="Haryana")
    db_session.add(location)
    db_session.flush()

    case = Case(
        fir_number="FIR-TEST-001",
        police_station="Sector 14 PS",
        district="Gurugram",
        state="Haryana",
        registration_date=datetime.date(2026, 1, 1),
        crime_type="BURGLARY",
        crime_category="PROPERTY_CRIME",
        location_id=location.id
    )
    db_session.add(case)
    db_session.commit()

    retrieved_case = db_session.get(Case, case.id)
    assert retrieved_case is not None
    assert retrieved_case.location.district == "Gurugram"


def test_case_person_roles(db_session):
    """Requirement 5: Case-person roles work (ACCUSED, VICTIM, SUSPECT, etc.)."""
    case = Case(
        fir_number="FIR-TEST-002",
        police_station="Central PS",
        district="Delhi",
        state="Delhi",
        registration_date=datetime.date(2026, 2, 1),
        crime_type="ASSAULT",
        crime_category="VIOLENT_CRIME"
    )
    person1 = Person(name="Suspect A", gender="MALE")
    person2 = Person(name="Victim B", gender="FEMALE")
    db_session.add_all([case, person1, person2])
    db_session.flush()

    cp1 = CasePerson(case_id=case.id, person_id=person1.id, role=PersonRole.ACCUSED, details="Identified by witness")
    cp2 = CasePerson(case_id=case.id, person_id=person2.id, role=PersonRole.VICTIM)
    db_session.add_all([cp1, cp2])
    db_session.commit()

    case_repo = CaseRepository(db_session)
    fetched_case = case_repo.get_by_fir_number("FIR-TEST-002")
    assert fetched_case is not None
    assert len(fetched_case.person_associations) == 2
    roles = {assoc.role for assoc in fetched_case.person_associations}
    assert PersonRole.ACCUSED in roles
    assert PersonRole.VICTIM in roles


def test_evidence_belongs_to_case(db_session):
    """Requirement 6: Evidence correctly belongs to a case."""
    case = Case(
        fir_number="FIR-TEST-003",
        police_station="West PS",
        district="Gurugram",
        state="Haryana",
        registration_date=datetime.date(2026, 3, 1),
        crime_type="CYBER_FRAUD",
        crime_category="FINANCIAL_CRIME"
    )
    db_session.add(case)
    db_session.flush()

    ev = Evidence(
        case_id=case.id,
        evidence_type=EvidenceType.DIGITAL,
        description="Server log file export",
        source="AWS CloudWatch"
    )
    db_session.add(ev)
    db_session.commit()

    ev_repo = EvidenceRepository(db_session)
    evidences = ev_repo.get_by_case_id(case.id)
    assert len(evidences) == 1
    assert evidences[0].evidence_type == EvidenceType.DIGITAL


def test_investigation_events_belong_to_case(db_session):
    """Requirement 7: Investigation events correctly belong to a case."""
    case = Case(
        fir_number="FIR-TEST-004",
        police_station="East PS",
        district="Noida",
        state="UP",
        registration_date=datetime.date(2026, 4, 1),
        crime_type="EXTORTION",
        crime_category="ORGANIZED_CRIME"
    )
    db_session.add(case)
    db_session.flush()

    ie1 = InvestigationEvent(
        case_id=case.id,
        event_type=InvestigationEventType.FIR_REGISTERED,
        description="FIR lodged at station",
        event_date=datetime.datetime(2026, 4, 1, 10, 0)
    )
    ie2 = InvestigationEvent(
        case_id=case.id,
        event_type=InvestigationEventType.ARREST,
        description="Suspect taken into custody",
        event_date=datetime.datetime(2026, 4, 2, 14, 30)
    )
    db_session.add_all([ie1, ie2])
    db_session.commit()

    ie_repo = InvestigationEventRepository(db_session)
    events = ie_repo.get_by_case_id(case.id)
    assert len(events) == 2
    assert events[0].event_type == InvestigationEventType.FIR_REGISTERED
    assert events[1].event_type == InvestigationEventType.ARREST


def test_legal_sections_associated_with_case(db_session):
    """Requirement 8: Legal sections can be associated with cases."""
    case = Case(
        fir_number="FIR-TEST-005",
        police_station="North PS",
        district="Delhi",
        state="Delhi",
        registration_date=datetime.date(2026, 5, 1),
        crime_type="HOMICIDE",
        crime_category="VIOLENT_CRIME"
    )
    section = LegalSection(code="BNS 103", title="Murder", law_name="BNS")
    db_session.add_all([case, section])
    db_session.flush()

    cls = CaseLegalSection(case_id=case.id, legal_section_id=section.id)
    db_session.add(cls)
    db_session.commit()

    case_repo = CaseRepository(db_session)
    fetched_case = case_repo.get_by_fir_number("FIR-TEST-005")
    assert len(fetched_case.legal_section_associations) == 1
    assert fetched_case.legal_section_associations[0].legal_section.code == "BNS 103"


def test_duplicate_fir_prevention(db_session):
    """Requirement 9: Duplicate FIR numbers are prevented."""
    case1 = Case(
        fir_number="FIR-DUP-001",
        police_station="PS A",
        district="District A",
        state="State A",
        registration_date=datetime.date(2026, 6, 1),
        crime_type="THEFT",
        crime_category="PROPERTY_CRIME"
    )
    db_session.add(case1)
    db_session.commit()

    case2 = Case(
        fir_number="FIR-DUP-001",
        police_station="PS B",
        district="District B",
        state="State B",
        registration_date=datetime.date(2026, 6, 2),
        crime_type="THEFT",
        crime_category="PROPERTY_CRIME"
    )
    db_session.add(case2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_fastapi_app_starts_and_health_endpoint():
    """Requirements 10 & 11: Application starts successfully and /health endpoint responds."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "S.I.R.I.S." in response.json()["message"]

    health_resp = client.get("/health")
    assert health_resp.status_code in [200, 503]
    assert "databases" in health_resp.json()


def test_neo4j_connection_interface():
    """Requirement 12: Verify Neo4j connection helper functions are accessible."""
    # Call connection check (returns boolean without raising syntax or import errors)
    status = check_neo4j_connection()
    assert isinstance(status, bool)
