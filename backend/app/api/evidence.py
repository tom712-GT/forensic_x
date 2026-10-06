from fastapi import APIRouter, HTTPException, status, UploadFile, File
from typing import List
import logging
from app.schemas.evidence import EvidenceCreate, EvidenceResponse, EvidenceVerifyResponse
from app.services.evidence_service import EvidenceService, BaselineAlreadyExistsError
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evidence"])

def _audit(action: str, outcome: str, http_status: int, case_id: str = None, evidence_id: str = None, details: dict = None):
    AuditService.record(
        action=action,
        outcome=outcome,
        http_status=http_status,
        case_id=case_id,
        evidence_id=evidence_id,
        details=details
    )

def _raise_audit(action: str, outcome: str, status_code: int, reason: str, case_id: str = None, evidence_id: str = None, detail_msg: str = None):
    _audit(action, outcome, status_code, case_id, evidence_id, {"reason": reason})
    raise HTTPException(status_code=status_code, detail=detail_msg or reason)

@router.post("/api/cases/{case_id}/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
def register_evidence(case_id: str, evidence_data: EvidenceCreate):
    """
    Register evidence metadata against an existing case.
    """
    new_evidence = EvidenceService.create_evidence(case_id, evidence_data)
    if not new_evidence:
        _raise_audit("EVIDENCE_REGISTER", "NOT_FOUND", 404, "UNKNOWN_CASE", case_id=case_id, detail_msg="Case not found")
    _audit("EVIDENCE_REGISTER", "SUCCESS", 201, case_id=case_id, evidence_id=new_evidence.evidence_id, details={})
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
        _raise_audit("EVIDENCE_INGEST", "NOT_FOUND", 404, "UNKNOWN_EVIDENCE", evidence_id=evidence_id, detail_msg="Evidence not found")
        
    case_id = evidence.case_id
    if evidence.status != "REGISTERED":
        _raise_audit("EVIDENCE_INGEST", "REJECTED", 409, "ALREADY_INGESTED", case_id=case_id, evidence_id=evidence_id, detail_msg="Evidence already ingested")
        
    try:
        EvidenceService.ingest_evidence_file(evidence, file, MAX_UPLOAD_BYTES)
    except ValueError as e:
        if str(e) == "File too large":
            _raise_audit("EVIDENCE_INGEST", "REJECTED", 413, "FILE_TOO_LARGE", case_id=case_id, evidence_id=evidence_id, detail_msg="File too large")
        if str(e) == "Uploaded file is empty":
            _raise_audit("EVIDENCE_INGEST", "REJECTED", 400, "EMPTY_FILE", case_id=case_id, evidence_id=evidence_id, detail_msg="Uploaded file is empty")
        logger.exception("Unexpected ValueError during ingest")
        _raise_audit("EVIDENCE_INGEST", "ERROR", 500, "INTERNAL_ERROR", case_id=case_id, evidence_id=evidence_id, detail_msg="Internal error while storing evidence")
    except FileExistsError:
        _raise_audit("EVIDENCE_INGEST", "REJECTED", 409, "ALREADY_INGESTED", case_id=case_id, evidence_id=evidence_id, detail_msg="Evidence already ingested")
    except Exception:
        logger.exception("Unexpected exception during ingest")
        _raise_audit("EVIDENCE_INGEST", "ERROR", 500, "INTERNAL_ERROR", case_id=case_id, evidence_id=evidence_id, detail_msg="Internal error while storing evidence")
        
    _audit("EVIDENCE_INGEST", "SUCCESS", 200, case_id=case_id, evidence_id=evidence_id, details={
        "stored_size": evidence.stored_size,
        "size_matches_declared": evidence.size_matches_declared
    })
    return evidence

@router.post("/api/evidence/{evidence_id}/hash", response_model=EvidenceResponse)
def hash_evidence(evidence_id: str):
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        _raise_audit("EVIDENCE_HASH", "NOT_FOUND", 404, "UNKNOWN_EVIDENCE", evidence_id=evidence_id, detail_msg="Evidence not found")
        
    case_id = evidence.case_id
    if evidence.status == "REGISTERED":
        _raise_audit("EVIDENCE_HASH", "REJECTED", 409, "NOT_INGESTED", case_id=case_id, evidence_id=evidence_id, detail_msg="Evidence must be ingested before hashing")
        
    if evidence.status == "HASHED":
        _raise_audit("EVIDENCE_HASH", "REJECTED", 409, "ALREADY_HASHED", case_id=case_id, evidence_id=evidence_id, detail_msg="Evidence already hashed")
        
    try:
        EvidenceService.hash_evidence(evidence)
    except FileNotFoundError:
        _raise_audit("EVIDENCE_HASH", "NOT_FOUND", 404, "STORED_FILE_MISSING", case_id=case_id, evidence_id=evidence_id, detail_msg="Stored evidence file missing")
    except BaselineAlreadyExistsError:
        _raise_audit("EVIDENCE_HASH", "REJECTED", 409, "ALREADY_HASHED", case_id=case_id, evidence_id=evidence_id, detail_msg="Evidence already hashed")
    except Exception:
        logger.exception("Unexpected exception during hash")
        _raise_audit("EVIDENCE_HASH", "ERROR", 500, "INTERNAL_ERROR", case_id=case_id, evidence_id=evidence_id, detail_msg="Internal error while hashing evidence")
        
    _audit("EVIDENCE_HASH", "SUCCESS", 200, case_id=case_id, evidence_id=evidence_id, details={
        "hash_algorithm": "SHA-256",
        "sha256": evidence.sha256
    })
    return evidence

@router.post("/api/evidence/{evidence_id}/verify", response_model=EvidenceVerifyResponse)
def verify_evidence(evidence_id: str):
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        _raise_audit("EVIDENCE_VERIFY", "NOT_FOUND", 404, "UNKNOWN_EVIDENCE", evidence_id=evidence_id, detail_msg="Evidence not found")
        
    case_id = evidence.case_id
    if evidence.status != "HASHED":
        _raise_audit("EVIDENCE_VERIFY", "REJECTED", 409, "NOT_HASHED", case_id=case_id, evidence_id=evidence_id, detail_msg="Evidence has not been hashed yet")
        
    try:
        result = EvidenceService.verify_evidence(evidence)
    except FileNotFoundError:
        _raise_audit("EVIDENCE_VERIFY", "NOT_FOUND", 404, "STORED_FILE_MISSING", case_id=case_id, evidence_id=evidence_id, detail_msg="Stored evidence file missing")
        
    outcome = "SUCCESS" if result["match"] else "INTEGRITY_FAILURE"
    _audit("EVIDENCE_VERIFY", outcome, 200, case_id=case_id, evidence_id=evidence_id, details={
        "baseline_sha256": result["baseline_sha256"],
        "computed_sha256": result["computed_sha256"],
        "match": result["match"]
    })
    return result

@router.post("/api/evidence/{evidence_id}/detect-format", response_model=EvidenceResponse)
def detect_format_endpoint(evidence_id: str):
    """
    Detects the file format of the evidence by reading its header.
    Allowed when status is INGESTED or HASHED.
    """
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        _raise_audit("FORMAT_DETECT", "NOT_FOUND", 404, "UNKNOWN_EVIDENCE", evidence_id=evidence_id, detail_msg="Evidence not found")
        
    case_id = evidence.case_id
    if evidence.status == "REGISTERED":
        _raise_audit("FORMAT_DETECT", "REJECTED", 409, "NOT_INGESTED", case_id=case_id, evidence_id=evidence_id, detail_msg="Evidence must be ingested before format detection")
        
    try:
        EvidenceService.detect_evidence_format(evidence)
        _audit("FORMAT_DETECT", "SUCCESS", 200, case_id=case_id, evidence_id=evidence_id, details={
            "detected_format": evidence.format_detection["detected_format"],
            "confidence": evidence.format_detection["confidence"]
        })
        return evidence
    except FileNotFoundError:
        _raise_audit("FORMAT_DETECT", "NOT_FOUND", 404, "STORED_FILE_MISSING", case_id=case_id, evidence_id=evidence_id, detail_msg="Stored evidence file missing")

@router.post("/api/evidence/{evidence_id}/detect-vendor", response_model=EvidenceResponse)
def detect_vendor_endpoint(evidence_id: str):
    """
    Detects the vendor of the evidence by reading its header.
    Allowed when status is INGESTED or HASHED.
    """
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        _raise_audit("VENDOR_DETECT", "NOT_FOUND", 404, "UNKNOWN_EVIDENCE", evidence_id=evidence_id, detail_msg="Evidence not found")
        
    case_id = evidence.case_id
    if evidence.status == "REGISTERED":
        _raise_audit("VENDOR_DETECT", "REJECTED", 409, "NOT_INGESTED", case_id=case_id, evidence_id=evidence_id, detail_msg="Evidence must be ingested before vendor detection")
        
    try:
        EvidenceService.detect_evidence_vendor(evidence)
        
        details = {
            "vendor": evidence.vendor_detection["vendor"],
            "confidence": evidence.vendor_detection["confidence"]
        }
        if "conflict" in evidence.vendor_detection:
            details["conflict"] = evidence.vendor_detection["conflict"]
            
        _audit("VENDOR_DETECT", "SUCCESS", 200, case_id=case_id, evidence_id=evidence_id, details=details)
        return evidence
    except FileNotFoundError:
        _raise_audit("VENDOR_DETECT", "NOT_FOUND", 404, "STORED_FILE_MISSING", case_id=case_id, evidence_id=evidence_id, detail_msg="Stored evidence file missing")

@router.post("/api/evidence/{evidence_id}/analyze-filesystem", response_model=EvidenceResponse)
def analyze_filesystem_endpoint(evidence_id: str):
    """
    Analyzes the filesystem/container of the evidence by reading its header.
    Allowed when status is INGESTED or HASHED.
    """
    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence:
        _raise_audit("FILESYSTEM_ANALYZE", "NOT_FOUND", 404, "UNKNOWN_EVIDENCE", evidence_id=evidence_id, detail_msg="Evidence not found")
        
    case_id = evidence.case_id
    if evidence.status == "REGISTERED":
        _raise_audit("FILESYSTEM_ANALYZE", "REJECTED", 409, "NOT_INGESTED", case_id=case_id, evidence_id=evidence_id, detail_msg="Evidence must be ingested before filesystem analysis")
        
    try:
        EvidenceService.analyze_evidence_filesystem(evidence)
        
        details = {
            "container_type": evidence.filesystem_analysis["container_type"],
            "filesystem_type": evidence.filesystem_analysis["filesystem_type"],
            "status": evidence.filesystem_analysis["status"]
        }
            
        _audit("FILESYSTEM_ANALYZE", "SUCCESS", 200, case_id=case_id, evidence_id=evidence_id, details=details)
        return evidence
    except FileNotFoundError:
        _raise_audit("FILESYSTEM_ANALYZE", "NOT_FOUND", 404, "STORED_FILE_MISSING", case_id=case_id, evidence_id=evidence_id, detail_msg="Stored evidence file missing")
    except Exception:
        logger.exception("Unexpected exception during filesystem analysis")
        _raise_audit("FILESYSTEM_ANALYZE", "ERROR", 500, "INTERNAL_ERROR", case_id=case_id, evidence_id=evidence_id, detail_msg="Internal error while analyzing filesystem")
