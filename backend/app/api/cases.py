from fastapi import APIRouter, HTTPException
from typing import List
from app.schemas.case import CaseCreate, CaseResponse
from app.services.case_service import CaseService

router = APIRouter(prefix="/api/cases", tags=["cases"])

@router.post("", response_model=CaseResponse, status_code=201)
def create_case(case_data: CaseCreate):
    """
    Create a new case.
    A case represents an investigation in FORENSIC-X.
    Evidence (like CCTV footage) will later be attached to this case.
    """
    new_case = CaseService.create_case(case_data)
    return new_case

@router.get("", response_model=List[CaseResponse])
def get_cases():
    """
    Retrieve all cases.
    """
    return CaseService.get_all_cases()

@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: str):
    """
    Retrieve a specific case by its ID.
    """
    case = CaseService.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case
