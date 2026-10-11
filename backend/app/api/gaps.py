from typing import Optional
from fastapi import APIRouter, Query
from app.schemas.gaps import EvidenceGroupUpdate, EvidenceGroupResponse, GapsResponse
from app.services.gap_service import GapService

router = APIRouter()


@router.put("/api/evidence/{evidence_id}/group", response_model=EvidenceGroupResponse)
def set_evidence_group(evidence_id: str, data: EvidenceGroupUpdate):
    return GapService.set_group(evidence_id, data.group_label)


@router.get("/api/evidence/{evidence_id}/group", response_model=EvidenceGroupResponse)
def get_evidence_group(evidence_id: str):
    return GapService.get_group(evidence_id)


@router.get("/api/cases/{case_id}/gaps", response_model=GapsResponse)
def get_case_gaps(
    case_id: str,
    group: Optional[str] = Query(None),
    min_gap_seconds: float = Query(0.0, ge=0.0, le=31536000.0),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return GapService.get_gaps(
        case_id=case_id,
        group=group,
        min_gap_seconds=min_gap_seconds,
        limit=limit,
        offset=offset,
    )
