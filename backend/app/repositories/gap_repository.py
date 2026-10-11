from app.db.database import get_connection


class GapRepository:

    @staticmethod
    def set_evidence_group(evidence_id: str, case_id: str, group_label: str, set_at: str, set_by: str = "UNAUTHENTICATED"):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO evidence_groups (evidence_id, case_id, group_label, set_at, set_by)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET
                    case_id = excluded.case_id,
                    group_label = excluded.group_label,
                    set_at = excluded.set_at,
                    set_by = excluded.set_by
            """, (evidence_id, case_id, group_label, set_at, set_by))

    @staticmethod
    def get_evidence_group(evidence_id: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT evidence_id, case_id, group_label, set_at, set_by
                FROM evidence_groups
                WHERE evidence_id = ?
            """, (evidence_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_case_evidence_ids(case_id: str, limit: int):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT evidence_id
                FROM evidence
                WHERE case_id = ?
                ORDER BY rowid
                LIMIT ?
            """, (case_id, limit))
            rows = cursor.fetchall()
            return [r["evidence_id"] for r in rows]

    @staticmethod
    def get_case_evidence_groups(case_id: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT evidence_id, group_label
                FROM evidence_groups
                WHERE case_id = ?
            """, (case_id,))
            rows = cursor.fetchall()
            return {r["evidence_id"]: r["group_label"] for r in rows}

    @staticmethod
    def get_case_metadata_extractions(case_id: str, limit: int):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT subject_id, result
                FROM metadata_extractions
                WHERE subject_type = 'EVIDENCE' AND case_id = ?
                ORDER BY rowid
                LIMIT ?
            """, (case_id, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
