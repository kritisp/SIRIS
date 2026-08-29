import os
from typing import Optional, List
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
    NEO4J_URI: str = "bolt://127.0.0.1:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"

    @property
    def effective_neo4j_user(self) -> str:
        return self.NEO4J_USERNAME or self.NEO4J_USER or "neo4j"

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

    # Step 4B Case Similarity Weights
    SIM_WEIGHT_MO_TEXT: float = 0.25
    SIM_WEIGHT_CRIME_CATEGORY: float = 0.15
    SIM_WEIGHT_LEGAL_SECTIONS: float = 0.10
    SIM_WEIGHT_GEOGRAPHIC: float = 0.15
    SIM_WEIGHT_TEMPORAL: float = 0.10
    SIM_WEIGHT_PERSON_OVERLAP: float = 0.15
    SIM_WEIGHT_VEHICLE_OVERLAP: float = 0.05
    SIM_WEIGHT_PHONE_OVERLAP: float = 0.05

    # Case Similarity Decay Constants & Thresholds
    GEO_DECAY_KM: float = 10.0
    TEMPORAL_DECAY_DAYS: float = 30.0
    THRESHOLD_HIGH_SIMILARITY: float = 0.75
    THRESHOLD_MODERATE_SIMILARITY: float = 0.50

    # Step 5B Evidentiary Contribution Weights
    REL_WEIGHT_SHARED_HIGH_CONFIDENCE_PERSON: float = 1.00
    REL_WEIGHT_SHARED_PHONE: float = 0.90
    REL_WEIGHT_SHARED_VEHICLE: float = 0.85
    REL_WEIGHT_SHARED_LOCATION: float = 0.50
    REL_WEIGHT_SIMILAR_MODUS_OPERANDI: float = 0.60
    REL_WEIGHT_SIMILAR_CRIME_CATEGORY: float = 0.25
    REL_WEIGHT_SIMILAR_LEGAL_SECTIONS: float = 0.15
    REL_WEIGHT_TEMPORAL_PROXIMITY: float = 0.35
    REL_WEIGHT_POSSIBLE_PERSON_RELATIONSHIP: float = 0.45

    # Step 5B Relationship Confidence Thresholds
    REL_THRESH_VERY_HIGH: float = 0.85
    REL_THRESH_HIGH: float = 0.70
    REL_THRESH_MODERATE: float = 0.50
    REL_THRESH_LOW: float = 0.25

    # Step 8 LLM Reasoning Layer Configuration
    LLM_PRIMARY_PROVIDER: str = "groq"
    LLM_FALLBACK_PROVIDER: str = "cerebras"
    LLM_LOCAL_PROVIDER: str = "ollama"
    GROQ_API_KEY: Optional[str] = None
    GROQ_API_KEYS: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    CEREBRAS_API_KEY: Optional[str] = None
    CEREBRAS_MODEL: str = "gpt-oss-120b"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3:latest"
    LLM_TEMPERATURE: float = 0.0
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 2

    @property
    def effective_groq_api_keys(self) -> List[str]:
        keys: List[str] = []
        if self.GROQ_API_KEYS:
            keys.extend([k.strip() for k in self.GROQ_API_KEYS.split(",") if k.strip()])
        if self.GROQ_API_KEY and self.GROQ_API_KEY.strip() not in keys:
            keys.append(self.GROQ_API_KEY.strip())
        return keys

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
