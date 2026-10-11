from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.schemas.calibration import CalibrationCreate, CalibrationRecord, CalibrationHistory, CalibratedTimelineResponse
from app.services.calibration_service import CalibrationService

router = APIRouter(tags=["calibration"])

@router.post("/api/evidence/{evidence_id}/calibration", response_model=CalibrationRecord, status_code=201)
def set_calibration(evidence_id: str, data: CalibrationCreate):
    return CalibrationService.set_calibration(evidence_id, data)

@router.get("/api/evidence/{evidence_id}/calibration", response_model=CalibrationHistory)
def get_calibration(evidence_id: str):
    return CalibrationService.get_calibration(evidence_id)

@router.get("/api/cases/{case_id}/calibrated-times", response_model=CalibratedTimelineResponse)
def get_calibrated_times(case_id: str, evidence_id: Optional[str] = Query(None)):
    return CalibrationService.get_calibrated_times(case_id, evidence_id)
