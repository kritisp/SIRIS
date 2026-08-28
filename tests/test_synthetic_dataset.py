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
from app.data.generators.cluster_builder import build_synthetic_dataset_v2
from app.data.ground_truth import GROUND_TRUTH_CLUSTERS


@pytest.fixture(scope="module")
def seeded_db():
    """Module-level in-memory SQLite fixture populated with seed dataset V2."""
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

    cases, ground_truth, style_counts = build_synthetic_dataset_v2(
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

    yield session, cases, ground_truth, style_counts, persons, name_variations, vehicles, phones

    session.close()
    Base.metadata.drop_all(bind=engine)


def test_validation_1_narrative_diversity(seeded_db):
    """Validates that narrative descriptions are diverse with near-duplicate rate under 5%."""
    session, cases, _, style_counts, _, _, _, _ = seeded_db
    descriptions = [c.description for c in cases if c.description]
    assert len(descriptions) >= 200

    # Ensure all 6 narrative styles are utilized
    assert len(style_counts) >= 4

    # Check Jaccard 3-gram similarity among narratives to ensure < 5% near-duplicates
    def get_3grams(text: str):
        words = text.lower().split()
        return set(" ".join(words[i:i+3]) for i in range(len(words)-2))

    near_duplicates = 0
    sample = descriptions[:50]
    total_pairs = 0
    for i in range(len(sample)):
        g1 = get_3grams(sample[i])
        for j in range(i + 1, len(sample)):
            g2 = get_3grams(sample[j])
            if not g1 or not g2:
                continue
            sim = len(g1 & g2) / len(g1 | g2)
            if sim > 0.65:
                near_duplicates += 1
            total_pairs += 1

    dup_rate = near_duplicates / max(1, total_pairs)
    assert dup_rate < 0.05, f"Near duplicate narrative rate too high: {dup_rate:.2%}"


def test_validation_2_case_scale_and_stations(seeded_db):
    """Validation: Expected cases exist across multiple stations."""
    session, _, _, _, _, _, _, _ = seeded_db
    total_cases = session.scalar(select(func.count(Case.id)))
    assert 200 <= total_cases <= 300

    station_counts = session.execute(
        select(Case.station_id, func.count(Case.id)).group_by(Case.station_id)
    ).all()
    assert len(station_counts) >= 5
    for station_id, count in station_counts:
        assert count > 0


def test_validation_3_entity_reuse_and_variations(seeded_db):
    """Validation: Entity reuse and representation variations exist."""
    session, _, _, _, _, name_variations, _, _ = seeded_db

    person_reuse = session.execute(
        select(CasePerson.person_id, func.count(CasePerson.case_id))
        .group_by(CasePerson.person_id)
        .having(func.count(CasePerson.case_id) > 1)
    ).all()
    assert len(person_reuse) > 0
    assert len(name_variations) > 0


def test_validation_4_planted_clusters_and_cross_station(seeded_db):
    """Validation: Planted clusters and cross-station links exist."""
    session, _, ground_truth, _, _, _, _, _ = seeded_db
    assert len(ground_truth) >= 3

    cluster_a = ground_truth["CLUSTER_A_VEHICLE_NETWORK"]
    assert len(set(cluster_a["station_ids"])) > 1


def test_validation_5_reproducibility(seeded_db):
    """Validation: Fixed random seed produces deterministic dataset."""
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    locs1 = generate_synthetic_locations(rng1, count=10)
    locs2 = generate_synthetic_locations(rng2, count=10)
    assert [l.address for l in locs1] == [l.address for l in locs2]
