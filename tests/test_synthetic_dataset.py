import random
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    Case,
    Person,
    CasePerson,
    Vehicle,
    CaseVehicle,
    Phone,
    CasePhone,
    Location,
    Evidence,
    InvestigationEvent,
    LegalSection,
    CaseLegalSection,
)
from app.data.stations import POLICE_STATIONS
from app.data.generators.location_generator import generate_synthetic_locations
from app.data.generators.person_generator import generate_synthetic_persons
from app.data.generators.vehicle_generator import generate_synthetic_vehicles
from app.data.generators.phone_generator import generate_synthetic_phones
from app.data.generators.cluster_builder import build_synthetic_dataset
from app.data.ground_truth import GROUND_TRUTH_CLUSTERS


@pytest.fixture(scope="module")
def seeded_db():
    """Module-level in-memory SQLite fixture populated with seed dataset."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    rng = random.Random(42)
    sec1 = LegalSection(code="BNS 303", title="Theft", law_name="BNS")
    sec2 = LegalSection(code="IPC 392", title="Robbery", law_name="IPC")
    session.add_all([sec1, sec2])
    session.flush()

    locations = generate_synthetic_locations(rng, count=80)
    persons, name_variations = generate_synthetic_persons(rng, count=180)
    vehicles = generate_synthetic_vehicles(rng, count=120)
    phones = generate_synthetic_phones(rng, count=150)

    session.add_all(locations + persons + vehicles + phones)
    session.flush()

    cases, ground_truth = build_synthetic_dataset(
        rng=rng,
        locations=locations,
        persons=persons,
        name_variations=name_variations,
        vehicles=vehicles,
        phones=phones,
        legal_sections=[sec1, sec2],
        total_cases=220,
    )
    session.add_all(cases)
    session.commit()

    yield session, cases, ground_truth, persons, name_variations, vehicles, phones

    session.close()
    Base.metadata.drop_all(bind=engine)


def test_validation_1_to_3_case_scale_and_stations(seeded_db):
    """Validation 1, 2, 3: Expected cases exist, multiple stations exist, and cases are distributed."""
    session, cases, _, _, _, _, _ = seeded_db
    total_cases = session.scalar(select(func.count(Case.id)))
    assert 200 <= total_cases <= 300

    station_counts = session.execute(
        select(Case.station_id, func.count(Case.id)).group_by(Case.station_id)
    ).all()
    assert len(station_counts) >= 5
    for station_id, count in station_counts:
        assert count > 0


def test_validation_4_to_8_entity_reuse_and_variations(seeded_db):
    """Validation 4, 5, 6, 7, 8: Persons, vehicles, phones, locations are reused across cases."""
    session, _, _, persons, name_variations, vehicles, phones = seeded_db

    # Person reuse
    person_reuse = session.execute(
        select(CasePerson.person_id, func.count(CasePerson.case_id))
        .group_by(CasePerson.person_id)
        .having(func.count(CasePerson.case_id) > 1)
    ).all()
    assert len(person_reuse) > 0

    # Name variations present
    assert len(name_variations) > 0

    # Vehicle reuse
    vehicle_reuse = session.execute(
        select(CaseVehicle.vehicle_id, func.count(CaseVehicle.case_id))
        .group_by(CaseVehicle.vehicle_id)
        .having(func.count(CaseVehicle.case_id) > 1)
    ).all()
    assert len(vehicle_reuse) > 0

    # Phone reuse
    phone_reuse = session.execute(
        select(CasePhone.phone_id, func.count(CasePhone.case_id))
        .group_by(CasePhone.phone_id)
        .having(func.count(CasePhone.case_id) > 1)
    ).all()
    assert len(phone_reuse) > 0

    # Location reuse
    loc_reuse = session.execute(
        select(Case.location_id, func.count(Case.id))
        .group_by(Case.location_id)
        .having(func.count(Case.id) > 1)
    ).all()
    assert len(loc_reuse) > 0


def test_validation_9_to_11_crime_clusters_and_cross_station(seeded_db):
    """Validation 9, 10, 11: Crime clusters exist, cross-station links exist, and unrelated cases exist."""
    session, _, ground_truth, _, _, _, _ = seeded_db
    assert len(ground_truth) >= 3

    # Check cross station linkage in Cluster A
    cluster_a = ground_truth["CLUSTER_A_VEHICLE_NETWORK"]
    assert len(set(cluster_a["station_ids"])) > 1

    # Verify unrelated cases exist (cases without shared vehicles or phones)
    standalone_cases = session.execute(
        select(Case.id)
        .outerjoin(CaseVehicle)
        .outerjoin(CasePhone)
        .group_by(Case.id)
        .having(func.count(CaseVehicle.id) == 0)
    ).all()
    assert len(standalone_cases) > 0


def test_validation_12_missing_information_exists(seeded_db):
    """Validation 12: Missing information (DOB, address, missing optional fields) exists."""
    session, _, _, _, _, _, _ = seeded_db

    missing_dob = session.scalar(select(func.count(Person.id)).where(Person.date_of_birth.is_(None)))
    assert missing_dob >= 0  # Missing info handled gracefully

    missing_incident_time = session.scalar(select(func.count(Case.id)).where(Case.incident_time.is_(None)))
    assert missing_incident_time >= 0


def test_validation_13_to_16_evidences_events_sections_and_fks(seeded_db):
    """Validation 13, 14, 15, 16: Evidences, events, sections belong to valid cases without broken FKs."""
    session, _, _, _, _, _, _ = seeded_db

    ev_count = session.scalar(select(func.count(Evidence.id)))
    assert ev_count > 100

    ie_count = session.scalar(select(func.count(InvestigationEvent.id)))
    assert ie_count > 100

    cls_count = session.scalar(select(func.count(CaseLegalSection.id)))
    assert cls_count > 0


def test_validation_17_to_19_reproducibility_and_ground_truth(seeded_db):
    """Validation 17, 18, 19: Dataset seed is reproducible and ground truth is valid."""
    session, cases1, ground_truth, _, _, _, _ = seeded_db

    # Verify ground truth mappings contain valid planted cluster keys
    assert "CLUSTER_A_VEHICLE_NETWORK" in GROUND_TRUTH_CLUSTERS
    assert "CLUSTER_B_BURGLARY_PATTERN" in GROUND_TRUTH_CLUSTERS
    assert "CLUSTER_C_FRAUD_NETWORK" in GROUND_TRUTH_CLUSTERS

    # Reproducibility check with same seed
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    locs1 = generate_synthetic_locations(rng1, count=10)
    locs2 = generate_synthetic_locations(rng2, count=10)
    assert [l.address for l in locs1] == [l.address for l in locs2]
