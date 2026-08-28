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
    assert res.overall_score >= 0.75
    assert len(res.strongest_evidence) > 0


def test_fixture_b_same_name_different_persons_name_only():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "persons": [{"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-01-01"}]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "persons": [{"id": "p2", "name": "Rahul Kumar", "date_of_birth": "1985-05-15"}]  # Conflicting DOB
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    p_sig = next(s for s in res.signals if s.signal_name == "PERSON_OVERLAP")
    assert p_sig.status == SignalStatus.PARTIAL
    assert p_sig.raw_score == 0.35
    assert "unverified identity" in p_sig.evidence[0].lower()


def test_fixture_c_same_person_confirmed_step3c():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "persons": [{"id": "p1", "name": "Rahul Kumar alias Raju", "date_of_birth": "1990-01-01"}]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "persons": [{"id": "p2", "name": "Rahul Kumar", "date_of_birth": "1990-01-01"}]  # Matching name + DOB
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    p_sig = next(s for s in res.signals if s.signal_name == "PERSON_OVERLAP")
    assert p_sig.status == SignalStatus.MATCH
    assert p_sig.raw_score == 1.0
    assert "confirmed entity match" in p_sig.evidence[0]


def test_fixture_d_phonetic_only_match():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "persons": [{"id": "p1", "name": "Suresh", "date_of_birth": "1992-01-01"}]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "persons": [{"id": "p2", "name": "Suraj", "date_of_birth": "1980-03-03"}]
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    p_sig = next(s for s in res.signals if s.signal_name == "PERSON_OVERLAP")
    assert p_sig.raw_score == 0.40
    assert p_sig.status == SignalStatus.PARTIAL


def test_fixture_e_unrelated_persons():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "persons": [{"id": "p1", "name": "Rahul Kumar"}]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "persons": [{"id": "p2", "name": "Jagannath Mohanty"}]
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    p_sig = next(s for s in res.signals if s.signal_name == "PERSON_OVERLAP")
    assert p_sig.raw_score == 0.0
    assert p_sig.status == SignalStatus.MISMATCH


def test_fixture_f_g_h_i_j_mo_similarity():
    dict_dedicated1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "modus_operandi": "Entered via rear skylight using glass cutter"
    }
    dict_dedicated2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "modus_operandi": "Entered via rear skylight using glass cutter"
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict_dedicated1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict_dedicated2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    mo_sig = next(s for s in res.signals if s.signal_name == "MO_TEXT_SIMILARITY")
    assert mo_sig.status == SignalStatus.MATCH
    assert mo_sig.raw_score >= 0.85
    assert "both cases have dedicated mo" in mo_sig.explanation.lower()

    # Missing MO test
    dict_missing = {"id": "c3", "fir_number": "FIR/3"}
    c3 = CaseFeatureExtractor.extract_from_dict(dict_missing)
    res_miss = CaseSimilarityEngine.compare_cases(c1, c3)
    mo_miss = next(s for s in res_miss.signals if s.signal_name == "MO_TEXT_SIMILARITY")
    assert mo_miss.status == SignalStatus.UNAVAILABLE


