import time
import pytest
from collections import Counter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from app.config.settings import settings
from app.models.case import Case
from app.services.case_similarity import CaseFeatureExtractor
from app.services.relationship_engine import (
    RelationshipConfidenceEngine,
    RelationshipConfidenceLevel,
    SignalFamily,
)


def test_scenario_a_no_signals_insufficient_data():
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

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    assert res.confidence_level == RelationshipConfidenceLevel.INSUFFICIENT_DATA
    assert res.confidence_score == 0.0


def test_scenario_b_same_case_self_comparison():
    c_dict = {"id": "c1", "fir_number": "FIR/1", "crime_type": "BURGLARY"}
    c1 = CaseFeatureExtractor.extract_from_dict(c_dict)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c1)
    assert res.confidence_level == RelationshipConfidenceLevel.SELF_COMPARISON
    assert res.confidence_score == 1.0


def test_scenario_c_d_only_contextual_signals_capped():
    """Verifies that contextual signals alone (category, legal sections) are capped at <= 0.45."""
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "crime_category": "PROPERTY_CRIME",
        "legal_sections": ["BNS 303"]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "crime_category": "PROPERTY_CRIME",
        "legal_sections": ["BNS 303"]
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    assert res.confidence_score <= 0.45
    assert res.confidence_level in (RelationshipConfidenceLevel.LOW, RelationshipConfidenceLevel.INSUFFICIENT_DATA)
    assert any("contextual" in note.lower() for note in res.uncertainty_notes)


def test_scenario_e_f_shared_phone_or_vehicle_meaningful():
    dict1 = {"id": "c1", "fir_number": "FIR/1", "phones": [{"id": "ph1", "normalized_number": "+919861105000"}]}
    dict2 = {"id": "c2", "fir_number": "FIR/2", "phones": [{"id": "ph2", "normalized_number": "+919861105000"}]}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    assert res.confidence_score >= 0.40
    assert SignalFamily.CONTACT in res.contributing_families


def test_scenario_g_h_person_relationship_contribution():
    dict_high1 = {"id": "c1", "fir_number": "FIR/1", "persons": [{"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-01-01", "phone": "+919861105000"}]}
    dict_high2 = {"id": "c2", "fir_number": "FIR/2", "persons": [{"id": "p2", "name": "Rahul Kumar alias Raju", "date_of_birth": "1990-01-01", "phone": "+919861105000"}]}

    c1 = CaseFeatureExtractor.extract_from_dict(dict_high1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict_high2)

    res_high = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    assert res_high.confidence_score >= 0.70
    assert len(res_high.high_confidence_signals) > 0


def test_scenario_i_j_corroborated_signals_reach_very_high():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "modus_operandi": "Entered via rear skylight using glass cutter",
        "vehicles": [{"id": "v1", "registration_number": "OD02AB1234"}],
        "phones": [{"id": "ph1", "normalized_number": "+919861105000"}],
        "persons": [{"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-01-01", "phone": "+919861105000"}]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "modus_operandi": "Entered via rear skylight using glass cutter",
        "vehicles": [{"id": "v2", "registration_number": "OD02AB1234"}],
        "phones": [{"id": "ph2", "normalized_number": "+919861105000"}],
        "persons": [{"id": "p2", "name": "Rahul Kumar", "date_of_birth": "1990-01-01", "phone": "+919861105000"}]
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    assert res.confidence_level in (RelationshipConfidenceLevel.VERY_HIGH, RelationshipConfidenceLevel.HIGH)
    assert res.confidence_score >= 0.85
    assert len(res.contributing_families) >= 4


def test_scenario_k_l_family_diminishing_returns_and_conflict_exposure():
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "persons": [{"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-01-01"}]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "persons": [{"id": "p2", "name": "Rahul Kumar", "date_of_birth": "1980-05-15"}]  # Conflicting DOB
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    assert len(res.conflicting_or_cautionary_signals) > 0
    assert "name-only match" in res.conflicting_or_cautionary_signals[0].lower()


def test_scenario_n_o_p_q_r_determinism_bounds_provenance():
    dict1 = {"id": "c1", "fir_number": "FIR/1", "phones": [{"id": "ph1", "normalized_number": "+919861105000"}]}
    dict2 = {"id": "c2", "fir_number": "FIR/2", "phones": [{"id": "ph2", "normalized_number": "+919861105000"}]}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    r1 = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    r2 = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)

    assert r1.model_dump() == r2.model_dump()
    assert 0.0 <= r1.confidence_score <= 1.0
    assert r1.methodology_version == "relationship-confidence-v1"
    assert "CONTACT" in r1.explanation


def test_live_supabase_relationship_confidence_engine_benchmark():
    """Benchmark relationship confidence assessment across real cases in Supabase PostgreSQL."""
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

        # Step 4A Feature Extraction
        features_list = [CaseFeatureExtractor.extract_from_model(c) for c in cases]

        # Step 5B Relationship Confidence Benchmark on 50 cases (1225 comparisons)
        start_time = time.time()
        assessments = []
        level_counts = Counter()
        total_family_contributions = 0

        for i in range(len(features_list)):
            for j in range(i + 1, len(features_list)):
                res = RelationshipConfidenceEngine.evaluate_relationship_confidence(features_list[i], features_list[j])
                assessments.append(res)
                level_counts[res.confidence_level.value] += 1
                total_family_contributions += len(res.contributing_families)

        elapsed = time.time() - start_time
        total_comparisons = len(assessments)
        avg_speed_ms = (elapsed / total_comparisons) * 1000.0 if total_comparisons > 0 else 0.0
        avg_families_per_pair = total_family_contributions / total_comparisons if total_comparisons > 0 else 0.0

        print("\n==================================================")
        print("STEP 5B RELATIONSHIP CONFIDENCE ENGINE BENCHMARK REPORT")
        print("==================================================")
        print(f"Total Cases Evaluated          : {total_cases}")
        print(f"Pairwise Comparisons Evaluated : {total_comparisons:,}")
        print("Relationship Confidence Levels Breakdown:")
        for lvl in ["VERY_HIGH", "HIGH", "MODERATE", "LOW", "INSUFFICIENT_DATA"]:
            print(f"  - {lvl:<20}: {level_counts[lvl]:,}")
        print(f"Average Contributing Families  : {avg_families_per_pair:.2f} families / pair")
        print(f"Total Execution Time           : {elapsed:.4f} seconds")
        print(f"Average Speed per Pairwise Comp: {avg_speed_ms:.4f} ms / pair")
        print("==================================================")

        assert total_comparisons > 0
    finally:
        session.close()
