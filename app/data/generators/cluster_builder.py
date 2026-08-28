import datetime
import random
from typing import Dict, List, Tuple
from app.data.stations import POLICE_STATIONS
from app.models.case import Case
from app.models.chargesheet import Chargesheet
from app.models.evidence import Evidence
from app.models.investigation_event import InvestigationEvent
from app.models.legal_section import LegalSection, CaseLegalSection
from app.models.location import Location
from app.models.person import Person, CasePerson, PersonRole
from app.models.phone import Phone, PersonPhone, CasePhone
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.data.generators.evidence_generator import generate_case_evidences, generate_case_investigation_events


def build_synthetic_dataset(
    rng: random.Random,
    locations: List[Location],
    persons: List[Person],
    name_variations: List[Tuple[Person, str]],
    vehicles: List[Vehicle],
    phones: List[Phone],
    legal_sections: List[LegalSection],
    total_cases: int = 250,
) -> Tuple[List[Case], Dict[str, Dict]]:
    """Builds complete interconnected multi-station dataset with planted clusters and ground truth."""

    cases: List[Case] = []
    ground_truth_clusters: Dict[str, Dict] = {}

    # Map sections by code
    sec_map = {s.code: s for s in legal_sections}

    case_counter = 1

    def make_fir_num(station_id: str, num: int) -> str:
        prefix = station_id.replace("PS_", "")
        return f"FIR-2026-{prefix}-{num:03d}"

    # ----------------------------------------------------
    # CLUSTER A — VEHICLE THEFT NETWORK (Cross-station: BBSR-001, BBSR-002, CTC-001)
    # ----------------------------------------------------
    suspect_a1 = persons[0]  # Rahul Kumar
    veh_a1 = vehicles[0]     # OD02A1234 (Scorpio)
    phone_a1 = phones[0]     # Shared phone 1
    loc_a1 = locations[0]    # Janpath

    fir_a1 = make_fir_num("PS_BBSR_001", case_counter)
    case_a1 = Case(
        fir_number=fir_a1,
        station_id="PS_BBSR_001",
        police_station="Kharavela Nagar PS",
        district="Khordha (Bhubaneswar)",
        state="Odisha",
        registration_date=datetime.date(2026, 1, 5),
        incident_date=datetime.date(2026, 1, 4),
        incident_time=datetime.time(22, 15),
        crime_type="VEHICLE_THEFT",
        crime_category="PROPERTY_CRIME",
        description="Theft of black Mahindra Scorpio SUV parked outside commercial complex on Janpath Road. Suspect used duplicate key.",
        status="UNDER_INVESTIGATION",
        location_id=loc_a1.id,
    )
    case_counter += 1
    cases.append(case_a1)

    fir_a2 = make_fir_num("PS_BBSR_002", case_counter)
    case_a2 = Case(
        fir_number=fir_a2,
        station_id="PS_BBSR_002",
        police_station="Saheed Nagar PS",
        district="Khordha (Bhubaneswar)",
        state="Odisha",
        registration_date=datetime.date(2026, 1, 12),
        incident_date=datetime.date(2026, 1, 11),
        incident_time=datetime.time(23, 40),
        crime_type="VEHICLE_THEFT",
        crime_category="PROPERTY_CRIME",
        description="Stolen Mahindra Scorpio SUV (OD02A1234) sighted during night patrol. Suspect fled leaving vehicle near Vani Vihar.",
        status="UNDER_INVESTIGATION",
        location_id=locations[1].id,
    )
    case_counter += 1
    cases.append(case_a2)

    fir_a3 = make_fir_num("PS_CTC_001", case_counter)
    case_a3 = Case(
        fir_number=fir_a3,
        station_id="PS_CTC_001",
        police_station="Cuttack Sadar PS",
        district="Cuttack",
        state="Odisha",
        registration_date=datetime.date(2026, 1, 20),
        incident_date=datetime.date(2026, 1, 19),
        incident_time=datetime.time(21, 10),
        crime_type="INTERSTATE_VEHICLE_LIFTING",
        crime_category="PROPERTY_CRIME",
        description="Interception of illegal vehicle lifting gang operating between Bhubaneswar and Cuttack using fake number plates.",
        status="UNDER_INVESTIGATION",
        location_id=locations[4].id,
    )
    case_counter += 1
    cases.append(case_a3)

    # Attach shared entities for Cluster A
    for c in [case_a1, case_a2, case_a3]:
        c.person_associations.append(CasePerson(case_id=c.id, person_id=suspect_a1.id, role=PersonRole.ACCUSED))
        c.vehicle_associations.append(CaseVehicle(case_id=c.id, vehicle_id=veh_a1.id, role=VehicleRole.SUSPECT_VEHICLE))
        c.phone_associations.append(CasePhone(case_id=c.id, phone_id=phone_a1.id))
        if "BNS 303" in sec_map:
            c.legal_section_associations.append(CaseLegalSection(case_id=c.id, legal_section_id=sec_map["BNS 303"].id))

    ground_truth_clusters["CLUSTER_A_VEHICLE_NETWORK"] = {
        "cluster_id": "CLUSTER_A_VEHICLE_NETWORK",
        "case_ids": [case_a1.fir_number, case_a2.fir_number, case_a3.fir_number],
        "station_ids": ["PS_BBSR_001", "PS_BBSR_002", "PS_CTC_001"],
        "expected_relationships": ["SHARED_PERSON", "SHARED_VEHICLE", "SHARED_PHONE", "CROSS_STATION_LINKAGE"],
    }

    # ----------------------------------------------------
    # CLUSTER B — BURGLARY PATTERN (Cross-station: BBSR-003, BBSR-004, PURI-001)
    # ----------------------------------------------------
    suspect_b1 = persons[1]  # Vikram Singh
    phone_b1 = phones[1]

    fir_b1 = make_fir_num("PS_BBSR_003", case_counter)
    case_b1 = Case(
        fir_number=fir_b1,
        station_id="PS_BBSR_003",
        police_station="Mancheswar PS",
        district="Khordha (Bhubaneswar)",
        state="Odisha",
        registration_date=datetime.date(2026, 2, 2),
        incident_date=datetime.date(2026, 2, 1),
        incident_time=datetime.time(3, 15),
        crime_type="HOUSE_BURGLARY",
        crime_category="PROPERTY_CRIME",
        description="Night house break-in. Culprits entered through rear window grille cut using hydraulic cutter. Gold jewelry and cash stolen.",
        status="UNDER_INVESTIGATION",
        location_id=locations[2].id,
    )
    case_counter += 1
    cases.append(case_b1)

    fir_b2 = make_fir_num("PS_BBSR_004", case_counter)
    case_b2 = Case(
        fir_number=fir_b2,
        station_id="PS_BBSR_004",
        police_station="Chandrasekharpur PS",
        district="Khordha (Bhubaneswar)",
        state="Odisha",
        registration_date=datetime.date(2026, 2, 10),
        incident_date=datetime.date(2026, 2, 9),
        incident_time=datetime.time(2, 45),
        crime_type="HOUSE_BURGLARY",
        crime_category="PROPERTY_CRIME",
        description="Residential house burglary in Patia area. Entry gained by cutting iron window grille with hydraulic cutter during early morning hours.",
        status="UNDER_INVESTIGATION",
        location_id=locations[1].id,
    )
    case_counter += 1
    cases.append(case_b2)

    fir_b3 = make_fir_num("PS_PURI_001", case_counter)
    case_b3 = Case(
        fir_number=fir_b3,
        station_id="PS_PURI_001",
        police_station="Puri Town PS",
        district="Puri",
        state="Odisha",
        registration_date=datetime.date(2026, 2, 18),
        incident_date=datetime.date(2026, 2, 17),
        incident_time=datetime.time(3, 30),
        crime_type="NIGHT_BURGLARY",
        crime_category="PROPERTY_CRIME",
        description="Burglary at beach front holiday home. Modus operandi involved cutting rear window grille using hydraulic cutters.",
        status="UNDER_INVESTIGATION",
        location_id=locations[6].id,
    )
    case_counter += 1
    cases.append(case_b3)

    for c in [case_b1, case_b2, case_b3]:
        c.person_associations.append(CasePerson(case_id=c.id, person_id=suspect_b1.id, role=PersonRole.SUSPECT))
        c.phone_associations.append(CasePhone(case_id=c.id, phone_id=phone_b1.id))
        if "IPC 392" in sec_map:
            c.legal_section_associations.append(CaseLegalSection(case_id=c.id, legal_section_id=sec_map["IPC 392"].id))

    ground_truth_clusters["CLUSTER_B_BURGLARY_PATTERN"] = {
        "cluster_id": "CLUSTER_B_BURGLARY_PATTERN",
        "case_ids": [case_b1.fir_number, case_b2.fir_number, case_b3.fir_number],
        "station_ids": ["PS_BBSR_003", "PS_BBSR_004", "PS_PURI_001"],
        "expected_relationships": ["SIMILAR_MO", "SHARED_PERSON", "TEMPORAL_PROXIMITY", "CROSS_STATION_LINKAGE"],
    }

    # ----------------------------------------------------
    # CLUSTER C — FRAUD NETWORK (Cross-station: BBSR-002, SBP-001, RKL-001)
    # ----------------------------------------------------
    suspect_c1 = persons[2]
    phone_c1 = phones[2]

    fir_c1 = make_fir_num("PS_BBSR_002", case_counter)
    case_c1 = Case(
        fir_number=fir_c1,
        station_id="PS_BBSR_002",
        police_station="Saheed Nagar PS",
        district="Khordha (Bhubaneswar)",
        state="Odisha",
        registration_date=datetime.date(2026, 3, 1),
        incident_date=datetime.date(2026, 2, 28),
        incident_time=datetime.time(14, 0),
        crime_type="CYBER_FINANCIAL_FRAUD",
        crime_category="CYBER_CRIME",
        description="Cyber fraud victim induced to transfer Rs 4.5 Lakhs under fake stock investment scheme via WhatsApp group.",
        status="UNDER_INVESTIGATION",
        location_id=locations[1].id,
    )
    case_counter += 1
    cases.append(case_c1)

    fir_c2 = make_fir_num("PS_SBP_001", case_counter)
    case_c2 = Case(
        fir_number=fir_c2,
        station_id="PS_SBP_001",
        police_station="Sambalpur Town PS",
        district="Sambalpur",
        state="Odisha",
        registration_date=datetime.date(2026, 3, 8),
        incident_date=datetime.date(2026, 3, 7),
        incident_time=datetime.time(16, 20),
        crime_type="ONLINE_INVESTMENT_FRAUD",
        crime_category="CYBER_CRIME",
        description="Online trading platform scam. Victim defrauded of Rs 6 Lakhs by fraudulent investment advisors communicating on phone +919861105000.",
        status="UNDER_INVESTIGATION",
        location_id=locations[8].id,
    )
    case_counter += 1
    cases.append(case_c2)

    for c in [case_c1, case_c2]:
        c.person_associations.append(CasePerson(case_id=c.id, person_id=suspect_c1.id, role=PersonRole.ACCUSED))
        c.phone_associations.append(CasePhone(case_id=c.id, phone_id=phone_c1.id))

    ground_truth_clusters["CLUSTER_C_FRAUD_NETWORK"] = {
        "cluster_id": "CLUSTER_C_FRAUD_NETWORK",
        "case_ids": [case_c1.fir_number, case_c2.fir_number],
        "station_ids": ["PS_BBSR_002", "PS_SBP_001"],
        "expected_relationships": ["SHARED_PHONE", "SHARED_PERSON", "SIMILAR_MO", "CROSS_STATION_LINKAGE"],
    }

    # ----------------------------------------------------
    # GENERATE REMAINING CASES (~240 cases across all 8 stations)
    # ----------------------------------------------------
    crime_templates = [
        ("CHAIN_SNATCHING", "PROPERTY_CRIME", "Pillion rider on motorcycle snatched gold chain from pedestrian walking near colony street."),
        ("COMMERCIAL_BURGLARY", "PROPERTY_CRIME", "Shoplifting and illegal break-in into electronics store during early morning."),
        ("MOBILE_THEFT", "PROPERTY_CRIME", "Mobile phone snatched from victim at crowded bus stop."),
        ("ATM_CARD_SWAP_FRAUD", "CYBER_CRIME", "Fraudster swapped victim's ATM card under pretext of assisting at ATM kiosk."),
        ("PHYSICAL_ASSAULT", "VIOLENT_CRIME", "Altercation between rival groups leading to physical assault and minor injuries."),
        ("ILICIT_LIQUOR_TRAFFICKING", "ORGANIZED_CRIME", "Seizure of illicit liquor consignment transported in commercial vehicle."),
    ]

    needed_cases = total_cases - len(cases)
    for i in range(needed_cases):
        station = rng.choice(POLICE_STATIONS)
        fir_num = make_fir_num(station["station_id"], case_counter)
        case_counter += 1

        ctype, ccat, desc_base = rng.choice(crime_templates)
        reg_d = datetime.date(2026, rng.randint(1, 4), rng.randint(1, 28))
        inc_d = reg_d - datetime.timedelta(days=rng.randint(0, 3))
        inc_t = datetime.time(rng.randint(0, 23), rng.randint(0, 59))

        loc = rng.choice(locations)

        c = Case(
            fir_number=fir_num,
            station_id=station["station_id"],
            police_station=station["police_station"],
            district=station["district"],
            state=station["state"],
            registration_date=reg_d,
            incident_date=inc_d,
            incident_time=inc_t,
            crime_type=ctype,
            crime_category=ccat,
            description=f"{desc_base} Reported at {station['police_station']}.",
            status=rng.choice(["UNDER_INVESTIGATION", "CHARGESHEET_FILED", "CLOSED"]),
            location_id=loc.id,
        )

        # Attach persons
        p_accused = rng.choice(persons)
        p_victim = rng.choice(persons)
        c.person_associations.append(CasePerson(case_id=c.id, person_id=p_accused.id, role=PersonRole.ACCUSED))
        c.person_associations.append(CasePerson(case_id=c.id, person_id=p_victim.id, role=PersonRole.VICTIM))

        # Randomly attach vehicle / phone / legal sections
        if rng.random() > 0.4:
            v = rng.choice(vehicles)
            c.vehicle_associations.append(CaseVehicle(case_id=c.id, vehicle_id=v.id, role=VehicleRole.SUSPECT_VEHICLE))

        if rng.random() > 0.3:
            ph = rng.choice(phones)
            c.phone_associations.append(CasePhone(case_id=c.id, phone_id=ph.id))

        if legal_sections:
            sec = rng.choice(legal_sections)
            c.legal_section_associations.append(CaseLegalSection(case_id=c.id, legal_section_id=sec.id))

        cases.append(c)

    # Attach evidences and investigation events to all cases
    for c in cases:
        evs = generate_case_evidences(rng, c.id)
        ies = generate_case_investigation_events(rng, c.id, c.registration_date)
        c.evidences.extend(evs)
        c.investigation_events.extend(ies)

        # Generate chargesheet for ~30% cases
        if c.status == "CHARGESHEET_FILED" or rng.random() > 0.7:
            cs = Chargesheet(
                case_id=c.id,
                filing_date=c.registration_date + datetime.timedelta(days=rng.randint(15, 60)),
                status="FILED",
                summary=f"Final investigation report submitted under {c.crime_type}."
            )
            c.chargesheet = cs

    return cases, ground_truth_clusters
