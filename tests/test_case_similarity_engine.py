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


def test_person_resolution_semantics_high_vs_possible_vs_name_vs_phonetic():
    """Explicitly verifies Person Resolution semantics: HIGH_CONFIDENCE=MATCH(1.0), POSSIBLE=PARTIAL(0.70), NAME_ONLY=PARTIAL(0.35), PHONETIC_ONLY=PARTIAL(0.40)."""
    
    # 1. High Confidence Match -> MATCH (1.0)
    dict_high1 = {"id": "c1", "fir_number": "FIR/1", "persons": [{"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-01-01", "phone": "+919861105000"}]}
    dict_high2 = {"id": "c2", "fir_number": "FIR/2", "persons": [{"id": "p2", "name": "Rahul Kumar alias Raju", "date_of_birth": "1990-01-01", "phone": "+919861105000"}]}
    f_high1 = CaseFeatureExtractor.extract_from_dict(dict_high1)
    f_high2 = CaseFeatureExtractor.extract_from_dict(dict_high2)
    res_high = CaseSimilarityEngine.compare_cases(f_high1, f_high2)
    p_high = next(s for s in res_high.signals if s.signal_name == "PERSON_OVERLAP")
    assert p_high.status == SignalStatus.MATCH
    assert p_high.raw_score == 1.0
    assert "high-confidence entity match" in p_high.evidence[0]

    # 2. Possible Match (moderate name similarity without supporting DOB/phone drops decision to POSSIBLE_MATCH) -> PARTIAL (0.70)
    dict_pos1 = {"id": "c3", "fir_number": "FIR/3", "persons": [{"id": "p3", "name": "Rahul Kumar"}]}
    dict_pos2 = {"id": "c4", "fir_number": "FIR/4", "persons": [{"id": "p4", "name": "Rahul Kumar Jena"}]}
    f_pos1 = CaseFeatureExtractor.extract_from_dict(dict_pos1)
    f_pos2 = CaseFeatureExtractor.extract_from_dict(dict_pos2)
    res_pos = CaseSimilarityEngine.compare_cases(f_pos1, f_pos2)
    p_pos = next(s for s in res_pos.signals if s.signal_name == "PERSON_OVERLAP")
    assert p_pos.status == SignalStatus.PARTIAL
    assert p_pos.raw_score == 0.70
    assert "identity is not confirmed" in p_pos.evidence[0]

    # 3. Name Only Match -> PARTIAL (0.35)
    dict_name1 = {"id": "c5", "fir_number": "FIR/5", "persons": [{"id": "p5", "name": "Rahul Kumar", "date_of_birth": "1990-01-01"}]}
    dict_name2 = {"id": "c6", "fir_number": "FIR/6", "persons": [{"id": "p6", "name": "Rahul Kumar", "date_of_birth": "1980-05-15"}]}  # Conflicting DOB
    f_name1 = CaseFeatureExtractor.extract_from_dict(dict_name1)
    f_name2 = CaseFeatureExtractor.extract_from_dict(dict_name2)
    res_name = CaseSimilarityEngine.compare_cases(f_name1, f_name2)
    p_name = next(s for s in res_name.signals if s.signal_name == "PERSON_OVERLAP")
    assert p_name.status == SignalStatus.PARTIAL
    assert p_name.raw_score == 0.35
    assert "unverified identity" in p_name.evidence[0]

    # 4. Phonetic Only Match -> PARTIAL (0.40)
    dict_ph1 = {"id": "c7", "fir_number": "FIR/7", "persons": [{"id": "p7", "name": "Suresh", "date_of_birth": "1992-01-01"}]}
    dict_ph2 = {"id": "c8", "fir_number": "FIR/8", "persons": [{"id": "p8", "name": "Suraj", "date_of_birth": "1980-03-03"}]}
    f_ph1 = CaseFeatureExtractor.extract_from_dict(dict_ph1)
    f_ph2 = CaseFeatureExtractor.extract_from_dict(dict_ph2)
    res_ph = CaseSimilarityEngine.compare_cases(f_ph1, f_ph2)
    p_ph = next(s for s in res_ph.signals if s.signal_name == "PERSON_OVERLAP")
    assert p_ph.status == SignalStatus.PARTIAL
    assert p_ph.raw_score == 0.40

    # 5. Unrelated Persons -> MISMATCH (0.0)
    dict_un1 = {"id": "c9", "fir_number": "FIR/9", "persons": [{"id": "p9", "name": "Rahul Kumar"}]}
    dict_un2 = {"id": "c10", "fir_number": "FIR/10", "persons": [{"id": "p10", "name": "Jagannath Mohanty"}]}
    f_un1 = CaseFeatureExtractor.extract_from_dict(dict_un1)
    f_un2 = CaseFeatureExtractor.extract_from_dict(dict_un2)
    res_un = CaseSimilarityEngine.compare_cases(f_un1, f_un2)
    p_un = next(s for s in res_un.signals if s.signal_name == "PERSON_OVERLAP")
    assert p_un.status == SignalStatus.MISMATCH
    assert p_un.raw_score == 0.0


def test_mo_source_weight_factors_1_00_0_95_0_90():
    """Explicitly verifies MO source combination factors: Dedicated+Dedicated=1.00, Dedicated+Derived=0.95, Derived+Derived=0.90."""
    text_mo = "Lock broken using iron cutter and gold stolen"

    # Dedicated + Dedicated -> 1.00 factor
    d1 = {"id": "c1", "fir_number": "FIR/1", "modus_operandi": text_mo}
    d2 = {"id": "c2", "fir_number": "FIR/2", "modus_operandi": text_mo}
    f1 = CaseFeatureExtractor.extract_from_dict(d1)
    f2 = CaseFeatureExtractor.extract_from_dict(d2)
    r12 = CaseSimilarityEngine.compare_cases(f1, f2)
    mo12 = next(s for s in r12.signals if s.signal_name == "MO_TEXT_SIMILARITY")
    assert "both cases have dedicated mo" in mo12.explanation.lower()
    assert mo12.raw_score == 1.00

    # Dedicated + Description Derived -> 0.95 factor
    d3 = {"id": "c3", "fir_number": "FIR/3", "description": text_mo}
    f3 = CaseFeatureExtractor.extract_from_dict(d3)
    r13 = CaseSimilarityEngine.compare_cases(f1, f3)
    mo13 = next(s for s in r13.signals if s.signal_name == "MO_TEXT_SIMILARITY")
    assert "one case has dedicated mo" in mo13.explanation.lower()
    assert mo13.raw_score == 0.95

    # Description Derived + Description Derived -> 0.90 factor
    d4 = {"id": "c4", "fir_number": "FIR/4", "description": text_mo}
    f4 = CaseFeatureExtractor.extract_from_dict(d4)
    r34 = CaseSimilarityEngine.compare_cases(f3, f4)
    mo34 = next(s for s in r34.signals if s.signal_name == "MO_TEXT_SIMILARITY")
    assert "both cases use description-derived mo" in mo34.explanation.lower()
    assert mo34.raw_score == 0.90


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
