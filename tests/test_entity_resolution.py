import time
import pytest
from sqlalchemy import create_engine, text
from app.config.settings import settings
from app.services.blocking import CandidateBlockingEngine
from app.services.resolution import EntityResolver, ResolutionDecision


def test_fixture_a_obvious_same_entity():
    """Fixture A: Obvious same entity with matching name, DOB, phone, and address."""
    p1 = {"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-05-12", "phone": "+919861105000", "address": "Saheed Nagar, Bhubaneswar"}
    p2 = {"id": "p2", "name": "Rahul Kumar", "date_of_birth": "1990-05-12", "phone": "+919861105000", "address": "Saheed Nagar, Bhubaneswar"}

    res = EntityResolver.resolve_person(p1, p2)
    assert res.decision == ResolutionDecision.HIGH_CONFIDENCE_MATCH
    assert res.overall_score >= 0.80
    assert len(res.matching_signals) >= 3


def test_fixture_b_obvious_different_entity():
    """Fixture B: Obvious different entity with completely different name, DOB, and phone."""
    p1 = {"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-05-12", "phone": "+919861105000"}
    p2 = {"id": "p2", "name": "Vikram Singh", "date_of_birth": "1978-01-15", "phone": "+917008999888"}

    res = EntityResolver.resolve_person(p1, p2)
    assert res.decision == ResolutionDecision.NO_MATCH
    assert res.overall_score < 0.55


def test_fixture_c_ambiguous_incomplete_entity():
    """Fixture C: Ambiguous/incomplete entity with partial name match + same location, missing DOB and phone."""
    p1 = {"id": "p1", "name": "Rahul Kumar", "address": "Patia, Bhubaneswar"}
    p2 = {"id": "p2", "name": "Rahul K. Mohanty", "address": "Patia, Bhubaneswar"}

    res = EntityResolver.resolve_person(p1, p2)
    assert res.decision == ResolutionDecision.POSSIBLE_MATCH
    assert 0.55 <= res.overall_score < 0.80
    assert "DOB" in res.unavailable_signals
    assert "PHONE" in res.unavailable_signals


def test_fixture_d_same_common_name_conflicting_dob():
    """Fixture D: Same common name but conflicting DOBs (False Positive protection)."""
    p1 = {"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1988-05-14", "phone": "+919861105000"}
    p2 = {"id": "p2", "name": "Rahul Kumar", "date_of_birth": "1995-11-22", "phone": "+917008123456"}

    res = EntityResolver.resolve_person(p1, p2)
    assert len(res.conflicting_signals) >= 2
    assert res.decision != ResolutionDecision.HIGH_CONFIDENCE_MATCH


def test_fixture_e_similar_name_same_district_missing_dob_phone():
    """Fixture E: Similar name + same district but missing DOB/phone."""
    p1 = {"id": "p1", "name": "Rahul Kumar", "district": "Khordha"}
    p2 = {"id": "p2", "name": "R. K. Mohanty", "district": "Khordha"}

    res = EntityResolver.resolve_person(p1, p2)
    assert res.decision == ResolutionDecision.POSSIBLE_MATCH
    assert 0.55 <= res.overall_score < 0.80
    assert any(s.name == "LOCATION_MATCH" for s in res.matching_signals)


def test_fixture_f_strong_phone_match_moderate_name_similarity():
    """Fixture F: Strong phone match + moderate name similarity."""
    p1 = {"id": "p1", "name": "Rahul Kumar", "phone": "+919861105000"}
    p2 = {"id": "p2", "name": "Rahul K. Sahoo", "phone": "+919861105000"}

    res = EntityResolver.resolve_person(p1, p2)
    assert res.decision in (ResolutionDecision.HIGH_CONFIDENCE_MATCH, ResolutionDecision.POSSIBLE_MATCH)
    assert any(s.name == "PHONE_MATCH" and s.status.value == "MATCH" for s in res.matching_signals)


