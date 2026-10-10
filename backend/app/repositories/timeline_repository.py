from app.db.database import get_connection

class TimelineRepository:
    @staticmethod
    def get_evidence(case_id: str, cap: int):
        with get_connection() as conn:
            # Need to fetch dictionaries
            conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
            c = conn.cursor()
            c.execute("""
                SELECT evidence_id, registered_at, ingested_at, hashed_at,
                       acquisition_time, format_detection, vendor_detection
                FROM evidence
                WHERE case_id = ?
                ORDER BY rowid LIMIT ?
            """, (case_id, cap + 1))
            return c.fetchall()

    @staticmethod
    def get_metadata(case_id: str, cap: int):
        with get_connection() as conn:
            conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
            c = conn.cursor()
            c.execute("""
                SELECT subject_id as evidence_id, result as result_dict, extracted_at
                FROM metadata_extractions
                WHERE case_id = ? AND subject_type = 'EVIDENCE'
                ORDER BY rowid LIMIT ?
            """, (case_id, cap + 1))
            return c.fetchall()

    @staticmethod
    def get_artifacts(case_id: str, cap: int):
        with get_connection() as conn:
            conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
            c = conn.cursor()
            c.execute("""
                SELECT evidence_id, artifact_id, detected_type, status, source_offset, recovery_timestamp
                FROM recovered_artifacts
                WHERE case_id = ?
                ORDER BY rowid LIMIT ?
            """, (case_id, cap + 1))
            return c.fetchall()

    @staticmethod
    def case_exists(case_id: str) -> bool:
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,))
            return c.fetchone() is not None
