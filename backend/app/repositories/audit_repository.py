import json
import sqlite3
from typing import List, Optional, Dict, Any
from app.db.database import get_connection

class AuditRepository:
    @staticmethod
    def insert(
        timestamp: str,
        action: str,
        outcome: str,
        http_status: int,
        actor: str,
        details: Dict[str, Any],
        case_id: Optional[str] = None,
        evidence_id: Optional[str] = None
    ) -> None:
        """
        Inserts a new audit log entry.
        """
        # Truncate IDs to 100 chars
        if case_id:
            case_id = str(case_id)[:100]
        if evidence_id:
            evidence_id = str(evidence_id)[:100]
            
        details_json = json.dumps(details)
        
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_log (timestamp, action, outcome, http_status, case_id, evidence_id, actor, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, action, outcome, http_status, case_id, evidence_id, actor, details_json))
            
    @staticmethod
    def list_entries(
        case_id: Optional[str] = None,
        evidence_id: Optional[str] = None,
        limit: int = 100
    ) -> List[sqlite3.Row]:
        """
        Retrieves audit entries, ordered by audit_id ASC.
        """
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if case_id:
            query += " AND case_id = ?"
            params.append(case_id)
            
        if evidence_id:
            query += " AND evidence_id = ?"
            params.append(evidence_id)
            
        query += " ORDER BY audit_id ASC LIMIT ?"
        params.append(limit)
        
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
