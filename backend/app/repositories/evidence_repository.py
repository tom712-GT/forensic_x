from datetime import datetime
import json
from typing import List, Optional
from app.models.evidence import Evidence
from app.db.database import get_connection

def _row_to_evidence(row) -> Evidence:
    ev = Evidence(
        case_id=row["case_id"],
        original_filename=row["original_filename"],
        evidence_type=row["evidence_type"],
        file_size=row["file_size"],
        description=row["description"],
        source=row["source"],
        acquisition_time=datetime.fromisoformat(row["acquisition_time"]) if row["acquisition_time"] else None,
        evidence_id=row["evidence_id"],
        status=row["status"],
        registered_at=datetime.fromisoformat(row["registered_at"]),
        stored_size=row["stored_size"],
        size_matches_declared=bool(row["size_matches_declared"]) if row["size_matches_declared"] is not None else None,
        ingested_at=datetime.fromisoformat(row["ingested_at"]) if row["ingested_at"] else None,
        stored_path=row["stored_path"],
        hash_algorithm=row["hash_algorithm"],
        sha256=row["sha256"],
        hashed_at=datetime.fromisoformat(row["hashed_at"]) if row["hashed_at"] else None,
        format_detection=json.loads(row["format_detection"]) if row["format_detection"] else None,
        vendor_detection=json.loads(row["vendor_detection"]) if row["vendor_detection"] else None
    )
    return ev

class EvidenceRepository:
    @staticmethod
    def insert(evidence: Evidence) -> Evidence:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id, case_id, original_filename, evidence_type, file_size,
                    description, source, acquisition_time, status, registered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.evidence_id,
                    evidence.case_id,
                    evidence.original_filename,
                    evidence.evidence_type,
                    evidence.file_size,
                    evidence.description,
                    evidence.source,
                    evidence.acquisition_time.isoformat() if evidence.acquisition_time else None,
                    evidence.status,
                    evidence.registered_at.isoformat()
                )
            )
        return evidence

    @staticmethod
    def get_by_id(evidence_id: str) -> Optional[Evidence]:
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,))
            row = cursor.fetchone()
            if row:
                return _row_to_evidence(row)
            return None

    @staticmethod
    def get_by_case(case_id: str) -> List[Evidence]:
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM evidence WHERE case_id = ? ORDER BY rowid", (case_id,))
            return [_row_to_evidence(row) for row in cursor.fetchall()]

    @staticmethod
    def update_ingest(evidence_id: str, stored_size: int, size_matches_declared: bool, ingested_at: datetime, stored_path: str, status: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE evidence 
                SET stored_size = ?, size_matches_declared = ?, ingested_at = ?, stored_path = ?, status = ?
                WHERE evidence_id = ?
                """,
                (
                    stored_size,
                    1 if size_matches_declared else 0,
                    ingested_at.isoformat(),
                    stored_path,
                    status,
                    evidence_id
                )
            )

    @staticmethod
    def update_hash(evidence_id: str, sha256: str, hash_algorithm: str, hashed_at: datetime) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE evidence
                SET sha256 = ?, hash_algorithm = ?, hashed_at = ?, status = 'HASHED'
                WHERE evidence_id = ? AND sha256 IS NULL
                """,
                (
                    sha256,
                    hash_algorithm,
                    hashed_at.isoformat(),
                    evidence_id
                )
            )
            return cursor.rowcount > 0

    @staticmethod
    def update_format_detection(evidence_id: str, format_detection: dict) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE evidence
                SET format_detection = ?
                WHERE evidence_id = ?
                """,
                (
                    json.dumps(format_detection),
                    evidence_id
                )
            )

    @staticmethod
    def update_vendor_detection(evidence_id: str, vendor_detection: dict) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE evidence
                SET vendor_detection = ?
                WHERE evidence_id = ?
                """,
                (
                    json.dumps(vendor_detection),
                    evidence_id
                )
            )
