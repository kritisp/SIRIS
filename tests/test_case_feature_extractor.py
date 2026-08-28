import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from app.config.settings import settings
from app.models.case import Case
from app.services.case_similarity import CaseFeatureExtractor, ExtractedCaseFeatures


def test_req_a_complete_case_feature_extraction():
    case_dict = {
        "id": "c100",
        "fir_number": "FIR/2026/001",
        "station_id": "PS_BBSR_001",
        "police_station": "Khandagiri PS",
        "district": "Khordha",
        "state": "Odisha",
        "registration_date": "2026-01-10",
        "incident_date": "2026-01-09",
        "hour": 22,
        "crime_type": "NIGHT_BURGLARY",
        "crime_category": "BURGLARY",
        "description": "Accused broken rear door lock using cutter and stole gold ornaments",
        "legal_sections": ["379", "380", "457"],
        "locality": "Khandagiri Square, Bhub",
        "district": "Khordha",
        "persons": [
            {"id": "p1", "name": "Rahul Kumar alias Raju", "role": "ACCUSED"},
            {"id": "p2", "name": "Suresh Jena", "role": "VICTIM"}
        ],
        "vehicles": [
            {"id": "v1", "registration_number": "OD-02-AB-1234"}
        ],
        "phones": [
            {"id": "ph1", "normalized_number": "+919861105000"}
        ],
        "evidence": [
            {"id": "ev1", "evidence_type": "CCTV", "description": "CCTV Footage showing suspect entering rear window"}
        ]
    }

    features = CaseFeatureExtractor.extract_from_dict(case_dict)
    assert isinstance(features, ExtractedCaseFeatures)

    # Identity
    assert features.identity.case_id == "c100"
    assert features.identity.fir_number == "FIR/2026/001"

    # Crime & MO
    assert "break" in features.crime.normalized_mo_tokens or "lock" in features.crime.normalized_mo_tokens

    # Legal
    assert len(features.legal.legal_sections) == 3
    assert "IPC_379" in features.legal.normalized_sections

    # Geographic
    assert "bhubaneswar" in features.geographic.location_tokens

    # Entities
    assert len(features.entities.persons) == 2
    assert features.entities.persons[0].normalized_name == "rahul kumar"
    assert features.entities.persons[0].phonetic_name == "R400-K560"
    assert features.entities.vehicles[0].normalized_reg == "OD02AB1234"
    assert features.entities.phones[0].normalized_e164 == "+919861105000"
    assert len(features.entities.evidence) == 1

    # Temporal
    assert features.temporal.year == 2026
    assert features.temporal.month == 1
    assert features.temporal.hour == 22
    assert features.temporal.time_of_day_bucket == "NIGHT"


def test_req_b_c_d_missing_attributes_safely():
    case_dict = {
        "id": "c101",
        "fir_number": "FIR/2026/002",
        "crime_type": "THEFT",
        "crime_category": "PROPERTY_CRIME"
    }

    features = CaseFeatureExtractor.extract_from_dict(case_dict)
    assert features.identity.case_id == "c101"
    assert features.crime.description is None
    assert features.crime.normalized_mo_tokens == []
    assert features.geographic.locality is None
    assert features.geographic.location_tokens == []
    assert features.entities.persons == []
    assert features.entities.vehicles == []
    assert features.entities.phones == []
    assert features.temporal.time_of_day_bucket is None


def test_req_e_f_g_h_multiple_linked_entities():
    case_dict = {
        "id": "c102",
        "fir_number": "FIR/2026/003",
        "crime_type": "ROBBERY",
        "crime_category": "VIOLENT_CRIME",
        "legal_sections": ["392", "397", "34", "120B"],
        "persons": [
            {"id": "p1", "name": "Rahul Kumar", "role": "ACCUSED"},
            {"id": "p2", "name": "Vikram Singh", "role": "ACCUSED"},
            {"id": "p3", "name": "Amit Sharma", "role": "VICTIM"}
        ],
        "vehicles": [
            {"id": "v1", "registration_number": "OD02AB1234"},
            {"id": "v2", "registration_number": "OD05C9999"}
        ],
        "phones": [
            {"id": "ph1", "normalized_number": "+919861105000"},
            {"id": "ph2", "normalized_number": "+919437000000"}
        ]
    }

    features = CaseFeatureExtractor.extract_from_dict(case_dict)
    assert len(features.legal.legal_sections) == 4
    assert len(features.entities.persons) == 3
    assert len(features.entities.vehicles) == 2
    assert len(features.entities.phones) == 2


def test_req_i_deterministic_repeated_extraction():
    case_dict = {
        "id": "c103",
        "fir_number": "FIR/2026/004",
        "crime_type": "THEFT",
        "crime_category": "PROPERTY_CRIME",
        "persons": [{"id": "p1", "name": "Rahul Kumar"}]
    }

    f1 = CaseFeatureExtractor.extract_from_dict(case_dict)
    f2 = CaseFeatureExtractor.extract_from_dict(case_dict)
    assert f1.model_dump() == f2.model_dump()


def test_req_j_zero_database_mutation():
    case_dict = {
        "id": "c104",
        "fir_number": "FIR/2026/005",
        "crime_type": "THEFT",
        "crime_category": "PROPERTY_CRIME",
    }
    copy_dict = dict(case_dict)
    f = CaseFeatureExtractor.extract_from_dict(case_dict)
    assert case_dict == copy_dict


def test_live_supabase_case_feature_extraction_benchmark():
    """Benchmark feature extraction across real seeded cases in Supabase PostgreSQL database."""
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
        ).limit(250).all()

        total_cases = len(cases)
        assert total_cases > 0, "Database should contain seeded cases"

        start_time = time.time()
        extracted_features: List[ExtractedCaseFeatures] = []
        missing_mo_count = 0
        missing_location_count = 0
        total_persons_extracted = 0

        for c in cases:
            feat = CaseFeatureExtractor.extract_from_model(c)
            extracted_features.append(feat)
            if not feat.crime.description:
                missing_mo_count += 1
            if not feat.geographic.locality and not feat.geographic.address:
                missing_location_count += 1
            total_persons_extracted += len(feat.entities.persons)

        elapsed = time.time() - start_time
        avg_speed_ms = (elapsed / total_cases) * 1000.0 if total_cases > 0 else 0.0

        print("\n==================================================")
        print("STEP 4A CASE FEATURE EXTRACTION BENCHMARK REPORT")
        print("==================================================")
        print(f"Total Database Cases Processed : {total_cases:,}")
        print(f"Total Persons Extracted        : {total_persons_extracted:,}")
        print(f"Cases with Missing MO/Desc     : {missing_mo_count:,}")
        print(f"Cases with Missing Locality    : {missing_location_count:,}")
        print(f"Total Extraction Execution Time: {elapsed:.4f} seconds")
        print(f"Average Speed per Case         : {avg_speed_ms:.4f} ms / case")
        print("==================================================")

        assert len(extracted_features) == total_cases
    finally:
        session.close()
