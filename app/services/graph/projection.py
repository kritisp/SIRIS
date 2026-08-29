import logging
from typing import Dict, Optional
from app.models.case import Case
from app.models.person import CasePerson, Person
from app.models.vehicle import CaseVehicle, Vehicle
from app.models.phone import CasePhone, Phone
from app.models.location import Location
from app.models.evidence import Evidence
from app.models.legal_section import CaseLegalSection, LegalSection
from app.services.graph.connection import (
    Neo4jConnectionService,
    _sanitize_error_message,
    neo4j_connection_service,
)
from app.services.graph.contracts import (
    CaseEvidenceRelContract,
    CaseGraphNode,
    CaseLegalSectionRelContract,
    CaseLocationRelContract,
    CasePersonRelContract,
    CasePhoneRelContract,
    CaseVehicleRelContract,
    EvidenceGraphNode,
    LegalSectionGraphNode,
    LocationGraphNode,
    PersonGraphNode,
    PhoneGraphNode,
    RelatedToCaseRelContract,
    VehicleGraphNode,
)
from app.services.relationship_engine.confidence.models import RelationshipConfidenceAssessment

logger = logging.getLogger(__name__)


class Neo4jGraphProjectionService:
    """Controlled, idempotent graph projection engine projecting authoritative PostgreSQL data into Neo4j."""

    def __init__(self, connection_service: Neo4jConnectionService = neo4j_connection_service):
        self.connection_service = connection_service

    # =====================================================================
    # 1. NODE PROJECTION METHODS
    # =====================================================================

    def project_case_node(self, case_contract: CaseGraphNode) -> bool:
        """Projects a (:Case) node deterministically using MERGE."""
        query = """
        MERGE (n:Case {node_id: $node_id})
        SET n.fir_number = $fir_number,
            n.station_id = $station_id,
            n.police_station = $police_station,
            n.district = $district,
            n.state = $state,
            n.registration_date = $registration_date,
            n.incident_date = $incident_date,
            n.crime_type = $crime_type,
            n.crime_category = $crime_category,
            n.status = $status,
            n.source_system = $source_system,
            n.source_id = $source_id,
            n.projection_version = $projection_version
        """
        return self._execute_query(query, case_contract.model_dump())

    def project_person_node(self, person_contract: PersonGraphNode) -> bool:
        """Projects a (:Person) node deterministically using MERGE."""
        query = """
        MERGE (n:Person {node_id: $node_id})
        SET n.name = $name,
            n.normalized_name = $normalized_name,
            n.gender = $gender,
            n.identifier_hash = $identifier_hash,
            n.source_system = $source_system,
            n.source_id = $source_id,
            n.projection_version = $projection_version
        """
        return self._execute_query(query, person_contract.model_dump())

    def project_vehicle_node(self, vehicle_contract: VehicleGraphNode) -> bool:
        """Projects a (:Vehicle) node deterministically using MERGE."""
        query = """
        MERGE (n:Vehicle {node_id: $node_id})
        SET n.registration_number = $registration_number,
            n.normalized_reg = $normalized_reg,
            n.vehicle_type = $vehicle_type,
            n.make = $make,
            n.model = $model,
            n.source_system = $source_system,
            n.source_id = $source_id,
            n.projection_version = $projection_version
        """
        return self._execute_query(query, vehicle_contract.model_dump())

    def project_phone_node(self, phone_contract: PhoneGraphNode) -> bool:
        """Projects a (:Phone) node deterministically using MERGE."""
        query = """
        MERGE (n:Phone {node_id: $node_id})
        SET n.normalized_number = $normalized_number,
            n.number_hash = $number_hash,
            n.source_system = $source_system,
            n.source_id = $source_id,
            n.projection_version = $projection_version
        """
        return self._execute_query(query, phone_contract.model_dump())

    def project_location_node(self, location_contract: LocationGraphNode) -> bool:
        """Projects a (:Location) node deterministically using MERGE."""
        query = """
        MERGE (n:Location {node_id: $node_id})
        SET n.locality = $locality,
            n.city = $city,
            n.district = $district,
            n.state = $state,
            n.latitude = $latitude,
            n.longitude = $longitude,
            n.source_system = $source_system,
            n.source_id = $source_id,
            n.projection_version = $projection_version
        """
        return self._execute_query(query, location_contract.model_dump())

    def project_evidence_node(self, evidence_contract: EvidenceGraphNode) -> bool:
        """Projects an (:Evidence) node deterministically using MERGE."""
        query = """
        MERGE (n:Evidence {node_id: $node_id})
        SET n.evidence_type = $evidence_type,
            n.source = $source,
            n.status = $status,
            n.source_system = $source_system,
            n.source_id = $source_id,
            n.projection_version = $projection_version
        """
        return self._execute_query(query, evidence_contract.model_dump())

    def project_legal_section_node(self, legal_section_contract: LegalSectionGraphNode) -> bool:
        """Projects a (:LegalSection) node deterministically using MERGE."""
        query = """
        MERGE (n:LegalSection {node_id: $node_id})
        SET n.code = $code,
            n.title = $title,
            n.law_name = $law_name,
            n.source_system = $source_system,
            n.source_id = $source_id,
            n.projection_version = $projection_version
        """
        return self._execute_query(query, legal_section_contract.model_dump())

    # =====================================================================
    # 2. ENTITY RELATIONSHIP PROJECTION METHODS
    # =====================================================================

    def project_case_person_rel(self, rel_contract: CasePersonRelContract) -> bool:
        """Projects (:Case)-[:HAS_PERSON]->(:Person) relationship."""
        query = """
        MATCH (c:Case {node_id: $case_id})
        MATCH (p:Person {node_id: $person_id})
        MERGE (c)-[r:HAS_PERSON]->(p)
        SET r.role = $role,
            r.projection_version = $projection_version
        """
        return self._execute_query(query, rel_contract.model_dump())

    def project_case_vehicle_rel(self, rel_contract: CaseVehicleRelContract) -> bool:
        """Projects (:Case)-[:HAS_VEHICLE]->(:Vehicle) relationship."""
        query = """
        MATCH (c:Case {node_id: $case_id})
        MATCH (v:Vehicle {node_id: $vehicle_id})
        MERGE (c)-[r:HAS_VEHICLE]->(v)
        SET r.role = $role,
            r.projection_version = $projection_version
        """
        return self._execute_query(query, rel_contract.model_dump())

    def project_case_phone_rel(self, rel_contract: CasePhoneRelContract) -> bool:
        """Projects (:Case)-[:HAS_PHONE]->(:Phone) relationship."""
        query = """
        MATCH (c:Case {node_id: $case_id})
        MATCH (p:Phone {node_id: $phone_id})
        MERGE (c)-[r:HAS_PHONE]->(p)
        SET r.projection_version = $projection_version
        """
        return self._execute_query(query, rel_contract.model_dump())

    def project_case_location_rel(self, rel_contract: CaseLocationRelContract) -> bool:
        """Projects (:Case)-[:HAS_LOCATION]->(:Location) relationship."""
        query = """
        MATCH (c:Case {node_id: $case_id})
        MATCH (l:Location {node_id: $location_id})
        MERGE (c)-[r:HAS_LOCATION]->(l)
        SET r.projection_version = $projection_version
        """
        return self._execute_query(query, rel_contract.model_dump())

    def project_case_evidence_rel(self, rel_contract: CaseEvidenceRelContract) -> bool:
        """Projects (:Case)-[:HAS_EVIDENCE]->(:Evidence) relationship."""
        query = """
        MATCH (c:Case {node_id: $case_id})
        MATCH (e:Evidence {node_id: $evidence_id})
        MERGE (c)-[r:HAS_EVIDENCE]->(e)
        SET r.evidence_type = $evidence_type,
            r.projection_version = $projection_version
        """
        return self._execute_query(query, rel_contract.model_dump())

    def project_case_legal_section_rel(self, rel_contract: CaseLegalSectionRelContract) -> bool:
        """Projects (:Case)-[:HAS_LEGAL_SECTION]->(:LegalSection) relationship."""
        query = """
        MATCH (c:Case {node_id: $case_id})
        MATCH (s:LegalSection {node_id: $legal_section_id})
        MERGE (c)-[r:HAS_LEGAL_SECTION]->(s)
        SET r.projection_version = $projection_version
        """
        return self._execute_query(query, rel_contract.model_dump())

    # =====================================================================
    # 3. CASE-TO-CASE ANALYTICAL RELATIONSHIP PROJECTION
    # =====================================================================

    def project_relationship_assessment(self, assessment: RelationshipConfidenceAssessment) -> bool:
        """Projects a Step 5B RelationshipConfidenceAssessment as a canonicalized RELATED_TO edge."""
        rel_contract = RelatedToCaseRelContract.from_assessment(assessment)
        query = """
        MATCH (c1:Case {node_id: $source_case_id})
        MATCH (c2:Case {node_id: $target_case_id})
        MERGE (c1)-[r:RELATED_TO {canonical_relationship_key: $canonical_relationship_key}]->(c2)
        SET r.confidence_score = $confidence_score,
            r.confidence_level = $confidence_level,
            r.contributing_families = $contributing_families,
            r.evidence_summary = $evidence_summary,
            r.explanation = $explanation,
            r.uncertainty_notes = $uncertainty_notes,
            r.provenance = $provenance,
            r.methodology_version = $methodology_version,
            r.projection_version = $projection_version
        """
        return self._execute_query(query, rel_contract.model_dump())

    # =====================================================================
    # 4. CONTROLLED HIGH-LEVEL CASE PROJECTION HELPER
    # =====================================================================

    def project_case_graph(self, case: Case) -> Dict[str, int]:
        """Projects a single PostgreSQL Case model instance and all its associated entities/relationships cleanly into Neo4j."""
        counts = {
            "cases": 0,
            "persons": 0,
            "vehicles": 0,
            "phones": 0,
            "locations": 0,
            "evidences": 0,
            "legal_sections": 0,
            "relationships": 0,
        }

        case_id_str = str(case.id)

        # 1. Project Case Node
        c_node = CaseGraphNode(
            node_id=case_id_str,
            source_id=case_id_str,
            fir_number=case.fir_number,
            station_id=case.station_id,
            police_station=case.police_station,
            district=case.district,
            state=case.state,
            registration_date=str(case.registration_date),
            incident_date=str(case.incident_date) if case.incident_date else None,
            crime_type=case.crime_type,
            crime_category=case.crime_category,
            status=case.status,
        )
        if self.project_case_node(c_node):
            counts["cases"] += 1

        # 2. Project Location if present
        if case.location:
            loc = case.location
            loc_id_str = str(loc.id)
            loc_node = LocationGraphNode(
                node_id=loc_id_str,
                source_id=loc_id_str,
                locality=loc.locality,
                city=loc.city,
                district=loc.district,
                state=loc.state,
                latitude=loc.latitude,
                longitude=loc.longitude,
            )
            if self.project_location_node(loc_node):
                counts["locations"] += 1

            loc_rel = CaseLocationRelContract(case_id=case_id_str, location_id=loc_id_str)
            if self.project_case_location_rel(loc_rel):
                counts["relationships"] += 1

        # 3. Project Persons and Person Associations
        if case.person_associations:
            for assoc in case.person_associations:
                if assoc.person:
                    p = assoc.person
                    p_id_str = str(p.id)
                    p_node = PersonGraphNode(
                        node_id=p_id_str,
                        source_id=p_id_str,
                        name=p.name,
                        normalized_name=getattr(p, "normalized_name", None) or p.name.lower().strip(),
                        gender=p.gender,
                        identifier_hash=p.identifier_hash,
                    )
                    if self.project_person_node(p_node):
                        counts["persons"] += 1

                    role_val = assoc.role.value if hasattr(assoc.role, "value") else str(assoc.role)
                    p_rel = CasePersonRelContract(case_id=case_id_str, person_id=p_id_str, role=role_val)
                    if self.project_case_person_rel(p_rel):
                        counts["relationships"] += 1

        # 4. Project Vehicles and Vehicle Associations
        if case.vehicle_associations:
            for assoc in case.vehicle_associations:
                if assoc.vehicle:
                    v = assoc.vehicle
                    v_id_str = str(v.id)
                    v_node = VehicleGraphNode(
                        node_id=v_id_str,
                        source_id=v_id_str,
                        registration_number=v.registration_number,
                        normalized_reg=getattr(v, "normalized_reg", None) or v.registration_number.upper().strip(),
                        vehicle_type=v.vehicle_type,
                        make=v.make,
                        model=v.model,
                    )
                    if self.project_vehicle_node(v_node):
                        counts["vehicles"] += 1

                    role_val = assoc.role.value if hasattr(assoc.role, "value") else str(assoc.role)
                    v_rel = CaseVehicleRelContract(case_id=case_id_str, vehicle_id=v_id_str, role=role_val)
                    if self.project_case_vehicle_rel(v_rel):
                        counts["relationships"] += 1

        # 5. Project Phones and Phone Associations
        if case.phone_associations:
            for assoc in case.phone_associations:
                if assoc.phone:
                    ph = assoc.phone
                    ph_id_str = str(ph.id)
                    ph_node = PhoneGraphNode(
                        node_id=ph_id_str,
                        source_id=ph_id_str,
                        normalized_number=ph.normalized_number,
                        number_hash=ph.number_hash,
                    )
                    if self.project_phone_node(ph_node):
                        counts["phones"] += 1

                    ph_rel = CasePhoneRelContract(case_id=case_id_str, phone_id=ph_id_str)
                    if self.project_case_phone_rel(ph_rel):
                        counts["relationships"] += 1

        # 6. Project Evidences
        if case.evidences:
            for ev in case.evidences:
                ev_id_str = str(ev.id)
                ev_type_val = ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type)
                ev_node = EvidenceGraphNode(
                    node_id=ev_id_str,
                    source_id=ev_id_str,
                    evidence_type=ev_type_val,
                    source=ev.source,
                    status=ev.status,
                )
                if self.project_evidence_node(ev_node):
                    counts["evidences"] += 1

                ev_rel = CaseEvidenceRelContract(
                    case_id=case_id_str, evidence_id=ev_id_str, evidence_type=ev_type_val
                )
                if self.project_case_evidence_rel(ev_rel):
                    counts["relationships"] += 1

        # 7. Project Legal Sections and Associations
        if case.legal_section_associations:
            for assoc in case.legal_section_associations:
                if assoc.legal_section:
                    ls = assoc.legal_section
                    ls_id_str = str(ls.id)
                    ls_node = LegalSectionGraphNode(
                        node_id=ls_id_str,
                        source_id=ls_id_str,
                        code=ls.code,
                        title=ls.title,
                        law_name=ls.law_name,
                    )
                    if self.project_legal_section_node(ls_node):
                        counts["legal_sections"] += 1

                    ls_rel = CaseLegalSectionRelContract(case_id=case_id_str, legal_section_id=ls_id_str)
                    if self.project_case_legal_section_rel(ls_rel):
                        counts["relationships"] += 1

        return counts

    # =====================================================================
    # PRIVATE QUERY EXECUTION HELPER
    # =====================================================================

    def _execute_query(self, query: str, params: dict) -> bool:
        """Executes a Cypher query with sanitized error handling."""
        try:
            driver = self.connection_service.get_driver()
            with driver.session(database=self.connection_service.database) as session:
                session.run(query, params)
                return True
        except Exception as e:
            sanitized_msg = _sanitize_error_message(e, self.connection_service.password)
            logger.error("Failed executing graph projection query: %s", sanitized_msg)
            raise RuntimeError(f"Graph projection query failed: {sanitized_msg}") from None


neo4j_graph_projection_service = Neo4jGraphProjectionService()
