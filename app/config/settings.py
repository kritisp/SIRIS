import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "S.I.R.I.S. — Smart Intelligence for Real Time Investigation Support"
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # PostgreSQL Configuration
    POSTGRES_SERVER: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "siris_user"
    POSTGRES_PASSWORD: str = "siris_password"
    POSTGRES_DB: str = "siris_db"

    # Neo4j Configuration
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "siris_password"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
