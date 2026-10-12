from typing import Any, Dict, List, Optional
from app.db.database import get_connection


class ReportRepository:
    @staticmethod
    def get_case(case_id: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT case_id, case_name, description, status, created_at
                FROM cases
                WHERE case_id = ?
                """,
                (case_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_case_evidence(case_id: str, limit: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT 
                    e.evidence_id,
                    e.evidence_type,
                    e.status,
                    e.file_size,
                    e.stored_size,
                    e.hash_algorithm,
                    e.sha256,
                    e.registered_at,
                    e.ingested_at,
                    e.hashed_at,
                    e.format_detection,
                    e.vendor_detection,
                    g.group_label,
                    m.status AS metadata_status,
                    CASE WHEN c.reference_id IS NOT NULL THEN 1 ELSE 0 END AS calibrated
                FROM evidence e
                LEFT JOIN evidence_groups g 
                    ON e.evidence_id = g.evidence_id
                LEFT JOIN metadata_extractions m 
                    ON m.subject_type = 'EVIDENCE' AND m.subject_id = e.evidence_id
                LEFT JOIN calibration_references c 
                    ON c.evidence_id = e.evidence_id AND c.superseded_at IS NULL
                WHERE e.case_id = ?
                ORDER BY e.rowid
                LIMIT ?
                """,
                (case_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_calibration_references(case_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT 
                    c.evidence_id,
                    c.reference_id,
                    c.offset_seconds,
                    c.uncertainty_seconds,
                    c.entered_at
                FROM calibration_references c
                JOIN evidence e 
                    ON c.evidence_id = e.evidence_id
                WHERE c.case_id = ? AND c.superseded_at IS NULL
                ORDER BY e.rowid
                """,
                (case_id,),
            ).fetchall()
            return [
                {
                    "evidence_id": r["evidence_id"],
                    "reference_id": r["reference_id"],
                    "offset_seconds": float(r["offset_seconds"]),
                    "uncertainty_seconds": float(r["uncertainty_seconds"]),
                    "entered_at": r["entered_at"],
                }
                for r in rows
            ]
