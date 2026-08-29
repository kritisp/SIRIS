import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.postgres import get_db
from app.schemas.intelligence import (
    IntelligenceAnalysisRequest,
    IntelligenceAnalysisResponse,
)
from app.services.intelligence_orchestration_service import (
    intelligence_orchestration_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/analyze",
    response_model=IntelligenceAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Central Intelligence Engine Analysis",
    description=(
        "Executes the full S.I.R.I.S. Central Intelligence Engine (Steps 3A through 8) "
        "across PostgreSQL case data and live Neo4j graph analytics. "
        "Performs entity resolution, relationship confidence scoring, multi-hop graph traversal, "
        "network analytics, community detection, pattern intelligence, explainability, "
        "PII privacy de-identification, LLM reasoning, post-LLM security scanning, "
        "and PII back-mapping before returning authorized police-facing intelligence."
    ),
    responses={
        200: {"description": "Intelligence report and multi-hop paths successfully generated."},
        400: {"description": "Invalid input parameters or analytical scope."},
        422: {"description": "Validation error in request payload parameters."},
        500: {"description": "Internal error during intelligence engine execution."},
    },
)
def analyze_intelligence(
    request: IntelligenceAnalysisRequest,
    db: Session = Depends(get_db),
) -> IntelligenceAnalysisResponse:
    """Primary FastAPI endpoint exposing the Central Intelligence Engine."""
    try:
        response = intelligence_orchestration_service.analyze(request, db_session=db)
        return response
    except ValueError as ve:
        logger.warning(f"Validation error in intelligence analysis request: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as exc:
        logger.error(f"Error executing intelligence engine: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intelligence engine execution failed: {str(exc)}",
        )