def test_phone_resolution():
    ph1 = {"id": "1", "normalized_number": "+919861105000"}
    ph2 = {"id": "2", "normalized_number": "09861105000"}

    res = EntityResolver.resolve_phone(ph1, ph2)
    assert res.decision == ResolutionDecision.HIGH_CONFIDENCE_MATCH
    assert res.overall_score == 1.0


def test_vehicle_resolution():
    v1 = {"id": "1", "registration_number": "OD02AB1234"}
    v2 = {"id": "2", "registration_number": "OD-02-AB-1234"}

    res = EntityResolver.resolve_vehicle(v1, v2)
    assert res.decision == ResolutionDecision.HIGH_CONFIDENCE_MATCH
    assert res.overall_score == 1.0


def test_location_resolution():
    l1 = {"id": "1", "locality": "Janpath Road, Master Canteen"}
    l2 = {"id": "2", "locality": "Janpath Rd, Master Canteen Sq"}

    res = EntityResolver.resolve_location(l1, l2)
    assert res.decision in (ResolutionDecision.HIGH_CONFIDENCE_MATCH, ResolutionDecision.POSSIBLE_MATCH)


def test_resolution_determinism():
    p1 = {"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-05-12"}
    p2 = {"id": "p2", "name": "R. Kumar", "date_of_birth": "1990-05-12"}

    res1 = EntityResolver.resolve_person(p1, p2)
    res2 = EntityResolver.resolve_person(p1, p2)
    assert res1.model_dump() == res2.model_dump()


def test_non_destructive_assertion():
    """Asserts that resolution does NOT delete, merge, or mutate inputs."""
    p1 = {"id": "p1", "name": "Rahul Kumar"}
    p2 = {"id": "p2", "name": "Rahul Kumar"}
    p1_copy = dict(p1)
    p2_copy = dict(p2)

    res = EntityResolver.resolve_person(p1, p2)
    assert p1 == p1_copy
    assert p2 == p2_copy
    assert not hasattr(res, "merged")


def test_entity_resolution_live_benchmark():
    """Benchmark Step 3C resolution against Step 3B candidate pairs on live Supabase PostgreSQL database."""
    db_engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    with db_engine.connect() as conn:
        persons = conn.execute(text("SELECT id, name, date_of_birth FROM persons")).mappings().all()
        person_dicts = [dict(p) for p in persons]
        person_lookup = {str(p["id"]): p for p in person_dicts}

    # Step 3B Candidates
    candidates = CandidateBlockingEngine.block_persons(person_dicts)
    total_candidates = len(candidates)
    assert total_candidates > 0

    # Step 3C Resolution
    start_time = time.time()
    results = EntityResolver.resolve_person_candidates(candidates, person_lookup)
    elapsed = time.time() - start_time

    decisions = {
        ResolutionDecision.HIGH_CONFIDENCE_MATCH: 0,
        ResolutionDecision.POSSIBLE_MATCH: 0,
        ResolutionDecision.NO_MATCH: 0,
    }
    for r in results:
        decisions[r.decision] += 1

    avg_time_ms = (elapsed / total_candidates) * 1000.0 if total_candidates > 0 else 0.0

    print("\n==================================================")
    print("STEP 3C ENTITY RESOLUTION BENCHMARK REPORT")
    print("==================================================")
    print(f"Total Input Candidate Pairs : {total_candidates:,}")
    print(f"Total Resolved Pairs       : {len(results):,}")
    print(f"  - High Confidence Matches : {decisions[ResolutionDecision.HIGH_CONFIDENCE_MATCH]:,}")
    print(f"  - Possible Matches        : {decisions[ResolutionDecision.POSSIBLE_MATCH]:,}")
    print(f"  - No Matches              : {decisions[ResolutionDecision.NO_MATCH]:,}")
    print(f"Total Execution Time        : {elapsed:.4f} seconds")
    print(f"Average Resolution Speed    : {avg_time_ms:.4f} ms / pair")
    print("==================================================")

    assert len(results) == total_candidates
