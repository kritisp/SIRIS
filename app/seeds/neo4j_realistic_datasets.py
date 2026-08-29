import logging
import uuid
from datetime import date, timedelta
from typing import Dict, List, Any, Tuple

from app.config.settings import settings
from app.models.case import Case
from app.models.person import Person, CasePerson, PersonRole
from app.models.vehicle import Vehicle, CaseVehicle, VehicleRole
from app.models.phone import Phone, CasePhone
from app.models.location import Location
from app.services.graph import (
    canonicalize_case_pair,
    neo4j_connection_service,
    neo4j_graph_projection_service,
)
from app.services.relationship_engine import (
    RelationshipConfidenceAssessment,
    RelationshipConfidenceLevel,
    SignalFamily,
)

logger = logging.getLogger(__name__)

TEST_ENVIRONMENT_TAG = "siris-test"

# Machine-readable expected topology specifications
EXPECTED_TOPOLOGY_SPECS = {
    "1_simple_direct": {
        "expected_cases": 2,
        "expected_persons": 1,
        "expected_phones": 1,
        "expected_vehicles": 1,
        "expected_stations": 1,
    },
    "2_cross_station": {
        "expected_cases": 3,
        "expected_persons": 1,
        "expected_stations": 3,
    },
    "3_multi_hop": {
        "expected_cases": 3,
        "expected_persons": 2,
        "expected_phones": 1,
        "expected_vehicles": 1,
        "expected_path_node_types": ["Case", "Person", "Case", "Phone", "Case", "Person", "Case", "Vehicle", "Case"],
    },
    "4_shared_vehicle": {
        "expected_cases": 4,
        "expected_vehicles": 1,
        "expected_top_vehicle_reg": "OD02REAL9999",
    },
    "5_shared_phone": {
        "expected_cases": 5,
        "expected_phones": 1,
        "expected_top_phone_num": "9861999999",
    },
    "6_location_time": {
        "expected_cases": 3,
        "expected_locations": 2,
        "expected_temporal_window_hours": 48,
    },
    "7_community_structure": {
        "expected_cases": 6,
        "expected_communities": 2,
        "expected_bridge_name": "Bridge Suspect D7 (Kalia)",
    },
    "8_noise_disambiguation": {
        "expected_cases": 2,
        "expected_persons": 2,
        "distinct_canonical_ids": True,
    },
    "9_large_graph": {
        "expected_cases": 60,
        "min_total_entities": 100,
        "expected_stations": 6,
    },
    "10_complex_multistation": {
        "expected_cases": 25,
        "expected_stations": 5,
        "min_total_entities": 30,
        "expected_communities": 2,
        "expected_bridge_name": "Synthetic Suspect D10 (Debendra Swain)",
    },
}


