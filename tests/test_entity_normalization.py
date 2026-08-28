from datetime import date, datetime, time
import pytest
from app.normalization import EntityType, EntityNormalizationService


def test_person_normalization():
    service = EntityNormalizationService()

    # 1. Whitespace, lowercase, and title stripping
    n1 = service.normalize_person(" Shri Rahul  Kumar ")
    assert n1.normalized_value == "rahul kumar"
    assert n1.entity_type == EntityType.PERSON

    n2 = service.normalize_person("rahul kumar")
    assert n2.normalized_value == "rahul kumar"

    # 2. Initials formatting
    n3 = service.normalize_person("R. Kumar")
    assert n3.normalized_value == "r kumar"

    n4 = service.normalize_person("Rahul K.")
    assert n4.normalized_value == "rahul k"

    # 3. Alias parsing
    n5 = service.normalize_person("Rahul Kumar alias Raju")
    assert n5.normalized_value == "rahul kumar"
    assert n5.metadata.get("alias") == "raju"

    # 4. Phonetic Soundex code presence
    assert len(n1.phonetic_value) > 0


def test_phone_normalization():
    service = EntityNormalizationService()

    valid_inputs = [
        "+919861105000",
        "919861105000",
        "09861105000",
        "9861105000",
        "9861-105-000",
        "(+91) 98611 05000",
    ]

    for inp in valid_inputs:
        norm = service.normalize_phone(inp)
        assert norm.normalized_value == "+919861105000"
        assert norm.metadata["is_valid"] is True
        assert norm.metadata["country_code"] == "+91"
        assert norm.metadata["national_number"] == "9861105000"

    # Invalid phone
    invalid = service.normalize_phone("123")
    assert invalid.metadata["is_valid"] is False


def test_vehicle_normalization():
    service = EntityNormalizationService()

    inputs = [
        "OD02AB1234",
        "OD 02 AB 1234",
        "OD-02-AB-1234",
        "od02ab1234",
    ]

    for inp in inputs:
        norm = service.normalize_vehicle(inp)
        assert norm.normalized_value == "OD02AB1234"
        assert norm.metadata["state_code"] == "OD"
        assert norm.metadata["rto_code"] == "02"
        assert norm.metadata["series"] == "AB"
        assert norm.metadata["registration_number"] == "1234"
        assert norm.metadata["is_valid"] is True


def test_location_normalization():
    service = EntityNormalizationService()

    norm = service.normalize_location("Janpath Rd, Master Canteen Sq, Bhub")
    assert norm.normalized_value == "janpath road master canteen square bhubaneswar"
    assert "bhubaneswar" in norm.tokens


def test_evidence_normalization():
    service = EntityNormalizationService()

    norm = service.normalize_evidence("CCTV Footage / Call Details Dump (CDR)")
    assert "cctv" in norm.tokens
    assert "cdr" in norm.tokens
    assert norm.raw_value == "CCTV Footage / Call Details Dump (CDR)"


def test_datetime_normalization():
    service = EntityNormalizationService()

    d_norm = service.normalize_datetime(date(2026, 1, 5))
    assert d_norm.normalized_value == "2026-01-05"
    assert d_norm.metadata["year"] == 2026

    dt_norm = service.normalize_datetime(datetime(2026, 1, 5, 10, 30, 0))
    assert "2026-01-05T10:30:00" in dt_norm.normalized_value
    assert dt_norm.metadata["epoch"] > 0


def test_modus_operandi_normalization():
    service = EntityNormalizationService()

    mo1 = service.normalize_mo("entered through rear window")
    mo2 = service.normalize_mo("entry via rear window")

    assert "enter" in mo1.tokens and "rear" in mo1.tokens and "window" in mo1.tokens
    assert "enter" in mo2.tokens and "rear" in mo2.tokens and "window" in mo2.tokens


def test_null_and_malformed_inputs():
    service = EntityNormalizationService()

    p_empty = service.normalize_person(None)
    assert p_empty.normalized_value == ""

    ph_empty = service.normalize_phone("")
    assert ph_empty.normalized_value == ""

    v_empty = service.normalize_vehicle("   ")
    assert v_empty.normalized_value == ""


def test_determinism():
    service = EntityNormalizationService()

    res1 = service.normalize_person("R. Kumar")
    res2 = service.normalize_person("R. Kumar")
    assert res1.model_dump() == res2.model_dump()
