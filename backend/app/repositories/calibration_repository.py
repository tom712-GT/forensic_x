import json
from app.db.database import get_connection

class CalibrationRepository:
    
    @staticmethod
    def insert_and_supersede(reference_id, evidence_id, case_id, device_time, reference_time,
                             offset_seconds, uncertainty_seconds, note, flags, entered_at, entered_by):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE calibration_references
                SET superseded_at = ?, superseded_by = ?
                WHERE evidence_id = ? AND superseded_at IS NULL
            """, (entered_at, reference_id, evidence_id))
            
            cursor.execute("""
                INSERT INTO calibration_references (
                    reference_id, evidence_id, case_id, device_time, reference_time,
                    offset_seconds, uncertainty_seconds, note, flags, entered_at, entered_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (reference_id, evidence_id, case_id, device_time, reference_time,
                  offset_seconds, uncertainty_seconds, note, json.dumps(flags), entered_at, entered_by))

    @staticmethod
    def get_history(evidence_id: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM calibration_references
                WHERE evidence_id = ?
                ORDER BY rowid DESC
            """, (evidence_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_active_for_case(case_id: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM calibration_references
                WHERE case_id = ? AND superseded_at IS NULL
            """, (case_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
