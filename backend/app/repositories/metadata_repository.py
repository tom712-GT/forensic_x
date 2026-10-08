import sqlite3
import json
import uuid
from app.db.database import get_connection

class MetadataRepository:
    @staticmethod
    def upsert(subject_type: str, subject_id: str, case_id: str, container: str, parser_version: str, status: str, result_dict: dict, extracted_at: str) -> dict:
        result_text = json.dumps(result_dict, sort_keys=True)
        metadata_id = str(uuid.uuid4())
        
        with get_connection() as conn:
            conn.execute('''
                INSERT INTO metadata_extractions 
                (metadata_id, subject_type, subject_id, case_id, container, parser_version, status, result, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject_type, subject_id) DO UPDATE SET
                    case_id = excluded.case_id,
                    container = excluded.container,
                    parser_version = excluded.parser_version,
                    status = excluded.status,
                    result = excluded.result,
                    extracted_at = excluded.extracted_at
            ''', (metadata_id, subject_type, subject_id, case_id, container, parser_version, status, result_text, extracted_at))
            
        return MetadataRepository.get(subject_type, subject_id)

    @staticmethod
    def get(subject_type: str, subject_id: str):
        with get_connection() as conn:
            cursor = conn.execute('SELECT * FROM metadata_extractions WHERE subject_type = ? AND subject_id = ?', (subject_type, subject_id))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res['result'] = json.loads(res['result'])
            return res