def test_fixture_k_l_m_n_o_geographic_similarity():
    dict_exact1 = {"id": "c1", "fir_number": "FIR/1", "latitude": 20.2961, "longitude": 85.8245}
    dict_exact2 = {"id": "c2", "fir_number": "FIR/2", "latitude": 20.2965, "longitude": 85.8249}  # ~50 meters

    c1 = CaseFeatureExtractor.extract_from_dict(dict_exact1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict_exact2)
    res = CaseSimilarityEngine.compare_cases(c1, c2)
    geo_sig = next(s for s in res.signals if s.signal_name == "GEOGRAPHIC_SIMILARITY")
    assert geo_sig.status == SignalStatus.MATCH
    assert geo_sig.raw_score >= 0.95

    # Invalid coordinates test
    dict_invalid = {"id": "c3", "fir_number": "FIR/3", "latitude": 999.0, "longitude": -500.0}
    c3 = CaseFeatureExtractor.extract_from_dict(dict_invalid)
    res_inv = CaseSimilarityEngine.compare_cases(c1, c3)
    geo_inv = next(s for s in res_inv.signals if s.signal_name == "GEOGRAPHIC_SIMILARITY")
    assert geo_inv.status == SignalStatus.UNAVAILABLE

    # District only test
    dict_dist1 = {"id": "c4", "fir_number": "FIR/4", "district": "Khordha"}
    dict_dist2 = {"id": "c5", "fir_number": "FIR/5", "district": "Khordha"}
    c4 = CaseFeatureExtractor.extract_from_dict(dict_dist1)
    c5 = CaseFeatureExtractor.extract_from_dict(dict_dist2)
    res_dist = CaseSimilarityEngine.compare_cases(c4, c5)
    geo_dist = next(s for s in res_dist.signals if s.signal_name == "GEOGRAPHIC_SIMILARITY")
    assert geo_dist.raw_score == 0.40
    assert geo_dist.status == SignalStatus.PARTIAL


def test_fixture_p_q_r_legal_section_similarity():
    dict1 = {"id": "c1", "fir_number": "FIR/1", "legal_sections": ["BNS 303"]}
    dict2 = {"id": "c2", "fir_number": "FIR/2", "legal_sections": ["IPC 303"]}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    sec_sig = next(s for s in res.signals if s.signal_name == "LEGAL_SECTION_SIMILARITY")
    assert sec_sig.raw_score == 0.0
    assert sec_sig.status == SignalStatus.MISMATCH


def test_fixture_s_t_u_temporal_similarity():
    dict1 = {"id": "c1", "fir_number": "FIR/1", "incident_date": "2026-01-10", "hour": 22}
    dict2 = {"id": "c2", "fir_number": "FIR/2", "incident_date": "2026-01-10", "hour": 22}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    t_sig = next(s for s in res.signals if s.signal_name == "TEMPORAL_SIMILARITY")
    assert t_sig.status == SignalStatus.MATCH
    assert t_sig.raw_score == 1.0


def test_fixture_v_completely_incomplete_cases():
    dict1 = {"id": "c1", "fir_number": "FIR/1"}
    dict2 = {"id": "c2", "fir_number": "FIR/2"}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = CaseSimilarityEngine.compare_cases(c1, c2)
    assert res.similarity_level == SimilarityLevel.INSUFFICIENT_DATA


def test_fixture_w_self_comparison():
    c_dict = {"id": "c1", "fir_number": "FIR/1", "crime_type": "BURGLARY"}
    c1 = CaseFeatureExtractor.extract_from_dict(c_dict)

    res = CaseSimilarityEngine.compare_cases(c1, c1)
    assert res.similarity_level == SimilarityLevel.SELF_COMPARISON
    assert res.overall_score == 1.0


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
        insufficient_count = 0

        for i in range(len(features_list)):
            for j in range(i + 1, len(features_list)):
                res = CaseSimilarityEngine.compare_cases(features_list[i], features_list[j])
                results.append(res)
                if res.similarity_level == SimilarityLevel.HIGH_SIMILARITY:
                    high_sim_count += 1
                elif res.similarity_level == SimilarityLevel.MODERATE_SIMILARITY:
                    mod_sim_count += 1
                elif res.similarity_level == SimilarityLevel.LOW_SIMILARITY:
                    low_sim_count += 1
                else:
                    insufficient_count += 1

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
        print(f"  - Low Similarity Cases       : {low_sim_count:,}")
        print(f"  - Insufficient Data Cases    : {insufficient_count:,}")
        print(f"Total Execution Time           : {elapsed:.4f} seconds")
        print(f"Average Speed per Pairwise Comp: {avg_speed_ms:.4f} ms / pair")
        print("==================================================")

        assert total_comparisons > 0
    finally:
        session.close()
