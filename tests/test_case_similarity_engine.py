import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from app.config.settings import settings
from app.models.case import Case
from app.services.case_similarity import CaseFeatureExtractor
from app.services.case_similarity.similarity import (
    CaseSimilarityEngine,
    SimilarityLevel,
    SignalStatus,
)


def test_fixture_a_identical_cases():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/2026/001",
        "crime_type": "BURGLARY",
        "crime_category": "PROPERTY_CRIME",
        "description": "Accused cut lock using iron cutter and stole gold ornaments",
        "legal_sections": ["BNS 303", "BNS 331"],
        "locality": "Saheed Nagar, Bhubaneswar",
        "district": "Khordha",
        "incident_date": "2026-01-10",
        "hour": 22
    }
    dict2 = dict(dict1)
    dict2["id"] = "c2"
    dict2["fir_number"] = "FIR/2026/002"

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    assert res.similarity_level == SimilarityLevel.HIGH_SIMILARITY
    assert res.overall_score >= 0.85
    assert len(res.strongest_evidence) > 0


def test_fixture_r_self_comparison():
    c_dict = {
        "id": "c1",
        "fir_number": "FIR/2026/001",
        "crime_type": "BURGLARY",
        "crime_category": "PROPERTY_CRIME"
    }
    c1 = CaseFeatureExtractor.extract_from_dict(c_dict)

    res = CaseSimilarityEngine.compare_cases(c1, c1)
    assert res.similarity_level == SimilarityLevel.SELF_COMPARISON
    assert res.overall_score == 1.0


def test_fixture_b_p_unrelated_cases_low_similarity():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "crime_type": "BURGLARY",
        "crime_category": "PROPERTY_CRIME",
        "description": "Lock cut with cutter and gold stolen",
        "district": "Khordha",
        "incident_date": "2026-01-10"
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "crime_type": "CYBER_FRAUD",
        "crime_category": "CYBER_CRIME",
        "description": "OTP scam transferred money from bank account",
        "district": "Sambalpur",
        "incident_date": "2025-05-20"
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    assert res.similarity_level == SimilarityLevel.LOW_SIMILARITY
    assert res.overall_score < 0.50


def test_fixture_m_bns_vs_ipc_legal_section_separation():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "legal_sections": ["BNS 303"]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "legal_sections": ["IPC 303"]
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    sec_sig = next(s for s in res.signals if s.signal_name == "LEGAL_SECTION_SIMILARITY")
    assert sec_sig.raw_score == 0.0
    assert sec_sig.status == SignalStatus.MISMATCH


def test_fixture_f_g_h_entity_overlaps():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "persons": [{"id": "p1", "name": "Rahul Kumar"}],
        "vehicles": [{"id": "v1", "registration_number": "OD02AB1234"}],
        "phones": [{"id": "ph1", "normalized_number": "+919861105000"}]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "persons": [{"id": "p2", "name": "Rahul Kumar"}],
        "vehicles": [{"id": "v2", "registration_number": "OD02AB1234"}],
        "phones": [{"id": "ph2", "normalized_number": "+919861105000"}]
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    p_sig = next(s for s in res.signals if s.signal_name == "PERSON_OVERLAP")
    v_sig = next(s for s in res.signals if s.signal_name == "VEHICLE_OVERLAP")
    ph_sig = next(s for s in res.signals if s.signal_name == "PHONE_OVERLAP")

    assert p_sig.status == SignalStatus.MATCH
    assert v_sig.status == SignalStatus.MATCH
    assert ph_sig.status == SignalStatus.MATCH


def test_fixture_q_insufficient_data():
    dict1 = {"id": "c1", "fir_number": "FIR/1"}
    dict2 = {"id": "c2", "fir_number": "FIR/2"}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    assert res.similarity_level == SimilarityLevel.INSUFFICIENT_DATA


def test_live_supabase_case_similarity_benchmark():
    """Benchmark pairwise case similarity evaluation against real cases in Supabase PostgreSQL."""
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        cases = session.query(Case).options(
            joinedload(Case.location),
            joinedload(Case.person_associations).joinedload(Case.person_associations.property.mapper.class_.person),
            joinedload(Case.vehicle_associations).joinedload(Case.vehicle_associations.property.mapper.class_.vehicle),
            joinedload(Case.phone_associations).joinedload(Case.phone_associations.property.mapper.class_.phone),
            joinedload(Case.evidences),
            joinedload(Case.legal_section_associations).joinedload(Case.legal_section_associations.property.mapper.class_.legal_section),
        ).limit(50).all()

        total_cases = len(cases)
        assert total_cases >= 2, "Database should contain at least 2 seeded cases"

        # Extract Step 4A features
        features_list = [CaseFeatureExtractor.extract_from_model(c) for c in cases]

        # Pairwise comparison benchmark on 50 cases (1225 comparisons)
        start_time = time.time()
        results = []
        high_sim_count = 0
        mod_sim_count = 0
        low_sim_count = 0

        for i in range(len(features_list)):
            for j in range(i + 1, len(features_list)):
                res = CaseSimilarityEngine.compare_cases(features_list[i], features_list[j])
                results.append(res)
                if res.similarity_level == SimilarityLevel.HIGH_SIMILARITY:
                    high_sim_count += 1
                elif res.similarity_level == SimilarityLevel.MODERATE_SIMILARITY:
                    mod_sim_count += 1
                else:
                    low_sim_count += 1

        elapsed = time.time() - start_time
        total_comparisons = len(results)
        avg_speed_ms = (elapsed / total_comparisons) * 1000.0 if total_comparisons > 0 else 0.0

        print("\n==================================================")
        print("STEP 4B CASE SIMILARITY ENGINE BENCHMARK REPORT")
        print("==================================================")
        print(f"Total Cases Evaluated          : {total_cases}")
        print(f"Pairwise Comparisons Evaluated : {total_comparisons:,}")
        print(f"  - High Similarity Cases      : {high_sim_count:,}")
        print(f"  - Moderate Similarity Cases  : {mod_sim_count:,}")
        print(f"  - Low Similarity / Insufficient: {low_sim_count:,}")
        print(f"Total Execution Time           : {elapsed:.4f} seconds")
        print(f"Average Speed per Pairwise Comp: {avg_speed_ms:.4f} ms / pair")
        print("==================================================")

        assert total_comparisons > 0
    finally:
        session.close()
