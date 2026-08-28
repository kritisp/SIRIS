import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings
from app.models import Case, Person, Phone, Vehicle
from app.services.case_similarity import CaseFeatureExtractor
from app.services.relationship_engine import (
    RelationshipSignalEngine,
    RelationshipConfidenceEngine,
    RelationshipConfidenceLevel,
    SignalCertainty,
    SignalFamily,
    get_canonical_relationship_key,
)


def test_1_stable_source_uuid_preserved():
    """Verifies that original PostgreSQL UUIDs are preserved as primary graph references."""
    dict1 = {
        "id": "11111111-1111-1111-1111-111111111111",
        "fir_number": "FIR/2026/001",
        "phones": [{"id": "22222222-2222-2222-2222-222222222222", "normalized_number": "+919861105000"}]
    }
    dict2 = {
        "id": "33333333-3333-3333-3333-333333333333",
        "fir_number": "FIR/2026/002",
        "phones": [{"id": "22222222-2222-2222-2222-222222222222", "normalized_number": "+919861105000"}]
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    assert res.source_case_id == "11111111-1111-1111-1111-111111111111"
    assert res.target_case_id == "33333333-3333-3333-3333-333333333333"
    assert "22222222-2222-2222-2222-222222222222" in res.contributing_signals[0].supporting_entity_ids


def test_2_canonical_relationship_key_ordering():
    """Verifies that Case A <-> Case B and Case B <-> Case A produce identical canonical relationship keys."""
    c_id_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    c_id_b = "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"

    key_ab = get_canonical_relationship_key(c_id_a, c_id_b)
    key_ba = get_canonical_relationship_key(c_id_b, c_id_a)

    assert key_ab == key_ba
    assert key_ab == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa:zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz:RELATED_TO"


def test_3_repeatability_and_idempotency():
    """Verifies that repeated analytical evaluations over identical inputs yield 100% identical results."""
    dict1 = {
        "id": "c1",
        "fir_number": "FIR/1",
        "vehicles": [{"id": "v1", "registration_number": "OD02AB1234"}],
        "phones": [{"id": "ph1", "normalized_number": "+919861105000"}]
    }
    dict2 = {
        "id": "c2",
        "fir_number": "FIR/2",
        "vehicles": [{"id": "v1", "registration_number": "OD02AB1234"}],
        "phones": [{"id": "ph1", "normalized_number": "+919861105000"}]
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res1 = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    res2 = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)

    assert res1.model_dump() == res2.model_dump()
    assert res1.canonical_relationship_key == res2.canonical_relationship_key


def test_4_attribute_overlap_does_not_assert_person_identity():
    """Verifies that shared phone/vehicle attributes emit EXACT_ATTRIBUTE_MATCH with explicit non-assumptive notes."""
    dict1 = {"id": "c1", "fir_number": "FIR/1", "phones": [{"id": "ph1", "normalized_number": "+919861105000"}]}
    dict2 = {"id": "c2", "fir_number": "FIR/2", "phones": [{"id": "ph2", "normalized_number": "+919861105000"}]}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    sig = res.contributing_signals[0]

    assert sig.certainty == SignalCertainty.EXACT_ATTRIBUTE_MATCH
    assert "does not establish person identity" in sig.uncertainty_note.lower()


def test_5_contextual_only_capped_at_low_or_moderate():
    """Verifies that crime category & legal section similarity alone cannot produce HIGH/VERY_HIGH confidence (capped <= 0.45)."""
    dict1 = {"id": "c1", "fir_number": "FIR/1", "crime_category": "PROPERTY_CRIME", "legal_sections": ["BNS 303"]}
    dict2 = {"id": "c2", "fir_number": "FIR/2", "crime_category": "PROPERTY_CRIME", "legal_sections": ["BNS 303"]}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    assert res.confidence_score <= 0.45
    assert res.confidence_level not in (RelationshipConfidenceLevel.HIGH, RelationshipConfidenceLevel.VERY_HIGH)


def test_6_cross_station_relationship_linkage():
    """Verifies central intelligence capability to link cases across different police station boundaries."""
    dict_ps1 = {
        "id": "c1",
        "fir_number": "FIR/PS1/2026/001",
        "station_id": "PS_BBSR_SAHEED_NAGAR",
        "police_station": "Saheed Nagar PS",
        "vehicles": [{"id": "v1", "registration_number": "OD02AB1234"}]
    }
    dict_ps2 = {
        "id": "c2",
        "fir_number": "FIR/PS2/2026/089",
        "station_id": "PS_CTC_BADAMBADI",
        "police_station": "Badambadi PS",
        "vehicles": [{"id": "v1", "registration_number": "OD02AB1234"}]
    }

    c1 = CaseFeatureExtractor.extract_from_dict(dict_ps1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict_ps2)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)
    assert res.confidence_score >= 0.40
    assert SignalFamily.VEHICLE in res.contributing_families


