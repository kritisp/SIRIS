from datetime import datetime
from pydantic import BaseModel, Field


class DatabaseStatus(BaseModel):
    postgres: str = Field(..., description="PostgreSQL database status ('healthy' or 'unhealthy')")
    neo4j: str = Field(..., description="Neo4j graph database status ('healthy' or 'unhealthy')")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall system status ('ok' or 'degraded')")
    app_name: str = Field(..., description="Application name")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of the health check")
    databases: DatabaseStatus = Field(..., description="Status breakdown of database connections")
