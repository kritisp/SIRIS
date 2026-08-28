import time
import pytest
from collections import Counter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from app.config.settings import settings
from app.models.case import Case
from app.services.case_similarity import CaseFeatureExtractor
from app.services.relationship_engine import (
    RelationshipSignalEngine,
    RelationshipType,
    SignalCertainty,
)


def test_scenario_a_confirmed_entity_resolution_relationship():
    dict1 = {"id": "c1", "fir_number": "FIR/1", "persons": [{"id": "p1", "name": "Rahul Kumar", "date_of_birth": "1990-01-01", "phone": "+919861105000"}]}
    dict2 = {"id": "c2", "fir_number": "FIR/2", "persons": [{"id": "p2", "name": "Rahul Kumar alias Raju", "date_of_birth": "1990-01-01", "phone": "+919861105000"}]}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    analysis = RelationshipSignalEngine.analyze_case_relationship(c1, c2)
    sig = next(s for s in analysis.signals if s.relationship_type == RelationshipType.SHARED_HIGH_CONFIDENCE_PERSON)

    assert sig.certainty == SignalCertainty.HIGH_CONFIDENCE
    assert sig.raw_score == 1.0
    assert "Step 3C Entity Resolution" in sig.provenance


def test_scenario_b_c_d_e_f_g_h_i_j_k_relationship_signals():
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
        "hour": 22,
        "vehicles": [{"id": "v1", "registration_number": "OD02AB1234"}],
        "phones": [{"id": "ph1", "normalized_number": "+919861105000"}]
    }
    dict2 = dict(dict1)
    dict2["id"] = "c2"
    dict2["fir_number"] = "FIR/2026/002"

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    analysis = RelationshipSignalEngine.analyze_case_relationship(c1, c2)
    sig_types = {s.relationship_type for s in analysis.signals}

    assert RelationshipType.SHARED_PHONE in sig_types
    assert RelationshipType.SHARED_VEHICLE in sig_types
    assert RelationshipType.SHARED_LOCATION in sig_types
    assert RelationshipType.SIMILAR_MODUS_OPERANDI in sig_types
    assert RelationshipType.SIMILAR_CRIME_CATEGORY in sig_types
    assert RelationshipType.SIMILAR_LEGAL_SECTIONS in sig_types
    assert RelationshipType.TEMPORAL_PROXIMITY in sig_types


def test_scenario_m_unrelated_cases_no_relationship_signals():
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

    analysis = RelationshipSignalEngine.analyze_case_relationship(c1, c2)
    assert len(analysis.signals) == 0
    assert "No relationship signals identified" in analysis.summary_explanation


def test_scenario_n_o_p_q_determinism_and_provenance():
    dict1 = {"id": "c1", "fir_number": "FIR/1", "phones": [{"id": "ph1", "normalized_number": "+919861105000"}]}
    dict2 = {"id": "c2", "fir_number": "FIR/2", "phones": [{"id": "ph2", "normalized_number": "+919861105000"}]}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    a1 = RelationshipSignalEngine.analyze_case_relationship(c1, c2)
    a2 = RelationshipSignalEngine.analyze_case_relationship(c1, c2)

    assert a1.model_dump() == a2.model_dump()
    assert a1.signals[0].provenance == "Step 3A Phone Normalization"
    assert a1.signals[0].uncertainty_note is not None
    assert "does not automatically establish criminal association" in a1.signals[0].uncertainty_note


def test_live_supabase_relationship_signal_engine_benchmark():
    """Benchmark relationship signal extraction across real cases in Supabase PostgreSQL."""
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

        # Step 5A Relationship Signal Benchmark on 50 cases (1225 comparisons)
        start_time = time.time()
        analyses = []
        signal_type_counts = Counter()

        for i in range(len(features_list)):
            for j in range(i + 1, len(features_list)):
                analysis = RelationshipSignalEngine.analyze_case_relationship(features_list[i], features_list[j])
                analyses.append(analysis)
                for sig in analysis.signals:
                    signal_type_counts[sig.relationship_type.value] += 1

        elapsed = time.time() - start_time
        total_comparisons = len(analyses)
        avg_speed_ms = (elapsed / total_comparisons) * 1000.0 if total_comparisons > 0 else 0.0
        total_signals_generated = sum(signal_type_counts.values())

        print("\n==================================================")
        print("STEP 5A RELATIONSHIP SIGNAL ENGINE BENCHMARK REPORT")
        print("==================================================")
        print(f"Total Cases Evaluated          : {total_cases}")
        print(f"Pairwise Comparisons Evaluated : {total_comparisons:,}")
        print(f"Total Relationship Signals     : {total_signals_generated:,}")
        print("Signals Generated by Type      :")
        for stype, count in signal_type_counts.most_common():
            print(f"  - {stype:<30}: {count:,}")
        print(f"Total Execution Time           : {elapsed:.4f} seconds")
        print(f"Average Speed per Pairwise Comp: {avg_speed_ms:.4f} ms / pair")
        print("==================================================")

        assert total_comparisons > 0
    finally:
        session.close()
