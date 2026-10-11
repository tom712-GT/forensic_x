from typing import Optional
from fastapi import APIRouter, Query
from app.schemas.correlation import CorrelationResponse
from app.services.correlation_service import CorrelationService

router = APIRouter()


@router.get("/api/cases/{case_id}/correlation", response_model=CorrelationResponse)
def get_case_correlation(
    case_id: str,
    groups: Optional[str] = Query(None),
    min_overlap_seconds: float = Query(0.0, ge=0.0, le=31536000.0),
    min_groups: int = Query(2, ge=2, le=50),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return CorrelationService.get_correlation(
        case_id=case_id,
        groups=groups,
        min_overlap_seconds=min_overlap_seconds,
        min_groups=min_groups,
        limit=limit,
        offset=offset,
    )
