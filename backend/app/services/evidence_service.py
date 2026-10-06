import os
import stat
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import UploadFile
from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceCreate
from app.services.case_service import CaseService
from app.forensic.format_detector import detect_format
from app.forensic.vendor_detector import detect_vendor
from app.repositories.evidence_repository import EvidenceRepository

class BaselineAlreadyExistsError(RuntimeError):
    pass

RAW_STORAGE_ROOT = Path(__file__).resolve().parents[3] / "data" / "raw"

class EvidenceService:
    HEADER_READ_BYTES = 4096
    @staticmethod
    def create_evidence(case_id: str, evidence_data: EvidenceCreate) -> Optional[Evidence]:
        """
        Creates new evidence metadata associated with a case.
        Returns None if the case does not exist.
        """
        # Verify case exists
        case = CaseService.get_case_by_id(case_id)
        if not case:
            return None
            
        new_evidence = Evidence(
            case_id=case_id,
            original_filename=evidence_data.original_filename,
            evidence_type=evidence_data.evidence_type,
            file_size=evidence_data.file_size,
            description=evidence_data.description,
            source=evidence_data.source,
            acquisition_time=evidence_data.acquisition_time
        )
        EvidenceRepository.insert(new_evidence)
        return new_evidence

    @staticmethod
    def get_evidence_by_id(evidence_id: str) -> Optional[Evidence]:
        """
        Retrieves a single piece of evidence by its ID.
        """
        return EvidenceRepository.get_by_id(evidence_id)

    @staticmethod
    def get_evidence_by_case(case_id: str) -> Optional[List[Evidence]]:
        """
        Retrieves all evidence associated with a case.
        Returns None if the case does not exist.
        """
        # Verify case exists
        case = CaseService.get_case_by_id(case_id)
        if not case:
            return None
            
        return EvidenceRepository.get_by_case(case_id)

    @staticmethod
    def ingest_evidence_file(evidence: Evidence, file: UploadFile, max_bytes: int) -> int:
        """
        Stores the uploaded original evidence file on disk.
        """
        # Originals are stored under server-generated names to prevent path traversal
        # and ensure a consistent, safe directory structure.
        raw_dir = RAW_STORAGE_ROOT / evidence.case_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = raw_dir / evidence.evidence_id
        
        bytes_written = 0
        created = False
        try:
            # Overwriting is refused to maintain the forensic principle that original evidence is never modified.
            with open(file_path, "xb") as f:
                created = True
                # Uploads are streamed in chunks so we don't exhaust server memory on large forensic files
                while True:
                    chunk = file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    
                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        raise ValueError("File too large")
                        
                    f.write(chunk)
            
            if bytes_written == 0:
                raise ValueError("Uploaded file is empty")
                
            # Read-only file permission is a basic protection against accidental modification.
            # It is NOT a hardware write blocker and NOT tamper-proof.
            # No hash exists yet, so integrity is not yet provable (hashing is next task).
            os.chmod(file_path, stat.S_IREAD)
            
            evidence.stored_size = bytes_written
            evidence.size_matches_declared = (bytes_written == evidence.file_size)
            evidence.ingested_at = datetime.now(timezone.utc)
            evidence.stored_path = str(file_path)
            evidence.status = "INGESTED"
            
            EvidenceRepository.update_ingest(
                evidence_id=evidence.evidence_id,
                stored_size=evidence.stored_size,
                size_matches_declared=evidence.size_matches_declared,
                ingested_at=evidence.ingested_at,
                stored_path=evidence.stored_path,
                status=evidence.status
            )
            
            return bytes_written
            
        except Exception as e:
            if created and file_path.exists():
                try:
                    # Windows might hold a lock, need to make sure file is writable to delete, or just try remove
                    os.chmod(file_path, stat.S_IWRITE)
                    os.remove(file_path)
                except:
                    pass
            raise e

    @staticmethod
    def _compute_sha256(file_path: str) -> str:
        """
        A hash is a fingerprint of the original evidence.
        Files are hashed in chunks to prevent memory exhaustion on large forensic images.
        """
        h = hashlib.sha256()
        # Open in read-binary mode ("rb") to ensure we only read and never modify the stored original.
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def hash_evidence(evidence: Evidence) -> None:
        """
        Computes the baseline hash of the evidence.
        The first hash is the baseline and must never be silently replaced.
        Hashing happens after ingestion as a separate step for now, but a later task can hash during receive.
        """
        if not evidence.stored_path or not os.path.exists(evidence.stored_path):
            raise FileNotFoundError("Stored evidence file missing")
            
        computed_hash = EvidenceService._compute_sha256(evidence.stored_path)
        
        hashed_at = datetime.now(timezone.utc)
        
        success = EvidenceRepository.update_hash(
            evidence_id=evidence.evidence_id,
            sha256=computed_hash,
            hash_algorithm="SHA-256",
            hashed_at=hashed_at
        )
        
        if success:
            evidence.sha256 = computed_hash
            evidence.hash_algorithm = "SHA-256"
            evidence.hashed_at = hashed_at
            evidence.status = "HASHED"
        else:
            raise BaselineAlreadyExistsError("Baseline hash already exists and cannot be overwritten")

    @staticmethod
    def verify_evidence(evidence: Evidence) -> dict:
        """
        Recomputes the hash and compares it with the stored baseline.
        Verify only reads and changes nothing. The baseline is never replaced.
        """
        if not evidence.stored_path or not os.path.exists(evidence.stored_path):
            raise FileNotFoundError("Stored evidence file missing")
            
        computed_hash = EvidenceService._compute_sha256(evidence.stored_path)
        
        return {
            "evidence_id": evidence.evidence_id,
            "hash_algorithm": evidence.hash_algorithm,
            "baseline_sha256": evidence.sha256,
            "computed_sha256": computed_hash,
            "match": computed_hash == evidence.sha256,
            "verified_at": datetime.now(timezone.utc)
        }

    @staticmethod
    def detect_evidence_format(evidence: Evidence) -> None:
        """
        Reads the first 4096 bytes and detects format.
        Does not change status, sha256, stored_size or file contents.
        """
        if not evidence.stored_path or not os.path.exists(evidence.stored_path):
            raise FileNotFoundError("Stored evidence file missing")
            
        with open(evidence.stored_path, "rb") as f:
            header = f.read(EvidenceService.HEADER_READ_BYTES)
            
        res = detect_format(header, evidence.original_filename)
        res["detected_at"] = datetime.now(timezone.utc).isoformat() # Convert to string if it isn't already, wait, it was originally just setting it to datetime.now
        # Actually in original code it was: res["detected_at"] = datetime.now(timezone.utc)
        # However, to JSON dump it properly, it needs to be a string. Let's ensure isoformat.
        res["detected_at"] = datetime.now(timezone.utc).isoformat()
        
        EvidenceRepository.update_format_detection(evidence.evidence_id, res)
        evidence.format_detection = res

    @staticmethod
    def detect_evidence_vendor(evidence: Evidence) -> None:
        """
        Reads the first 4096 bytes and detects vendor.
        Does not change status, sha256, stored_size or file contents.
        """
        if not evidence.stored_path or not os.path.exists(evidence.stored_path):
            raise FileNotFoundError("Stored evidence file missing")
            
        with open(evidence.stored_path, "rb") as f:
            header = f.read(EvidenceService.HEADER_READ_BYTES)
            
        res = detect_vendor(header, evidence.original_filename)
        res["detected_at"] = datetime.now(timezone.utc).isoformat()
        
        EvidenceRepository.update_vendor_detection(evidence.evidence_id, res)
        evidence.vendor_detection = res

    @staticmethod
    def analyze_evidence_filesystem(evidence: Evidence) -> None:
        """
        Reads the first 8192 bytes and detects filesystem/container.
        Does not change status, sha256, stored_size or file contents.
        """
        if not evidence.stored_path or not os.path.exists(evidence.stored_path):
            raise FileNotFoundError("Stored evidence file missing")
            
        with open(evidence.stored_path, "rb") as f:
            # Need at least 8192 for EXT4 which is at 1080 bytes offset
            header = f.read(8192)
            
        from app.forensic.filesystem_inspector import inspect_filesystem
        res = inspect_filesystem(header)
        res["detected_at"] = datetime.now(timezone.utc).isoformat()
        
        EvidenceRepository.update_filesystem_analysis(evidence.evidence_id, res)
        evidence.filesystem_analysis = res
