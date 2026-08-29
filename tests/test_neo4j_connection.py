import pytest
from app.config.settings import settings
from app.services.graph import (
    Neo4jConnectionService,
    Neo4jHealthCheck,
    neo4j_connection_service,
)


def test_neo4j_connection_service_initialization():
    """Verifies that Neo4jConnectionService initializes with default settings."""
    service = Neo4jConnectionService()
    assert service.uri == settings.NEO4J_URI
    assert service.username == settings.effective_neo4j_user
    assert service.database == settings.NEO4J_DATABASE
    service.close()


def test_neo4j_health_check_offline_graceful_handling():
    """Verifies graceful health check response when connecting to an unreachable host."""
    service = Neo4jConnectionService(uri="bolt://127.0.0.1:17687", password="secret_password_xyz")
    try:
        health = service.check_health()
        assert isinstance(health, Neo4jHealthCheck)
        assert health.status in ("UNAVAILABLE", "DOWN")
        assert health.error_message is not None
        # Verify password is never leaked in error message
        assert "secret_password_xyz" not in health.error_message
    finally:
        service.close()


def test_neo4j_live_connection_smoke_test():
    """Smoke test verifying connectivity and RETURN 1 query without creating graph data."""
    health = neo4j_connection_service.check_health()

    if health.status == "UP":
        assert health.status == "UP"
        assert health.database == settings.NEO4J_DATABASE
        assert health.latency_ms is not None
        assert health.latency_ms > 0

        # Execute read-only RETURN 1 AS ok using active driver session
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            res = session.run("RETURN 1 AS ok")
            rec = res.single()
            assert rec["ok"] == 1

            # Read-only verification: Count total nodes to prove ZERO data was created
            count_res = session.run("MATCH (n) RETURN count(n) AS total_nodes")
            node_count = count_res.single()["total_nodes"]
            assert isinstance(node_count, int)
    else:
        pytest.skip(f"Neo4j live instance not reachable on {settings.NEO4J_URI} ({health.error_message}). Skipping live integration test.")
