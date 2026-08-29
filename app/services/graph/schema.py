import logging
from typing import Dict, List
from app.config.settings import settings
from app.services.graph.connection import Neo4jConnectionService, neo4j_connection_service

logger = logging.getLogger(__name__)

CONSTRAINTS_DDL = [
    ("c_case_node_id", "CREATE CONSTRAINT c_case_node_id IF NOT EXISTS FOR (n:Case) REQUIRE n.node_id IS UNIQUE"),
    ("c_person_node_id", "CREATE CONSTRAINT c_person_node_id IF NOT EXISTS FOR (n:Person) REQUIRE n.node_id IS UNIQUE"),
    ("c_vehicle_node_id", "CREATE CONSTRAINT c_vehicle_node_id IF NOT EXISTS FOR (n:Vehicle) REQUIRE n.node_id IS UNIQUE"),
    ("c_phone_node_id", "CREATE CONSTRAINT c_phone_node_id IF NOT EXISTS FOR (n:Phone) REQUIRE n.node_id IS UNIQUE"),
    ("c_location_node_id", "CREATE CONSTRAINT c_location_node_id IF NOT EXISTS FOR (n:Location) REQUIRE n.node_id IS UNIQUE"),
    ("c_evidence_node_id", "CREATE CONSTRAINT c_evidence_node_id IF NOT EXISTS FOR (n:Evidence) REQUIRE n.node_id IS UNIQUE"),
    ("c_legal_section_node_id", "CREATE CONSTRAINT c_legal_section_node_id IF NOT EXISTS FOR (n:LegalSection) REQUIRE n.node_id IS UNIQUE"),
]

INDEXES_DDL = [
    ("i_case_fir_number", "CREATE INDEX i_case_fir_number IF NOT EXISTS FOR (n:Case) ON (n.fir_number)"),
    ("i_case_station_id", "CREATE INDEX i_case_station_id IF NOT EXISTS FOR (n:Case) ON (n.station_id)"),
    ("i_phone_number", "CREATE INDEX i_phone_number IF NOT EXISTS FOR (n:Phone) ON (n.normalized_number)"),
    ("i_vehicle_reg", "CREATE INDEX i_vehicle_reg IF NOT EXISTS FOR (n:Vehicle) ON (n.registration_number)"),
    ("i_legal_code", "CREATE INDEX i_legal_code IF NOT EXISTS FOR (n:LegalSection) ON (n.code)"),
]


class Neo4jSchemaManager:
    """Manager for S.I.R.I.S. Neo4j graph DDL schema constraints and indexes."""

    def __init__(self, connection_service: Neo4jConnectionService = neo4j_connection_service):
        self.connection_service = connection_service

    def apply_schema_constraints(self) -> Dict[str, List[str]]:
        """Applies uniqueness constraints and indexes cleanly and idempotently."""
        applied_constraints: List[str] = []
        applied_indexes: List[str] = []

        driver = self.connection_service.get_driver()
        with driver.session(database=self.connection_service.database) as session:
            # 1. Apply Uniqueness Constraints
            for name, ddl in CONSTRAINTS_DDL:
                try:
                    session.run(ddl)
                    applied_constraints.append(name)
                    logger.info("Applied Cypher constraint: %s", name)
                except Exception as e:
                    logger.warning("Constraint DDL notice for %s: %s", name, e)

            # 2. Apply Targeted Indexes
            for name, ddl in INDEXES_DDL:
                try:
                    session.run(ddl)
                    applied_indexes.append(name)
                    logger.info("Applied Cypher index: %s", name)
                except Exception as e:
                    logger.warning("Index DDL notice for %s: %s", name, e)

        return {
            "applied_constraints": applied_constraints,
            "applied_indexes": applied_indexes,
        }

    def verify_schema_status(self) -> Dict[str, int]:
        """Queries Neo4j schema metadata to verify active constraint and index count."""
        driver = self.connection_service.get_driver()
        c_count = 0
        i_count = 0

        with driver.session(database=self.connection_service.database) as session:
            try:
                res_c = session.run("SHOW CONSTRAINTS")
                c_count = len(list(res_c))
            except Exception:
                pass

            try:
                res_i = session.run("SHOW INDEXES")
                i_count = len(list(res_i))
            except Exception:
                pass

        return {
            "active_constraints": c_count,
            "active_indexes": i_count,
        }


neo4j_schema_manager = Neo4jSchemaManager()
