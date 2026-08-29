from typing import Optional
from pydantic import BaseModel


class Neo4jHealthCheck(BaseModel):
    """Pydantic model representing the result of a Neo4j connection health check."""
    status: str  # "UP", "DOWN", "UNAUTHENTICATED", "UNAVAILABLE"
    database: str
    uri: str
    server_version: Optional[str] = None
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None
