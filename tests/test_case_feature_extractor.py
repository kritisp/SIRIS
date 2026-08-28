import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from app.config.settings import settings
from app.models.case import Case
from app.services.case_similarity import CaseFeatureExtractor, ExtractedCaseFeatures, MOSourceType


def test_fix1_to_5_no_fabricated_defaults_and_strict_missing_data():
    """Validates that missing crime_type, crime_category, station, district, state, description do NOT produce fabricated defaults."""
    c_dict = {
        "id": "case_101",
        "fir_number": "FIR/2026/999"
    }

    features = CaseFeatureExtractor.extract_from_dict(c_dict)

    # Required identifiers
    assert features.identity.case_id == "case_101"
    assert features.identity.fir_number == "FIR/2026/999"

    # Fix 1 & 4 assertions: Must NOT fabricate PS_BBSR_001, Khordha, Odisha, THEFT, etc.
    assert features.identity.station_id is None
    assert features.identity.police_station is None
    assert features.identity.district is None
    assert features.identity.state is None

    assert features.crime.crime_type is None
    assert features.crime.crime_category is None
    assert features.crime.description is None
    assert features.crime.raw_mo is None
    assert features.crime.mo_source == MOSourceType.UNAVAILABLE
    assert features.crime.normalized_mo_tokens == []
    assert features.crime.mo_keywords == []

    # Legal sections empty
    assert features.legal.legal_sections == []
    assert features.legal.normalized_sections == []

    # Geographic empty / None
    assert features.geographic.locality is None
    assert features.geographic.district is None
    assert features.geographic.latitude is None
    assert features.geographic.longitude is None
    assert features.geographic.location_tokens == []

    # Temporal
    assert features.temporal.hour is None
    assert features.temporal.time_of_day_bucket is None


def test_fix6_missing_fir_and_case_id_explicit_validation():
    """Validates that missing required identifiers raise explicit ValueError rather than generating fake FIRs."""
    with pytest.raises(ValueError, match="case_id is required"):
        CaseFeatureExtractor.extract_from_dict({"fir_number": "FIR/123"})

    with pytest.raises(ValueError, match="fir_number is required"):
        CaseFeatureExtractor.extract_from_dict({"id": "c1"})


def test_fix2_mo_source_attribution_dedicated_vs_description():
    """Validates preference for dedicated MO and explicit source type attribution."""
    # Scenario A: Dedicated MO present
    cA = {
        "id": "cA",
        "fir_number": "FIR/A",
        "modus_operandi": "Entered via rear skylight using glass cutter",
        "description": "General incident report text"
    }
    fA = CaseFeatureExtractor.extract_from_dict(cA)
    assert fA.crime.mo_source == MOSourceType.DEDICATED_MO
    assert fA.crime.raw_mo == "Entered via rear skylight using glass cutter"
    assert fA.crime.description == "General incident report text"
    assert "skylight" in fA.crime.normalized_mo_tokens or "glass" in fA.crime.normalized_mo_tokens

    # Scenario B: Description derived MO
    cB = {
        "id": "cB",
        "fir_number": "FIR/B",
        "description": "Suspect broke padlock with heavy iron rod"
    }
    fB = CaseFeatureExtractor.extract_from_dict(cB)
    assert fB.crime.mo_source == MOSourceType.DESCRIPTION_DERIVED
    assert fB.crime.raw_mo == "Suspect broke padlock with heavy iron rod"
    assert fB.crime.description == "Suspect broke padlock with heavy iron rod"

    # Scenario C: MO Unavailable
    cC = {"id": "cC", "fir_number": "FIR/C"}
    fC = CaseFeatureExtractor.extract_from_dict(cC)
    assert fC.crime.mo_source == MOSourceType.UNAVAILABLE
    assert fC.crime.raw_mo is None
    assert fC.crime.description is None


def test_fix5_legal_sections_preserves_bns_and_ipc():
    """Validates that BNS and IPC section codes preserve exact law attribution without hardcoding IPC."""
    c_dict = {
        "id": "cL",
        "fir_number": "FIR/LAW",
        "legal_sections": [
            "BNS 303",
            "IPC 379",
            {"code": "111", "law_name": "BNS"},
            {"code": "420", "law_name": "IPC"},
            "66D"
        ]
    }

    features = CaseFeatureExtractor.extract_from_dict(c_dict)
    assert "303" in features.legal.legal_sections
    assert "379" in features.legal.legal_sections
    assert "111" in features.legal.legal_sections
    assert "BNS_303" in features.legal.normalized_sections
    assert "IPC_379" in features.legal.normalized_sections
    assert "BNS_111" in features.legal.normalized_sections
    assert "IPC_420" in features.legal.normalized_sections
    assert "66D" in features.legal.normalized_sections


def test_complete_case_feature_extraction():
    """Validates feature extraction for a complete case dict fixture."""
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
        "legal_sections": ["BNS 303", "IPC 379"],
        "locality": "Khandagiri Square, Bhub",
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
    assert features.identity.case_id == "c100"
    assert features.identity.fir_number == "FIR/2026/001"
    assert features.identity.station_id == "PS_BBSR_001"
    assert features.identity.police_station == "Khandagiri PS"

    assert features.crime.mo_source == MOSourceType.DESCRIPTION_DERIVED
    assert "BNS_303" in features.legal.normalized_sections
    assert "IPC_379" in features.legal.normalized_sections

    assert len(features.entities.persons) == 2
    assert features.entities.vehicles[0].normalized_reg == "OD02AB1234"
    assert features.entities.phones[0].normalized_e164 == "+919861105000"
    assert features.temporal.time_of_day_bucket == "NIGHT"


def test_deterministic_extraction_and_zero_mutation():
    """Validates determinism and zero database/payload mutation."""
    c_dict = {
        "id": "cDet",
        "fir_number": "FIR/DET",
        "crime_type": "THEFT",
        "persons": [{"id": "p1", "name": "Rahul Kumar"}]
    }

    copy_dict = dict(c_dict)

    f1 = CaseFeatureExtractor.extract_from_dict(c_dict)
    f2 = CaseFeatureExtractor.extract_from_dict(c_dict)

    assert f1.model_dump() == f2.model_dump()
    assert c_dict == copy_dict


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
            if feat.crime.mo_source == MOSourceType.UNAVAILABLE:
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
        print(f"Cases with Missing MO          : {missing_mo_count:,}")
        print(f"Cases with Missing Locality    : {missing_location_count:,}")
        print(f"Total Extraction Execution Time: {elapsed:.4f} seconds")
        print(f"Average Speed per Case         : {avg_speed_ms:.4f} ms / case")
        print("==================================================")

        assert len(extracted_features) == total_cases
    finally:
        session.close()