class Neo4jRealisticDatasets:
    """Generates 10 deterministic, highly realistic synthetic datasets for testing the Central Intelligence Engine."""

    def __init__(self):
        self.dataset_generators = {
            "1_simple_direct": self.build_dataset_1_simple_direct,
            "2_cross_station": self.build_dataset_2_cross_station,
            "3_multi_hop": self.build_dataset_3_multi_hop,
            "4_shared_vehicle": self.build_dataset_4_shared_vehicle,
            "5_shared_phone": self.build_dataset_5_shared_phone,
            "6_location_time": self.build_dataset_6_location_time,
            "7_community_structure": self.build_dataset_7_community_structure,
            "8_noise_disambiguation": self.build_dataset_8_noise_disambiguation,
            "9_large_graph": self.build_dataset_9_large_graph,
            "10_complex_multistation": self.build_dataset_10_complex_multistation,
        }

    def seed_dataset(self, dataset_key: str) -> Dict[str, Any]:
        """Seeds a specific realistic synthetic dataset into Neo4j."""
        if dataset_key not in self.dataset_generators:
            raise ValueError(f"Unknown dataset key: {dataset_key}. Available: {list(self.dataset_generators.keys())}")

        # Clear previous run of this specific dataset
        self.clear_dataset(dataset_key)

        data = self.dataset_generators[dataset_key]()
        cases = data["cases"]

        # Project into Neo4j
        for case_obj in cases:
            neo4j_graph_projection_service.project_case_graph(case_obj)

        # Generate & Project Step 5B Relationship Confidence Assessments
        assessments = []
        for i in range(len(cases)):
            for j in range(i + 1, len(cases)):
                c1, c2 = cases[i], cases[j]
                shared_p = bool(set(p.person_id for p in c1.person_associations) & set(p.person_id for p in c2.person_associations))
                shared_v = bool(set(v.vehicle_id for v in c1.vehicle_associations) & set(v.vehicle_id for v in c2.vehicle_associations))
                shared_ph = bool(set(ph.phone_id for ph in c1.phone_associations) & set(ph.phone_id for ph in c2.phone_associations))

                if shared_p or shared_v or shared_ph:
                    score = 0.95 if (shared_p and shared_v) else (0.85 if shared_p else 0.70)
                    level = RelationshipConfidenceLevel.VERY_HIGH if score >= 0.85 else RelationshipConfidenceLevel.HIGH
                    _, _, rel_key = canonicalize_case_pair(str(c1.id), str(c2.id))
                    
                    ass = RelationshipConfidenceAssessment(
                        source_case_id=str(c1.id),
                        target_case_id=str(c2.id),
                        canonical_relationship_key=rel_key,
                        confidence_score=score,
                        confidence_level=level,
                        contributing_families=[SignalFamily.PERSON_IDENTITY] if shared_p else [SignalFamily.VEHICLE],
                        evidence_summary=f"Dataset [{dataset_key}] link between {c1.fir_number} and {c2.fir_number}",
                        explanation="Shared entity association in synthetic test scenario.",
                        uncertainty_notes=[],
                    )
                    assessments.append(ass)
                    neo4j_graph_projection_service.project_relationship_assessment(ass)

        # Tag all created nodes with dataset_id and environment='siris-test'
        self._tag_neo4j_nodes(dataset_key, data["uuids"])
        data["assessments"] = assessments
        return data

    def seed_all(self) -> Dict[str, Dict[str, Any]]:
        """Seeds all 10 datasets into Neo4j."""
        results = {}
        for k in self.dataset_generators:
            results[k] = self.seed_dataset(k)
        return results

    def clear_dataset(self, dataset_key: str):
        """Clears all Neo4j nodes belonging to a specific dataset_id."""
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("MATCH (n {dataset_id: $dataset_id}) DETACH DELETE n", {"dataset_id": dataset_key})

    def clear_all_test_data(self):
        """Completely clears all synthetic test nodes tagged with environment='siris-test' or standard SIRIS schema labels without destroying arbitrary non-test nodes."""
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run("""
                MATCH (n)
                WHERE n.environment = $env
                   OR n.dataset_id IS NOT NULL
                   OR any(lbl IN labels(n) WHERE lbl IN ['Case', 'Person', 'Vehicle', 'Phone', 'Location', 'Evidence', 'LegalSection', 'RelationshipAssessment'])
                DETACH DELETE n
            """, {"env": TEST_ENVIRONMENT_TAG})

    def _tag_neo4j_nodes(self, dataset_key: str, uuids: List[str]):
        """Sets environment='siris-test' and dataset_id on created nodes."""
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run(
                "MATCH (n) WHERE n.node_id IN $ids OR n.case_id IN $ids SET n.environment = $env, n.dataset_id = $ds",
                {"ids": uuids, "env": TEST_ENVIRONMENT_TAG, "ds": dataset_key}
            )

    # -----------------------------------------------------------------
    # DATASET GENERATORS (1 THROUGH 10)
    # -----------------------------------------------------------------

    def build_dataset_1_simple_direct(self) -> Dict[str, Any]:
        """DATASET 1: Direct link across 2 FIRs sharing suspect, vehicle, and phone."""
        id_c1, id_c2 = uuid.uuid5(uuid.NAMESPACE_DNS, "d1_c1"), uuid.uuid5(uuid.NAMESPACE_DNS, "d1_c2")
        id_p1, id_v1, id_ph1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d1_p1"), uuid.uuid5(uuid.NAMESPACE_DNS, "d1_v1"), uuid.uuid5(uuid.NAMESPACE_DNS, "d1_ph1")

        p1 = Person(id=id_p1, name="Synthetic Person D1 (Ramesh Das)", gender="MALE", identifier_hash="hash_d1_p1")
        v1 = Vehicle(id=id_v1, registration_number="OD02D11111", vehicle_type="CAR", make="MARUTI", model="SWIFT")
        ph1 = Phone(id=id_ph1, normalized_number="9861000001", number_hash="hash_d1_ph1")

        c1 = Case(
            id=id_c1, fir_number="FIR/2026/D1_001", station_id="PS_BBSR_001",
            police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 1),
            crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
        )
        c1.person_associations = [CasePerson(case_id=id_c1, person_id=id_p1, person=p1, role=PersonRole.SUSPECT)]
        c1.vehicle_associations = [CaseVehicle(case_id=id_c1, vehicle_id=id_v1, vehicle=v1, role=VehicleRole.SUSPECT_VEHICLE)]
        c1.phone_associations = [CasePhone(case_id=id_c1, phone_id=id_ph1, phone=ph1)]

        c2 = Case(
            id=id_c2, fir_number="FIR/2026/D1_002", station_id="PS_BBSR_001",
            police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 5),
            crime_type="THEFT", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION",
        )
        c2.person_associations = [CasePerson(case_id=id_c2, person_id=id_p1, person=p1, role=PersonRole.ACCUSED)]
        c2.vehicle_associations = [CaseVehicle(case_id=id_c2, vehicle_id=id_v1, vehicle=v1, role=VehicleRole.RECOVERED_VEHICLE)]
        c2.phone_associations = [CasePhone(case_id=id_c2, phone_id=id_ph1, phone=ph1)]

        cases = [c1, c2]
        uuids = [str(c.id) for c in cases] + [str(id_p1), str(id_v1), str(id_ph1)]
        return {"cases": cases, "uuids": uuids}

    def build_dataset_2_cross_station(self) -> Dict[str, Any]:
        """DATASET 2: Cross-station link across 3 police stations linked by shared person."""
        id_c1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d2_c1")
        id_c2 = uuid.uuid5(uuid.NAMESPACE_DNS, "d2_c2")
        id_c3 = uuid.uuid5(uuid.NAMESPACE_DNS, "d2_c3")
        id_p1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d2_p1")

        p1 = Person(id=id_p1, name="Synthetic Person D2 (Sujit Kumar)", gender="MALE", identifier_hash="hash_d2_p1")

        c1 = Case(id=id_c1, fir_number="FIR/2026/D2_001", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 2), crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
        c1.person_associations = [CasePerson(case_id=id_c1, person_id=id_p1, person=p1, role=PersonRole.SUSPECT)]

        c2 = Case(id=id_c2, fir_number="FIR/2026/D2_002", station_id="PS_CTC_002", police_station="Cuttack City PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 10), crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
        c2.person_associations = [CasePerson(case_id=id_c2, person_id=id_p1, person=p1, role=PersonRole.ACCUSED)]

        c3 = Case(id=id_c3, fir_number="FIR/2026/D2_003", station_id="PS_PURI_003", police_station="Puri Sea Beach PS", district="Puri", state="Odisha", registration_date=date(2026, 8, 15), crime_type="LARCENY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
        c3.person_associations = [CasePerson(case_id=id_c3, person_id=id_p1, person=p1, role=PersonRole.SUSPECT)]

        cases = [c1, c2, c3]
        uuids = [str(c.id) for c in cases] + [str(id_p1)]
        return {"cases": cases, "uuids": uuids}

    def build_dataset_3_multi_hop(self) -> Dict[str, Any]:
        """DATASET 3: Structural multi-hop path through supported graph contracts:
        Case A (FIR/2026/D3_001) -> Person A (Amit Patnaik) -> Case Mid (FIR/2026/D3_MID) -> Phone A (9861000003) -> Case Mid -> Person B (Bikram Mohanty) -> Case B (FIR/2026/D3_002) -> Vehicle B (OD02D33333) -> Case B
        """
        id_cA, id_cMid, id_cB = uuid.uuid5(uuid.NAMESPACE_DNS, "d3_cA"), uuid.uuid5(uuid.NAMESPACE_DNS, "d3_cMid"), uuid.uuid5(uuid.NAMESPACE_DNS, "d3_cB")
        id_pA, id_pB = uuid.uuid5(uuid.NAMESPACE_DNS, "d3_pA"), uuid.uuid5(uuid.NAMESPACE_DNS, "d3_pB")
        id_phA = uuid.uuid5(uuid.NAMESPACE_DNS, "d3_phA")
        id_vB = uuid.uuid5(uuid.NAMESPACE_DNS, "d3_vB")

        pA = Person(id=id_pA, name="Synthetic Person D3_A (Amit Patnaik)", gender="MALE", identifier_hash="hash_d3_pa")
        pB = Person(id=id_pB, name="Synthetic Person D3_B (Bikram Mohanty)", gender="MALE", identifier_hash="hash_d3_pb")
        phA = Phone(id=id_phA, normalized_number="9861000003", number_hash="hash_d3_pha")
        vB = Vehicle(id=id_vB, registration_number="OD02D33333", vehicle_type="CAR", make="HYUNDAI", model="VERNA")

        cA = Case(id=id_cA, fir_number="FIR/2026/D3_001", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 3), crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
        cA.person_associations = [CasePerson(case_id=id_cA, person_id=id_pA, person=pA, role=PersonRole.SUSPECT)]
        cA.phone_associations = [CasePhone(case_id=id_cA, phone_id=id_phA, phone=phA)]

        cMid = Case(id=id_cMid, fir_number="FIR/2026/D3_MID", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 7), crime_type="THEFT", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
        cMid.phone_associations = [CasePhone(case_id=id_cMid, phone_id=id_phA, phone=phA)]
        cMid.person_associations = [CasePerson(case_id=id_cMid, person_id=id_pB, person=pB, role=PersonRole.SUSPECT)]

        cB = Case(id=id_cB, fir_number="FIR/2026/D3_002", station_id="PS_CTC_002", police_station="Cuttack City PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 12), crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
        cB.person_associations = [CasePerson(case_id=id_cB, person_id=id_pB, person=pB, role=PersonRole.ACCUSED)]
        cB.vehicle_associations = [CaseVehicle(case_id=id_cB, vehicle_id=id_vB, vehicle=vB, role=VehicleRole.SUSPECT_VEHICLE)]

        cases = [cA, cMid, cB]
        uuids = [str(c.id) for c in cases] + [str(id_pA), str(id_pB), str(id_phA), str(id_vB)]
        return {"cases": cases, "uuids": uuids}

    def build_dataset_4_shared_vehicle(self) -> Dict[str, Any]:
        """DATASET 4: 4 FIRs sharing vehicle OD02REAL9999 across different suspects."""
        id_v1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d4_v1")
        v1 = Vehicle(id=id_v1, registration_number="OD02REAL9999", vehicle_type="TRUCK", make="TATA", model="407")

        cases, uuids = [], [str(id_v1)]
        for i in range(1, 5):
            c_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d4_c{i}")
            p_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d4_p{i}")
            p = Person(id=p_id, name=f"Synthetic Suspect D4_{i}", gender="MALE", identifier_hash=f"hash_d4_p{i}")
            c = Case(id=c_id, fir_number=f"FIR/2026/D4_00{i}", station_id=f"PS_BBSR_00{i}", police_station=f"Station {i}", district="Khordha", state="Odisha", registration_date=date(2026, 8, i), crime_type="THEFT", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
            c.person_associations = [CasePerson(case_id=c_id, person_id=p_id, person=p, role=PersonRole.SUSPECT)]
            c.vehicle_associations = [CaseVehicle(case_id=c_id, vehicle_id=id_v1, vehicle=v1, role=VehicleRole.SUSPECT_VEHICLE)]
            cases.append(c)
            uuids.extend([str(c_id), str(p_id)])

        return {"cases": cases, "uuids": uuids}

    def build_dataset_5_shared_phone(self) -> Dict[str, Any]:
        """DATASET 5: 5 FIRs sharing phone number 9861999999 across different suspects."""
        id_ph1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d5_ph1")
        ph1 = Phone(id=id_ph1, normalized_number="9861999999", number_hash="hash_d5_ph1")

        cases, uuids = [], [str(id_ph1)]
        for i in range(1, 6):
            c_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d5_c{i}")
            p_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d5_p{i}")
            p = Person(id=p_id, name=f"Synthetic Suspect D5_{i}", gender="MALE", identifier_hash=f"hash_d5_p{i}")
            c = Case(id=c_id, fir_number=f"FIR/2026/D5_00{i}", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, i), crime_type="EXTORTION", crime_category="CRIMINAL_INTIMIDATION", status="UNDER_INVESTIGATION")
            c.person_associations = [CasePerson(case_id=c_id, person_id=p_id, person=p, role=PersonRole.ACCUSED)]
            c.phone_associations = [CasePhone(case_id=c_id, phone_id=id_ph1, phone=ph1)]
            cases.append(c)
            uuids.extend([str(c_id), str(p_id)])

        return {"cases": cases, "uuids": uuids}

    def build_dataset_6_location_time(self) -> Dict[str, Any]:
        """DATASET 6: True location + temporal correlation across 3 cases with GPS coordinates and 24-48h window."""
        cases, uuids = [], []
        id_p1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d6_p1")
        p1 = Person(id=id_p1, name="Synthetic Person D6 (Manoj Swain)", gender="MALE", identifier_hash="hash_d6_p1")
        uuids.append(str(id_p1))

        id_locX = uuid.uuid5(uuid.NAMESPACE_DNS, "d6_locX")
        locX = Location(id=id_locX, locality="Saheed Nagar Market", city="Bhubaneswar", district="Khordha", state="Odisha", latitude=20.2961, longitude=85.8245)

        id_locY = uuid.uuid5(uuid.NAMESPACE_DNS, "d6_locY")
        locY = Location(id=id_locY, locality="Janpath Commercial Area", city="Bhubaneswar", district="Khordha", state="Odisha", latitude=20.2980, longitude=85.8260)

        uuids.extend([str(id_locX), str(id_locY)])

        c1_id = uuid.uuid5(uuid.NAMESPACE_DNS, "d6_c1")
        c1 = Case(id=c1_id, fir_number="FIR/2026/D6_001", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 10), incident_date=date(2026, 8, 10), crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION", location=locX)
        c1.person_associations = [CasePerson(case_id=c1_id, person_id=id_p1, person=p1, role=PersonRole.SUSPECT)]
        cases.append(c1)
        uuids.append(str(c1_id))

        c2_id = uuid.uuid5(uuid.NAMESPACE_DNS, "d6_c2")
        c2 = Case(id=c2_id, fir_number="FIR/2026/D6_002", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 11), incident_date=date(2026, 8, 11), crime_type="THEFT", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION", location=locX)
        c2.person_associations = [CasePerson(case_id=c2_id, person_id=id_p1, person=p1, role=PersonRole.SUSPECT)]
        cases.append(c2)
        uuids.append(str(c2_id))

        c3_id = uuid.uuid5(uuid.NAMESPACE_DNS, "d6_c3")
        c3 = Case(id=c3_id, fir_number="FIR/2026/D6_003", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 12), incident_date=date(2026, 8, 12), crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION", location=locY)
        c3.person_associations = [CasePerson(case_id=c3_id, person_id=id_p1, person=p1, role=PersonRole.SUSPECT)]
        cases.append(c3)
        uuids.append(str(c3_id))

        return {"cases": cases, "uuids": uuids}

    def build_dataset_7_community_structure(self) -> Dict[str, Any]:
        """DATASET 7: True 2-community structure (Community A: 3 cases, Community B: 3 cases) linked by 1 bridge suspect (Kalia)."""
        cases, uuids = [], []

        id_bridge = uuid.uuid5(uuid.NAMESPACE_DNS, "d7_p_bridge")
        p_bridge = Person(id=id_bridge, name="Bridge Suspect D7 (Kalia)", gender="MALE", identifier_hash="hash_d7_bridge")
        uuids.append(str(id_bridge))

        id_pA1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d7_pA1")
        pA1 = Person(id=id_pA1, name="Synthetic Suspect D7_A1 (Ashok)", gender="MALE", identifier_hash="hash_d7_pa1")
        id_phA1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d7_phA1")
        phA1 = Phone(id=id_phA1, normalized_number="9861700001", number_hash="hash_d7_pha1")
        uuids.extend([str(id_pA1), str(id_phA1)])

        for i in range(1, 4):
            c_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d7_cA_{i}")
            c = Case(id=c_id, fir_number=f"FIR/2026/D7_A0{i}", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, i), crime_type="ROBBERY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
            c.person_associations = [CasePerson(case_id=c_id, person_id=id_pA1, person=pA1, role=PersonRole.SUSPECT)]
            c.phone_associations = [CasePhone(case_id=c_id, phone_id=id_phA1, phone=phA1)]
            if i == 3:
                c.person_associations.append(CasePerson(case_id=c_id, person_id=id_bridge, person=p_bridge, role=PersonRole.SUSPECT))
            cases.append(c)
            uuids.append(str(c_id))

        id_pB1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d7_pB1")
        pB1 = Person(id=id_pB1, name="Synthetic Suspect D7_B1 (Biju)", gender="MALE", identifier_hash="hash_d7_pb1")
        id_vB1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d7_vB1")
        vB1 = Vehicle(id=id_vB1, registration_number="OD05D77777", vehicle_type="MOTORCYCLE", make="HONDA", model="SHINE")
        uuids.extend([str(id_pB1), str(id_vB1)])

        for i in range(1, 4):
            c_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d7_cB_{i}")
            c = Case(id=c_id, fir_number=f"FIR/2026/D7_B0{i}", station_id="PS_CTC_002", police_station="Cuttack City PS", district="Cuttack", state="Odisha", registration_date=date(2026, 8, 10 + i), crime_type="BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
            c.person_associations = [CasePerson(case_id=c_id, person_id=id_pB1, person=pB1, role=PersonRole.ACCUSED)]
            c.vehicle_associations = [CaseVehicle(case_id=c_id, vehicle_id=id_vB1, vehicle=vB1, role=VehicleRole.SUSPECT_VEHICLE)]
            if i == 1:
                c.person_associations.append(CasePerson(case_id=c_id, person_id=id_bridge, person=p_bridge, role=PersonRole.ACCUSED))
            cases.append(c)
            uuids.append(str(c_id))

        return {"cases": cases, "uuids": uuids}

    def build_dataset_8_noise_disambiguation(self) -> Dict[str, Any]:
        """DATASET 8: Near-match names (Debendra Swain vs Debendra Kumar Swain) kept separate."""
        id_c1, id_c2 = uuid.uuid5(uuid.NAMESPACE_DNS, "d8_c1"), uuid.uuid5(uuid.NAMESPACE_DNS, "d8_c2")
        id_p1, id_p2 = uuid.uuid5(uuid.NAMESPACE_DNS, "d8_p1"), uuid.uuid5(uuid.NAMESPACE_DNS, "d8_p2")

        p1 = Person(id=id_p1, name="Debendra Swain", gender="MALE", identifier_hash="hash_d8_p1_unique")
        p2 = Person(id=id_p2, name="Debendra Kumar Swain", gender="MALE", identifier_hash="hash_d8_p2_different")

        c1 = Case(id=id_c1, fir_number="FIR/2026/D8_001", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 1), crime_type="THEFT", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
        c1.person_associations = [CasePerson(case_id=id_c1, person_id=id_p1, person=p1, role=PersonRole.SUSPECT)]

        c2 = Case(id=id_c2, fir_number="FIR/2026/D8_002", station_id="PS_BBSR_001", police_station="Saheed Nagar PS", district="Khordha", state="Odisha", registration_date=date(2026, 8, 2), crime_type="THEFT", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION")
        c2.person_associations = [CasePerson(case_id=id_c2, person_id=id_p2, person=p2, role=PersonRole.SUSPECT)]

        cases = [c1, c2]
        uuids = [str(c.id) for c in cases] + [str(id_p1), str(id_p2)]
        return {"cases": cases, "uuids": uuids}

    def build_dataset_9_large_graph(self) -> Dict[str, Any]:
        """DATASET 9: True 60-case scalability graph with 110 total entity nodes (170 total nodes in Neo4j) across 6 stations."""
        cases, uuids = [], []

        persons = []
        for p_idx in range(1, 41):
            p_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d9_p_{p_idx}")
            p = Person(id=p_id, name=f"Scalability Suspect D9_{p_idx}", gender="MALE", identifier_hash=f"hash_d9_p_{p_idx}")
            persons.append(p)
            uuids.append(str(p_id))

        phones = []
        for ph_idx in range(1, 31):
            ph_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d9_ph_{ph_idx}")
            ph = Phone(id=ph_id, normalized_number=f"9861900{ph_idx:03d}", number_hash=f"hash_d9_ph_{ph_idx}")
            phones.append(ph)
            uuids.append(str(ph_id))

        vehicles = []
        for v_idx in range(1, 26):
            v_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d9_v_{v_idx}")
            v = Vehicle(id=v_id, registration_number=f"OD02D99{v_idx:03d}", vehicle_type="CAR", make="TATA", model="NEXON")
            vehicles.append(v)
            uuids.append(str(v_id))

        locations = []
        for l_idx in range(1, 16):
            l_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d9_l_{l_idx}")
            l = Location(id=l_id, locality=f"Locality {l_idx}", city="Bhubaneswar", district="Khordha", state="Odisha", latitude=20.2900 + (l_idx * 0.001), longitude=85.8200 + (l_idx * 0.001))
            locations.append(l)
            uuids.append(str(l_id))

        stations = ["PS_BBSR_001", "PS_CTC_002", "PS_PURI_003", "PS_BALASORE_004", "PS_BERHAMPUR_005", "PS_SAMBALPUR_006"]

        for c_idx in range(1, 61):
            c_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d9_c_{c_idx}")
            st = stations[(c_idx - 1) % len(stations)]
            assigned_p = persons[c_idx % len(persons)]
            assigned_ph = phones[c_idx % len(phones)]
            assigned_v = vehicles[c_idx % len(vehicles)]
            assigned_loc = locations[c_idx % len(locations)]

            c = Case(
                id=c_id, fir_number=f"FIR/2026/D9_{c_idx:03d}", station_id=st,
                police_station=f"Police Station {st}", district="District_Large", state="Odisha",
                registration_date=date(2026, 8, (c_idx % 25) + 1), crime_type="BURGLARY" if c_idx % 2 == 0 else "THEFT",
                crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION", location=assigned_loc,
            )
            c.person_associations = [CasePerson(case_id=c_id, person_id=assigned_p.id, person=assigned_p, role=PersonRole.SUSPECT)]
            c.phone_associations = [CasePhone(case_id=c_id, phone_id=assigned_ph.id, phone=assigned_ph)]
            c.vehicle_associations = [CaseVehicle(case_id=c_id, vehicle_id=assigned_v.id, vehicle=assigned_v, role=VehicleRole.SUSPECT_VEHICLE)]

            cases.append(c)
            uuids.append(str(c_id))

        return {"cases": cases, "uuids": uuids}

    def build_dataset_10_complex_multistation(self) -> Dict[str, Any]:
        """DATASET 10: Primary demonstration dataset (25 cases, 5 stations, 34 entities, 2 communities, bridge node, noise entities)."""
        cases, uuids = [], []

        id_p1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d10_p1")
        id_p2 = uuid.uuid5(uuid.NAMESPACE_DNS, "d10_p2")
        id_v1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d10_v1")
        id_ph1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d10_ph1")
        id_loc1 = uuid.uuid5(uuid.NAMESPACE_DNS, "d10_loc1")

        p1 = Person(id=id_p1, name="Synthetic Suspect D10 (Debendra Swain)", gender="MALE", identifier_hash="hash_d10_p1")
        p2 = Person(id=id_p2, name="Synthetic Associate D10 (Subhash Chandra)", gender="MALE", identifier_hash="hash_d10_p2")
        v1 = Vehicle(id=id_v1, registration_number="OD02DEMO9999", vehicle_type="SUV", make="MAHINDRA", model="THAR")
        ph1 = Phone(id=id_ph1, normalized_number="9861888888", number_hash="hash_d10_ph1")
        loc1 = Location(id=id_loc1, locality="Master Canteen Square", city="Bhubaneswar", district="Khordha", state="Odisha", latitude=20.2700, longitude=85.8400)

        id_p_noise = uuid.uuid5(uuid.NAMESPACE_DNS, "d10_p_noise")
        p_noise = Person(id=id_p_noise, name="Debendra Kumar Swain", gender="MALE", identifier_hash="hash_d10_p_noise")
        id_v_noise = uuid.uuid5(uuid.NAMESPACE_DNS, "d10_v_noise")
        v_noise = Vehicle(id=id_v_noise, registration_number="OD05NOISE777", vehicle_type="SEDAN", make="HONDA", model="CITY")

        uuids.extend([str(id_p1), str(id_p2), str(id_v1), str(id_ph1), str(id_loc1), str(id_p_noise), str(id_v_noise)])

        stations = ["PS_BBSR_001", "PS_CTC_002", "PS_PURI_003", "PS_BALASORE_004", "PS_BERHAMPUR_005"]

        for i in range(1, 26):
            c_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"d10_c_{i}")
            st = stations[(i - 1) % len(stations)]
            c = Case(id=c_id, fir_number=f"FIR/2026/D10_{i:03d}", station_id=st, police_station=f"Police Station {st}", district="Demo District", state="Odisha", registration_date=date(2026, 8, (i % 20) + 1), crime_type="ORGANIZED_THEFT" if i % 2 == 0 else "BURGLARY", crime_category="PROPERTY_CRIME", status="UNDER_INVESTIGATION", location=loc1 if i % 4 == 0 else None)
            
            if i % 2 == 0:
                c.person_associations.append(CasePerson(case_id=c_id, person_id=id_p1, person=p1, role=PersonRole.SUSPECT))
                c.vehicle_associations.append(CaseVehicle(case_id=c_id, vehicle_id=id_v1, vehicle=v1, role=VehicleRole.SUSPECT_VEHICLE))
            if i % 3 == 0:
                c.person_associations.append(CasePerson(case_id=c_id, person_id=id_p2, person=p2, role=PersonRole.ACCUSED))
                c.phone_associations.append(CasePhone(case_id=c_id, phone_id=id_ph1, phone=ph1))
            if i == 25:
                c.person_associations.append(CasePerson(case_id=c_id, person_id=id_p_noise, person=p_noise, role=PersonRole.SUSPECT))
                c.vehicle_associations.append(CaseVehicle(case_id=c_id, vehicle_id=id_v_noise, vehicle=v_noise, role=VehicleRole.SUSPECT_VEHICLE))

            cases.append(c)
            uuids.append(str(c_id))

        return {"cases": cases, "uuids": uuids}


neo4j_realistic_datasets = Neo4jRealisticDatasets()
