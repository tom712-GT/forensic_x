from datetime import datetime
from typing import List, Optional
from app.models.case import Case
from app.db.database import get_connection

def _row_to_case(row) -> Case:
    return Case(
        case_id=row["case_id"],
        case_name=row["case_name"],
        description=row["description"],
        created_at=datetime.fromisoformat(row["created_at"]),
        status=row["status"]
    )

class CaseRepository:
    @staticmethod
    def insert(case: Case) -> Case:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO cases (case_id, case_name, description, created_at, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    case.case_id,
                    case.case_name,
                    case.description,
                    case.created_at.isoformat(),
                    case.status
                )
            )
        return case

    @staticmethod
    def get_all() -> List[Case]:
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM cases ORDER BY rowid")
            return [_row_to_case(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_id(case_id: str) -> Optional[Case]:
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
            row = cursor.fetchone()
            if row:
                return _row_to_case(row)
            return None
