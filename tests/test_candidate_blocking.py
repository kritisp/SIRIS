import time
import pytest
from sqlalchemy import create_engine, text
from app.config.settings import settings
from app.services.blocking import CandidateBlockingEngine, CandidatePair


def test_person_blocking_exact_and_phonetic():
    engine = CandidateBlockingEngine()
    persons = [
        {"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-05-12"},
        {"id": "p2", "name": "rahul kumar", "date_of_birth": "1990-05-12"},
        {"id": "p3", "name": "R. Kumar", "date_of_birth": "1990-01-01"},
        {"id": "p4", "name": "Vikram Singh", "date_of_birth": "1985-08-20"},
    ]

    candidates = engine.block_persons(persons)
    assert len(candidates) > 0

    # Ensure no identity decision fields exist on CandidatePair
    for c in candidates:
        assert not hasattr(c, "same_person")
        assert not hasattr(c, "is_match")
        assert not hasattr(c, "merged")

    # Pair p1 and p2 should have EXACT_NAME signal
    p1_p2 = [c for c in candidates if (c.source_entity_id == "p1" and c.candidate_entity_id == "p2")]
    assert len(p1_p2) == 1
    assert "EXACT_NAME" in p1_p2[0].blocking_signals


def test_phone_blocking():
    engine = CandidateBlockingEngine()
    phones = [
        {"id": "ph1", "normalized_number": "+919861105000"},
        {"id": "ph2", "normalized_number": "09861105000"},
        {"id": "ph3", "normalized_number": "+919437000000"},
    ]

    candidates = engine.block_phones(phones)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.source_entity_id == "ph1" and c.candidate_entity_id == "ph2"
    assert "NORMALIZED_PHONE" in c.blocking_signals


def test_vehicle_blocking():
    engine = CandidateBlockingEngine()
    vehicles = [
        {"id": "v1", "registration_number": "OD02AB1234"},
        {"id": "v2", "registration_number": "OD-02-AB-1234"},
        {"id": "v3", "registration_number": "OD14C9999"},
    ]

    candidates = engine.block_vehicles(vehicles)
    assert len(candidates) == 1
    assert candidates[0].source_entity_id == "v1" and candidates[0].candidate_entity_id == "v2"
    assert "NORMALIZED_VEHICLE" in candidates[0].blocking_signals


def test_location_blocking():
    engine = CandidateBlockingEngine()
    locations = [
        {"id": "l1", "locality": "Janpath Road, Master Canteen", "district": "Khordha"},
        {"id": "l2", "locality": "Janpath Rd, Master Canteen Sq", "district": "Khordha"},
        {"id": "l3", "locality": "Badambadi", "district": "Cuttack"},
    ]

    candidates = engine.block_locations(locations)
    assert len(candidates) > 0


def test_candidate_determinism():
    engine = CandidateBlockingEngine()
    persons = [
        {"id": "p1", "name": "Rahul Kumar"},
        {"id": "p2", "name": "R. Kumar"},
    ]
    c1 = engine.block_persons(persons)
    c2 = engine.block_persons(persons)
    assert [x.model_dump() for x in c1] == [x.model_dump() for x in c2]


def test_blocking_performance_benchmark():
    """Benchmark blocking pair reduction against actual Supabase database records."""
    db_engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    with db_engine.connect() as conn:
        persons = conn.execute(text("SELECT id, name, date_of_birth FROM persons")).mappings().all()
        person_dicts = [dict(p) for p in persons]

    N = len(person_dicts)
    if N < 2:
        pytest.skip("Insufficient dataset size for benchmark")

    naive_pairs = (N * (N - 1)) // 2

    start_time = time.time()
    candidates = CandidateBlockingEngine.block_persons(person_dicts)
    elapsed = time.time() - start_time

    cand_count = len(candidates)
    reduction = (1.0 - (cand_count / naive_pairs)) * 100.0

    print("\n==================================================")
    print("PERSON CANDIDATE BLOCKING BENCHMARK REPORT")
    print("==================================================")
    print(f"Total Person Entities       : {N}")
    print(f"Naive Pair Comparisons O(N²): {naive_pairs:,}")
    print(f"Generated Candidate Pairs  : {cand_count:,}")
    print(f"Comparison Reduction %     : {reduction:.2f}%")
    print(f"Execution Time             : {elapsed:.4f} seconds")
    print("==================================================")

    assert reduction > 50.0, "Blocking engine should achieve significant pair reduction"