def test_7_multi_hop_analytical_path_integrity():
    """Verifies that direct relationships (A-B, B-C) are extracted without fabricating a non-existent direct A-C signal."""
    # Case A and Case B share Phone X
    dict_a = {"id": "case_a", "fir_number": "FIR/A", "phones": [{"id": "ph_x", "normalized_number": "+919861105000"}]}
    dict_b = {
        "id": "case_b",
        "fir_number": "FIR/B",
        "phones": [{"id": "ph_x", "normalized_number": "+919861105000"}],
        "vehicles": [{"id": "v_1", "registration_number": "OD02AB1234"}]
    }
    # Case B and Case C share Vehicle V1
    dict_c = {"id": "case_c", "fir_number": "FIR/C", "vehicles": [{"id": "v_1", "registration_number": "OD02AB1234"}]}

    ca = CaseFeatureExtractor.extract_from_dict(dict_a)
    cb = CaseFeatureExtractor.extract_from_dict(dict_b)
    cc = CaseFeatureExtractor.extract_from_dict(dict_c)

    res_ab = RelationshipConfidenceEngine.evaluate_relationship_confidence(ca, cb)
    res_bc = RelationshipConfidenceEngine.evaluate_relationship_confidence(cb, cc)
    res_ac = RelationshipConfidenceEngine.evaluate_relationship_confidence(ca, cc)

    # A <-> B is linked via Phone X
    assert SignalFamily.CONTACT in res_ab.contributing_families
    # B <-> C is linked via Vehicle V1
    assert SignalFamily.VEHICLE in res_bc.contributing_families
    # A <-> C has NO direct evidence signal
    assert res_ac.confidence_level == RelationshipConfidenceLevel.INSUFFICIENT_DATA
    assert res_ac.confidence_score == 0.0


def test_8_zero_database_mutations():
    """Verifies that analytical execution causes 0 database record changes."""
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        c1_count_before = session.scalar(select(func.count(Case.id)))
        p1_count_before = session.scalar(select(func.count(Person.id)))

        # Perform 5A + 5B analysis over 10 cases
        cases = session.query(Case).limit(10).all()
        features = [CaseFeatureExtractor.extract_from_model(c) for c in cases]

        for i in range(len(features)):
            for j in range(i + 1, len(features)):
                RelationshipConfidenceEngine.evaluate_relationship_confidence(features[i], features[j])

        c1_count_after = session.scalar(select(func.count(Case.id)))
        p1_count_after = session.scalar(select(func.count(Person.id)))

        assert c1_count_before == c1_count_after
        assert p1_count_before == p1_count_after
    finally:
        session.close()


def test_9_provenance_and_version_metadata():
    """Verifies that methodology_version and projection_version metadata survive analytical aggregation."""
    dict1 = {"id": "c1", "fir_number": "FIR/1", "phones": [{"id": "ph1", "normalized_number": "+919861105000"}]}
    dict2 = {"id": "c2", "fir_number": "FIR/2", "phones": [{"id": "ph2", "normalized_number": "+919861105000"}]}

    c1 = CaseFeatureExtractor.extract_from_dict(dict1)
    c2 = CaseFeatureExtractor.extract_from_dict(dict2)

    res = RelationshipConfidenceEngine.evaluate_relationship_confidence(c1, c2)

    assert res.methodology_version == "relationship-confidence-v1"
    assert res.projection_version == "graph-v1"
    assert res.provenance == "Step 5A Relationship Signals"
