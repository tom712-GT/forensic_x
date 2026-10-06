from fastapi import APIRouter, HTTPException, status, UploadFile, File
from typing import List
import logging
from app.schemas.evidence import EvidenceCreate, EvidenceResponse, EvidenceVerifyResponse
from app.services.evidence_service import EvidenceService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evidence"])

@router.post("/api/cases/{case_id}/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
def register_evidence(case_id: str, evidence_data: EvidenceCreate):
    """
    Register evidence metadata against an existing case.
    """
    new_evidence = EvidenceService.create_evidence(case_id, evidence_data)
    if not new_evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return new_evidence

@router.get("/api/cases/{case_id}/evidence", response_model=List[EvidenceResponse])
def get_case_evidence(case_id: str):
    """
    Return all evidence registered against a case.
    """
    evidence_list = EvidenceService.get_evidence_by_case(case_id)
    if evidence_list is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return evidence_list

@router.get("/api/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(evidence_id: str):
    """
    Return one evidence record.
    """
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return evidence

# Temporary development limit
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

@router.post("/api/evidence/{evidence_id}/file", response_model=EvidenceResponse)
def ingest_evidence(evidence_id: str, file: UploadFile = File(...)):
    """
    Upload the actual original evidence file.
    """
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    if evidence.status != "REGISTERED":
        raise HTTPException(status_code=409, detail="Evidence already ingested")
        
    try:
        EvidenceService.ingest_evidence_file(evidence, file, MAX_UPLOAD_BYTES)
    except ValueError as e:
        if str(e) == "File too large":
            raise HTTPException(status_code=413, detail="File too large")
        if str(e) == "Uploaded file is empty":
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        logger.exception("Unexpected ValueError during ingest")
        raise HTTPException(status_code=500, detail="Internal error while storing evidence")
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Evidence already ingested")
    except Exception as e:
        logger.exception("Unexpected exception during ingest")
        raise HTTPException(status_code=500, detail="Internal error while storing evidence")
        
    return evidence

@router.post("/api/evidence/{evidence_id}/hash", response_model=EvidenceResponse)
def hash_evidence(evidence_id: str):
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    if evidence.status == "REGISTERED":
        raise HTTPException(status_code=409, detail="Evidence must be ingested before hashing")
        
    if evidence.status == "HASHED":
        raise HTTPException(status_code=409, detail="Evidence already hashed")
        
    try:
        EvidenceService.hash_evidence(evidence)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Stored evidence file missing")
    except RuntimeError as e:
        if "already exists" in str(e) or "already hashed" in str(e):
            raise HTTPException(status_code=409, detail="Evidence already hashed")
        raise HTTPException(status_code=500, detail=str(e))
        
    return evidence

@router.post("/api/evidence/{evidence_id}/verify", response_model=EvidenceVerifyResponse)
def verify_evidence(evidence_id: str):
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    if evidence.status != "HASHED":
        raise HTTPException(status_code=409, detail="Evidence has not been hashed yet")
        
    try:
        result = EvidenceService.verify_evidence(evidence)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Stored evidence file missing")
        
    return result

@router.post("/api/evidence/{evidence_id}/detect-format", response_model=EvidenceResponse)
def detect_format_endpoint(evidence_id: str):
    """
    Detects the file format of the evidence by reading its header.
    Allowed when status is INGESTED or HASHED.
    """
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    if evidence.status == "REGISTERED":
        raise HTTPException(status_code=409, detail="Evidence must be ingested before format detection")
        
    try:
        EvidenceService.detect_evidence_format(evidence)
        return evidence
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Stored evidence file missing")

@router.post("/api/evidence/{evidence_id}/detect-vendor", response_model=EvidenceResponse)
def detect_vendor_endpoint(evidence_id: str):
    """
    Detects the vendor of the evidence by reading its header.
    Allowed when status is INGESTED or HASHED.
    """
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    if evidence.status == "REGISTERED":
        raise HTTPException(status_code=409, detail="Evidence must be ingested before vendor detection")
        
    try:
        EvidenceService.detect_evidence_vendor(evidence)
        return evidence
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Stored evidence file missing")
