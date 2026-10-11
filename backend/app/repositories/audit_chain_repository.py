from typing import Generator, Dict, Any
from app.db.database import get_connection


class AuditChainRepository:
    @staticmethod
    def iter_rows() -> Generator[Dict[str, Any], None, None]:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT audit_id, timestamp, action, outcome, http_status,
                       case_id, evidence_id, actor, details, prev_hash, row_hash
                FROM audit_log
                ORDER BY audit_id ASC
                """
            )
            for row in cursor:
                yield dict(row)

    @staticmethod
    def check_anchor(anchor_hash: str) -> Dict[str, Any]:
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT audit_id FROM audit_log WHERE row_hash = ? ORDER BY audit_id ASC LIMIT 1",
                (anchor_hash,),
            )
            row = cursor.fetchone()
            if row is None:
                return {
                    "matched": False,
                    "audit_id": None,
                    "rows_after_anchor": None,
                }
            matched_id = row[0]
            cursor_after = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE row_hash IS NOT NULL AND audit_id > ?",
                (matched_id,),
            )
            rows_after = cursor_after.fetchone()[0]
            return {
                "matched": True,
                "audit_id": matched_id,
                "rows_after_anchor": rows_after,
            }
