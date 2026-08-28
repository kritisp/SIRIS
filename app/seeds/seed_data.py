import datetime
import logging
from sqlalchemy.orm import Session
from app.models import (
    Case,
    Person,
    CasePerson,
    PersonRole,
    Vehicle,
    CaseVehicle,
    VehicleRole,
    Phone,
    PersonPhone,
    CasePhone,
    Location,
    Evidence,
    EvidenceType,
    Chargesheet,
    InvestigationEvent,
    InvestigationEventType,
    LegalSection,
    CaseLegalSection,
)

logger = logging.getLogger(__name__)


def create_minimal_seed_data(session: Session) -> list[Case]:
    """Generates 5 interrelated test cases for domain foundation verification."""

    # 1. Locations
    loc1 = Location(address="MG Road Sector 14", locality="Sector 14", city="Gurugram", district="Gurugram", state="Haryana", latitude=28.4595, longitude=77.0266)
    loc2 = Location(address="Connaught Place Outer Circle", locality="CP", city="New Delhi", district="Central New Delhi", state="Delhi", latitude=28.6315, longitude=77.2167)
    session.add_all([loc1, loc2])
    session.flush()

    # 2. Legal Sections
    sec_murder = LegalSection(code="IPC 302", title="Punishment for Murder", description="Whoever commits murder shall be punished with death or imprisonment for life", law_name="IPC")
    sec_theft = LegalSection(code="BNS 303", title="Theft", description="Punishment for committing theft", law_name="BNS")
    sec_robbery = LegalSection(code="IPC 392", title="Punishment for Robbery", description="Robbery punishment", law_name="IPC")
    session.add_all([sec_murder, sec_theft, sec_robbery])
    session.flush()

    # 3. Persons
    p1 = Person(name="Rajesh Kumar", date_of_birth=datetime.date(1988, 5, 12), gender="MALE", address="H.No 45, Civil Lines, Gurugram", identifier_hash="hash_p1")
    p2 = Person(name="Vikram Singh", date_of_birth=datetime.date(1992, 11, 3), gender="MALE", address="Flat 202, South Ext, New Delhi", identifier_hash="hash_p2")
    p3 = Person(name="Anita Sharma", date_of_birth=datetime.date(1995, 2, 28), gender="FEMALE", address="Sector 56, Gurugram", identifier_hash="hash_p3")
    session.add_all([p1, p2, p3])
    session.flush()

    # 4. Phones & Vehicles
    phone1 = Phone(normalized_number="+919876543210", number_hash="hash_ph1")
    phone2 = Phone(normalized_number="+919123456789", number_hash="hash_ph2")
    veh1 = Vehicle(registration_number="HR26DK1234", vehicle_type="SUV", make="Mahindra", model="Scorpio")
    session.add_all([phone1, phone2, veh1])
    session.flush()

    # Phone associations
    pp1 = PersonPhone(person_id=p1.id, phone_id=phone1.id)
    pp2 = PersonPhone(person_id=p2.id, phone_id=phone2.id)
    session.add_all([pp1, pp2])

    # 5. Case 1
    case1 = Case(
        fir_number="FIR-2026-GUR-001",
        police_station="Gurugram Central",
        district="Gurugram",
        state="Haryana",
        registration_date=datetime.date(2026, 1, 10),
        incident_date=datetime.date(2026, 1, 9),
        incident_time=datetime.time(22, 30),
        crime_type="ROBBERY",
        crime_category="PROPERTY_CRIME",
        description="Armed robbery targeting commercial jewelry store on MG Road.",
        status="UNDER_INVESTIGATION",
        location_id=loc1.id,
    )
    session.add(case1)
    session.flush()

    cp1 = CasePerson(case_id=case1.id, person_id=p1.id, role=PersonRole.ACCUSED, details="Primary suspect identified on CCTV")
    cp2 = CasePerson(case_id=case1.id, person_id=p3.id, role=PersonRole.VICTIM, details="Store owner")
    cv1 = CaseVehicle(case_id=case1.id, vehicle_id=veh1.id, role=VehicleRole.SUSPECT_VEHICLE)
    cph1 = CasePhone(case_id=case1.id, phone_id=phone1.id)
    cls1 = CaseLegalSection(case_id=case1.id, legal_section_id=sec_robbery.id)

    ev1 = Evidence(case_id=case1.id, evidence_type=EvidenceType.CCTV, description="CCTV footage of getaway SUV", source="Store Camera 1")
    ev2 = Evidence(case_id=case1.id, evidence_type=EvidenceType.MOBILE, description="Call records near tower", source="Telecom operator")
    ie1 = InvestigationEvent(case_id=case1.id, event_type=InvestigationEventType.FIR_REGISTERED, description="FIR registered based on complaint", event_date=datetime.datetime(2026, 1, 10, 8, 0, tzinfo=datetime.timezone.utc))

    session.add_all([cp1, cp2, cv1, cph1, cls1, ev1, ev2, ie1])

    # 6. Case 2
    case2 = Case(
        fir_number="FIR-2026-DEL-002",
        police_station="Connaught Place PS",
        district="Central New Delhi",
        state="Delhi",
        registration_date=datetime.date(2026, 2, 1),
        incident_date=datetime.date(2026, 1, 31),
        incident_time=datetime.time(23, 15),
        crime_type="VEHICLE_THEFT",
        crime_category="PROPERTY_CRIME",
        description="Theft of SUV vehicle from CP parking lot.",
        status="UNDER_INVESTIGATION",
        location_id=loc2.id,
    )
    session.add(case2)
    session.flush()

    cp3 = CasePerson(case_id=case2.id, person_id=p2.id, role=PersonRole.ACCUSED, details="Co-conspirator")
    cv2 = CaseVehicle(case_id=case2.id, vehicle_id=veh1.id, role=VehicleRole.STOLEN_VEHICLE)
    cls2 = CaseLegalSection(case_id=case2.id, legal_section_id=sec_theft.id)
    cs2 = Chargesheet(case_id=case2.id, filing_date=datetime.date(2026, 2, 15), status="FILED", summary="Chargesheet submitted against Vikram Singh.")

    session.add_all([cp3, cv2, cls2, cs2])

    session.commit()
    logger.info("Minimal seed dataset successfully created.")
    return [case1, case2]
