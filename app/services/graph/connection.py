import logging
import time
from typing import Optional
from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import AuthError, ServiceUnavailable, Neo4jError

from app.config.settings import settings
from app.services.graph.models import Neo4jHealthCheck

logger = logging.getLogger(__name__)


def _sanitize_error_message(err: Exception, password: Optional[str]) -> str:
    """Removes sensitive password strings from exception messages if present."""
    msg = str(err)
    if password and password.strip() and password in msg:
        msg = msg.replace(password, "******")
    return msg


class Neo4jConnectionService:
    """Reusable Neo4j Connection & Infrastructure Service for S.I.R.I.S. Central Intelligence Engine."""

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.uri = uri or settings.NEO4J_URI
        self.username = username or settings.effective_neo4j_user
        self.password = password if password is not None else settings.NEO4J_PASSWORD
        self.database = database or settings.NEO4J_DATABASE
        self._driver: Optional[Driver] = None

    def get_driver(self) -> Driver:
        """Returns the active Neo4j Driver instance for this service, initializing lazily if necessary."""
        if self._driver is None or self._driver._closed:
            try:
                auth = (self.username, self.password)
                self._driver = GraphDatabase.driver(
                    self.uri,
                    auth=auth,
                    max_connection_lifetime=3600,
                    max_connection_pool_size=50,
                )
                logger.info("Initialized Neo4j driver for URI: %s", self.uri)
            except Exception as e:
                sanitized_msg = _sanitize_error_message(e, self.password)
                logger.error("Failed to initialize Neo4j driver: %s", sanitized_msg)
                raise RuntimeError(f"Neo4j driver initialization failed: {sanitized_msg}") from None

        return self._driver

    def verify_connectivity(self) -> bool:
        """Verifies driver connectivity to the Neo4j database server."""
        try:
            driver = self.get_driver()
            driver.verify_connectivity()
            return True
        except Exception as e:
            sanitized_msg = _sanitize_error_message(e, self.password)
            logger.warning("Neo4j connectivity verification failed: %s", sanitized_msg)
            return False

    def check_health(self) -> Neo4jHealthCheck:
        """Executes a deterministic health check query (RETURN 1 AS ok) and retrieves server metadata."""
        start_time = time.time()
        masked_uri = self.uri

        try:
            driver = self.get_driver()
            driver.verify_connectivity()

            with driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS ok")
                record = result.single()

                if record and record["ok"] == 1:
                    latency = round((time.time() - start_time) * 1000, 2)
                    server_ver = None
                    try:
                        ver_res = session.run("CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition")
                        records = list(ver_res)
                        if records:
                            ver_rec = records[0]
                            server_ver = f"{ver_rec['name']} {ver_rec['versions'][0]} ({ver_rec['edition']})"
                    except Exception:
                        server_ver = "Neo4j Server"

                    return Neo4jHealthCheck(
                        status="UP",
                        database=self.database,
                        uri=masked_uri,
                        server_version=server_ver,
                        latency_ms=latency,
                        error_message=None,
                    )
                else:
                    return Neo4jHealthCheck(
                        status="DEGRADED",
                        database=self.database,
                        uri=masked_uri,
                        error_message="Unexpected query result from RETURN 1 AS ok",
                    )
        except AuthError as e:
            sanitized_msg = _sanitize_error_message(e, self.password)
            return Neo4jHealthCheck(
                status="UNAUTHENTICATED",
                database=self.database,
                uri=masked_uri,
                error_message=f"Authentication failed: {sanitized_msg}",
            )
        except ServiceUnavailable as e:
            sanitized_msg = _sanitize_error_message(e, self.password)
            return Neo4jHealthCheck(
                status="UNAVAILABLE",
                database=self.database,
                uri=masked_uri,
                error_message=f"Neo4j service unavailable: {sanitized_msg}",
            )
        except Exception as e:
            sanitized_msg = _sanitize_error_message(e, self.password)
            return Neo4jHealthCheck(
                status="DOWN",
                database=self.database,
                uri=masked_uri,
                error_message=f"Connection error: {sanitized_msg}",
            )

    def close(self) -> None:
        """Closes the active Neo4j driver connection pool for this service."""
        if self._driver and not self._driver._closed:
            try:
                self._driver.close()
                logger.info("Closed Neo4j driver connection pool.")
            except Exception as e:
                sanitized_msg = _sanitize_error_message(e, self.password)
                logger.warning("Error closing Neo4j driver: %s", sanitized_msg)
            finally:
                self._driver = None


neo4j_connection_service = Neo4jConnectionService()
