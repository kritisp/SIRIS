import datetime
import random
from typing import Dict, List, Tuple, Optional
from app.models.case import Case
from app.models.chargesheet import Chargesheet
from app.models.evidence import Evidence
from app.models.investigation_event import InvestigationEvent
from app.models.legal_section import LegalSection, CaseLegalSection
from app.models.location import Location
from app.models.person import Person, CasePerson, PersonRole
from app.models.phone import Phone, CasePhone
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.data.generators.narrative_generator import generate_varied_narrative
from app.data.generators.evidence_generator import generate_case_evidences, generate_case_investigation_events

CRIME_DISTRIBUTION = [
    ("VEHICLE_THEFT", "PROPERTY_CRIME", 0.25),
    ("HOUSE_BURGLARY", "PROPERTY_CRIME", 0.20),
    ("CYBER_FINANCIAL_FRAUD", "CYBER_CRIME", 0.18),
    ("CHAIN_SNATCHING", "PROPERTY_CRIME", 0.15),
    ("PHYSICAL_ASSAULT", "VIOLENT_CRIME", 0.12),
    ("COMMERCIAL_BURGLARY", "PROPERTY_CRIME", 0.10),
]

INVESTIGATION_STATES = ["UNDER_INVESTIGATION", "CHARGESHEET_FILED", "CLOSED"]


def generate_single_case(
    rng: random.Random,
    fir_number: str,
    station: Dict[str, str],
    loc: Location,
    complainant: Person,
    accused: Person,
    legal_sections: List[LegalSection],
    crime_override: Optional[Tuple[str, str]] = None,
) -> Tuple[Case, str]:
    """Generates a realistic crime case record with rich narrative structure and realistic progression."""

    if crime_override:
        ctype, ccat = crime_override
    else:
        # Select crime type based on weights
        r = rng.random()
        cumulative = 0.0
        ctype, ccat = CRIME_DISTRIBUTION[0][0], CRIME_DISTRIBUTION[0][1]
        for item_type, item_cat, weight in CRIME_DISTRIBUTION:
            cumulative += weight
            if r <= cumulative:
                ctype, ccat = item_type, item_cat
                break

    reg_d = datetime.date(2026, rng.randint(1, 4), rng.randint(1, 28))
    inc_d = reg_d - datetime.timedelta(days=rng.randint(0, 4))
    inc_t = datetime.time(rng.randint(0, 23), rng.randint(0, 59)) if rng.random() > 0.10 else None

    # Accused display name (sometimes formatted with alias or initial variation)
    accused_display = accused.name
    if rng.random() > 0.85:
        parts = accused.name.split()
        if len(parts) >= 2:
            accused_display = f"{parts[0]} {parts[1][0]}."

    narrative, narrative_style = generate_varied_narrative(
        rng=rng,
        crime_type=ctype,
        police_station=station["police_station"],
        registration_date=reg_d,
        incident_date=inc_d,
        incident_time=inc_t or datetime.time(22, 0),
        complainant_name=complainant.name,
        accused_name=accused_display,
        location_address=loc.locality or loc.address,
        fir_number=fir_number,
    )

    status = rng.choice(INVESTIGATION_STATES)

    case = Case(
        fir_number=fir_number,
        station_id=station["station_id"],
        police_station=station["police_station"],
        district=station["district"],
        state=station["state"],
        registration_date=reg_d,
        incident_date=inc_d,
        incident_time=inc_t,
        crime_type=ctype,
        crime_category=ccat,
        description=narrative,
        status=status,
        location_id=loc.id,
    )

    # Attach complainant and accused
    case.person_associations.append(CasePerson(case_id=case.id, person_id=complainant.id, role=PersonRole.COMPLAINANT))
    case.person_associations.append(CasePerson(case_id=case.id, person_id=accused.id, role=PersonRole.ACCUSED))

    # Attach legal sections
    if legal_sections:
        sec = rng.choice(legal_sections)
        case.legal_section_associations.append(CaseLegalSection(case_id=case.id, legal_section_id=sec.id))

    return case, narrative_style
