import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "S.I.R.I.S. — Smart Intelligence for Real Time Investigation Support"
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Supabase PostgreSQL Configuration
    DATABASE_URL: Optional[str] = None

    # Neo4j Configuration
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "siris_password"

    # Entity Resolution Scoring Weights
    PERSON_WEIGHT_NAME: float = 0.30
    PERSON_WEIGHT_PHONETIC: float = 0.15
    PERSON_WEIGHT_DOB: float = 0.20
    PERSON_WEIGHT_PHONE: float = 0.20
    PERSON_WEIGHT_VEHICLE: float = 0.10
    PERSON_WEIGHT_LOCATION: float = 0.05

    # Decision Thresholds
    THRESHOLD_HIGH_CONFIDENCE: float = 0.80
    THRESHOLD_POSSIBLE_MATCH: float = 0.55

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        url = self.DATABASE_URL or "postgresql://postgres:password@localhost:5432/postgres"
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
