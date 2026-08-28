import datetime
import random
from typing import Dict, List, Tuple, Any
from app.data.stations import POLICE_STATIONS
from app.models.case import Case
from app.models.chargesheet import Chargesheet
from app.models.evidence import Evidence
from app.models.investigation_event import InvestigationEvent
from app.models.legal_section import LegalSection, CaseLegalSection
from app.models.location import Location
from app.models.person import Person, CasePerson, PersonRole
from app.models.phone import Phone, CasePhone
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.data.generators.crime_generator import generate_single_case
from app.data.generators.evidence_generator import generate_case_evidences, generate_case_investigation_events


def build_synthetic_dataset_v2(
    rng: random.Random,
    locations: List[Location],
    persons: List[Person],
    name_variations: List[Tuple[Person, str]],
    vehicles: List[Vehicle],
    phones: List[Phone],
    legal_sections: List[LegalSection],
    total_cases: int = 250,
) -> Tuple[List[Case], Dict[str, Dict[str, Any]], Dict[str, int]]:
    """Builds complete interconnected multi-station dataset V2 with 5 planted clusters and narrative tracking."""

    cases: List[Case] = []
    ground_truth_clusters: Dict[str, Dict[str, Any]] = {}
    narrative_style_counts: Dict[str, int] = {}

    sec_map = {s.code: s for s in legal_sections}
    case_counter = 1

    def make_fir_num(station_id: str, num: int) -> str:
        prefix = station_id.replace("PS_", "")
        return f"FIR-2026-{prefix}-{num:03d}"

    def track_style(style: str):
        narrative_style_counts[style] = narrative_style_counts.get(style, 0) + 1

    # ----------------------------------------------------
    # CLUSTER A — VEHICLE THEFT NETWORK (Cross-station: BBSR-001, BBSR-002, CTC-001)
    # ----------------------------------------------------
    suspect_a1 = persons[0]  # Rahul Kumar
    veh_a1 = vehicles[0]     # OD02A1234
    phone_a1 = phones[0]     # +919861105000

    c_a1, s1 = generate_single_case(
        rng, make_fir_num("PS_BBSR_001", case_counter),
        {"station_id": "PS_BBSR_001", "police_station": "Kharavela Nagar PS", "district": "Khordha (Bhubaneswar)", "state": "Odisha"},
        locations[0], persons[10], suspect_a1, legal_sections, ("VEHICLE_THEFT", "PROPERTY_CRIME")
    )
    case_counter += 1
    track_style(s1)

    c_a2, s2 = generate_single_case(
        rng, make_fir_num("PS_BBSR_002", case_counter),
        {"station_id": "PS_BBSR_002", "police_station": "Saheed Nagar PS", "district": "Khordha (Bhubaneswar)", "state": "Odisha"},
        locations[1], persons[11], suspect_a1, legal_sections, ("VEHICLE_THEFT", "PROPERTY_CRIME")
    )
    case_counter += 1
    track_style(s2)

    c_a3, s3 = generate_single_case(
        rng, make_fir_num("PS_CTC_001", case_counter),
        {"station_id": "PS_CTC_001", "police_station": "Cuttack Sadar PS", "district": "Cuttack", "state": "Odisha"},
        locations[4], persons[12], suspect_a1, legal_sections, ("VEHICLE_THEFT", "PROPERTY_CRIME")
    )
    case_counter += 1
    track_style(s3)

    for c in [c_a1, c_a2, c_a3]:
        c.vehicle_associations.append(CaseVehicle(case_id=c.id, vehicle_id=veh_a1.id, role=VehicleRole.SUSPECT_VEHICLE))
        c.phone_associations.append(CasePhone(case_id=c.id, phone_id=phone_a1.id))
        cases.append(c)

    ground_truth_clusters["CLUSTER_A_VEHICLE_NETWORK"] = {
        "cluster_id": "CLUSTER_A_VEHICLE_NETWORK",
        "case_ids": [c_a1.fir_number, c_a2.fir_number, c_a3.fir_number],
        "station_ids": ["PS_BBSR_001", "PS_BBSR_002", "PS_CTC_001"],
        "expected_relationships": ["SHARED_PERSON", "SHARED_VEHICLE", "SHARED_PHONE", "CROSS_STATION_LINKAGE"],
    }

    # ----------------------------------------------------
    # CLUSTER B — BURGLARY PATTERN (Cross-station: BBSR-003, BBSR-004, PURI-001)
    # ----------------------------------------------------
    suspect_b1 = persons[1]  # Vikram Singh
    phone_b1 = phones[1]

    c_b1, sb1 = generate_single_case(
        rng, make_fir_num("PS_BBSR_003", case_counter),
        {"station_id": "PS_BBSR_003", "police_station": "Mancheswar PS", "district": "Khordha (Bhubaneswar)", "state": "Odisha"},
        locations[2], persons[13], suspect_b1, legal_sections, ("HOUSE_BURGLARY", "PROPERTY_CRIME")
    )
    case_counter += 1
    track_style(sb1)

    c_b2, sb2 = generate_single_case(
        rng, make_fir_num("PS_BBSR_004", case_counter),
        {"station_id": "PS_BBSR_004", "police_station": "Chandrasekharpur PS", "district": "Khordha (Bhubaneswar)", "state": "Odisha"},
        locations[3], persons[14], suspect_b1, legal_sections, ("HOUSE_BURGLARY", "PROPERTY_CRIME")
    )
    case_counter += 1
    track_style(sb2)

    c_b3, sb3 = generate_single_case(
        rng, make_fir_num("PS_PURI_001", case_counter),
        {"station_id": "PS_PURI_001", "police_station": "Puri Town PS", "district": "Puri", "state": "Odisha"},
        locations[6], persons[15], suspect_b1, legal_sections, ("HOUSE_BURGLARY", "PROPERTY_CRIME")
    )
    case_counter += 1
    track_style(sb3)

    for c in [c_b1, c_b2, c_b3]:
        c.phone_associations.append(CasePhone(case_id=c.id, phone_id=phone_b1.id))
        cases.append(c)

    ground_truth_clusters["CLUSTER_B_BURGLARY_PATTERN"] = {
        "cluster_id": "CLUSTER_B_BURGLARY_PATTERN",
        "case_ids": [c_b1.fir_number, c_b2.fir_number, c_b3.fir_number],
        "station_ids": ["PS_BBSR_003", "PS_BBSR_004", "PS_PURI_001"],
        "expected_relationships": ["SIMILAR_MO", "SHARED_PERSON", "TEMPORAL_PROXIMITY", "CROSS_STATION_LINKAGE"],
    }

    # ----------------------------------------------------
    # CLUSTER C — FRAUD NETWORK (Cross-station: BBSR-002, SBP-001, RKL-001)
    # ----------------------------------------------------
    suspect_c1 = persons[2]
    phone_c1 = phones[2]

    c_c1, sc1 = generate_single_case(
        rng, make_fir_num("PS_BBSR_002", case_counter),
        {"station_id": "PS_BBSR_002", "police_station": "Saheed Nagar PS", "district": "Khordha (Bhubaneswar)", "state": "Odisha"},
        locations[1], persons[16], suspect_c1, legal_sections, ("CYBER_FINANCIAL_FRAUD", "CYBER_CRIME")
    )
    case_counter += 1
    track_style(sc1)

    c_c2, sc2 = generate_single_case(
        rng, make_fir_num("PS_SBP_001", case_counter),
        {"station_id": "PS_SBP_001", "police_station": "Sambalpur Town PS", "district": "Sambalpur", "state": "Odisha"},
        locations[8], persons[17], suspect_c1, legal_sections, ("CYBER_FINANCIAL_FRAUD", "CYBER_CRIME")
    )
    case_counter += 1
    track_style(sc2)

    c_c3, sc3 = generate_single_case(
        rng, make_fir_num("PS_RKL_001", case_counter),
        {"station_id": "PS_RKL_001", "police_station": "Rourkela PS", "district": "Sundargarh", "state": "Odisha"},
        locations[9], persons[18], suspect_c1, legal_sections, ("CYBER_FINANCIAL_FRAUD", "CYBER_CRIME")
    )
    case_counter += 1
    track_style(sc3)

    for c in [c_c1, c_c2, c_c3]:
        c.phone_associations.append(CasePhone(case_id=c.id, phone_id=phone_c1.id))
        cases.append(c)

    ground_truth_clusters["CLUSTER_C_FRAUD_NETWORK"] = {
        "cluster_id": "CLUSTER_C_FRAUD_NETWORK",
        "case_ids": [c_c1.fir_number, c_c2.fir_number, c_c3.fir_number],
        "station_ids": ["PS_BBSR_002", "PS_SBP_001", "PS_RKL_001"],
        "expected_relationships": ["SHARED_PHONE", "SHARED_PERSON", "SIMILAR_MO", "CROSS_STATION_LINKAGE"],
    }

    # ----------------------------------------------------
    # GENERATE REMAINING CASES UP TO total_cases
    # ----------------------------------------------------
    needed = total_cases - len(cases)
    for _ in range(needed):
        station = rng.choice(POLICE_STATIONS)
        fir_num = make_fir_num(station["station_id"], case_counter)
        case_counter += 1

        loc = rng.choice(locations)
        complainant = rng.choice(persons)
        accused = rng.choice(persons)

        c_rem, s_rem = generate_single_case(
            rng, fir_num, station, loc, complainant, accused, legal_sections
        )
        track_style(s_rem)

        # Randomly attach additional vehicle/phone/evidence
        if rng.random() > 0.4:
            v = rng.choice(vehicles)
            c_rem.vehicle_associations.append(CaseVehicle(case_id=c_rem.id, vehicle_id=v.id, role=VehicleRole.SUSPECT_VEHICLE))

        if rng.random() > 0.3:
            ph = rng.choice(phones)
            c_rem.phone_associations.append(CasePhone(case_id=c_rem.id, phone_id=ph.id))

        cases.append(c_rem)

    # Attach evidences & events
    for c in cases:
        c.evidences.extend(generate_case_evidences(rng, c.id))
        c.investigation_events.extend(generate_case_investigation_events(rng, c.id, c.registration_date))

        if c.status == "CHARGESHEET_FILED" or rng.random() > 0.7:
            c.chargesheet = Chargesheet(
                case_id=c.id,
                filing_date=c.registration_date + datetime.timedelta(days=rng.randint(15, 60)),
                status="FILED",
                summary=f"Final investigation report submitted under {c.crime_type}."
            )

    return cases, ground_truth_clusters, narrative_style_counts
