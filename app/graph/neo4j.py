import logging
from typing import Optional
from neo4j import GraphDatabase, Driver
from app.config.settings import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self):
        self._driver: Optional[Driver] = None

    def connect(self) -> None:
        """Initialize the Neo4j driver connection."""
        if not self._driver:
            try:
                self._driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
                logger.info("Neo4j driver initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Neo4j driver: {e}")
                raise e

    def get_driver(self) -> Driver:
        """Retrieve active driver instance."""
        if not self._driver:
            self.connect()
        return self._driver

    def close(self) -> None:
        """Close driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j driver connection closed.")

    def check_connection(self) -> bool:
        """Verify Neo4j server connectivity."""
        try:
            driver = self.get_driver()
            driver.verify_connectivity()
            with driver.session() as session:
                result = session.run("RETURN 1 AS test")
                record = result.single()
                return record is not None and record["test"] == 1
        except Exception as e:
            logger.error(f"Neo4j connection check failed: {e}")
            return False


neo4j_client = Neo4jClient()


def check_neo4j_connection() -> bool:
    """Helper function to test Neo4j database health."""
    return neo4j_client.check_connection()
