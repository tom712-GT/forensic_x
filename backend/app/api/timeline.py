from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.schemas.timeline import TimelineResponse
from app.services.timeline_service import TimelineService
from app.repositories.timeline_repository import TimelineRepository
from app.forensic.timeline_builder import parse_timestamp, parse_to_datetime

router = APIRouter(tags=["timeline"])

@router.get("/api/cases/{case_id}/timeline", response_model=TimelineResponse)
def get_timeline(
    case_id: str,
    kind: Optional[str] = Query(None),
    time_source: Optional[str] = Query(None),
    evidence_id: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    if not TimelineRepository.case_exists(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
        
    kinds_list = None
    if kind is not None:
        kinds_list = [k.strip() for k in kind.split(",")]
        valid_kinds = {
            "EVIDENCE_REGISTERED", "EVIDENCE_INGESTED", "EVIDENCE_HASHED",
            "FORMAT_DETECTED", "VENDOR_DETECTED", "ACQUISITION_DECLARED",
            "METADATA_EXTRACTED", "CONTAINER_CREATION_TIME",
            "CONTAINER_MODIFICATION_TIME", "ARTIFACT_RECOVERED"
        }
        for k in kinds_list:
            if k not in valid_kinds:
                raise HTTPException(status_code=400, detail="Invalid kind")
                
    if time_source is not None:
        if time_source not in ("TOOL_CLOCK", "USER_DECLARED", "CONTAINER_CLAIM"):
            raise HTTPException(status_code=400, detail="Invalid time_source")
            
    parsed_start = None
    if start is not None:
        parsed_start, _ = parse_to_datetime(start)
        if parsed_start is None:
            raise HTTPException(status_code=400, detail="Invalid start")
            
    parsed_end = None
    if end is not None:
        parsed_end, _ = parse_to_datetime(end)
        if parsed_end is None:
            raise HTTPException(status_code=400, detail="Invalid end")
            
    if parsed_start is not None and parsed_end is not None:
        if parsed_start > parsed_end:
            raise HTTPException(status_code=400, detail="start must not be after end")
            
    return TimelineService.get_timeline(
        case_id=case_id,
        kinds=kinds_list,
        time_source=time_source,
        evidence_id=evidence_id,
        start=parsed_start,
        end=parsed_end,
        limit=limit,
        offset=offset
    )
