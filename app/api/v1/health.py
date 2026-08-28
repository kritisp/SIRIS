from fastapi import APIRouter, status, Response
from app.config.settings import settings
from app.database.postgres import check_postgres_connection
from app.graph.neo4j import check_neo4j_connection
from app.schemas.health import HealthResponse, DatabaseStatus

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health Check",
    description="Returns overall system operational status and checks connectivity for PostgreSQL and Neo4j databases."
)
def get_health(response: Response):
    postgres_healthy = check_postgres_connection()
    neo4j_healthy = check_neo4j_connection()

    postgres_status = "healthy" if postgres_healthy else "unhealthy"
    neo4j_status = "healthy" if neo4j_healthy else "unhealthy"

    overall_healthy = postgres_healthy and neo4j_healthy
    overall_status = "ok" if overall_healthy else "degraded"

    if not overall_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        app_name=settings.PROJECT_NAME,
        databases=DatabaseStatus(
            postgres=postgres_status,
            neo4j=neo4j_status
        )
    )
