import pytest
import sqlite3
from app.db.database import get_connection
from app.repositories.metadata_repository import MetadataRepository

def test_metadata_repository_1_schema():
    with get_connection() as conn:
        cursor = conn.execute("PRAGMA user_version")
        version = cursor.fetchone()[0]
        assert version == 7
        
        cursor = conn.execute("PRAGMA table_info(metadata_extractions)")
        columns = {row['name'] for row in cursor.fetchall()}
        
        expected_columns = {
            'metadata_id', 'subject_type', 'subject_id', 'case_id', 
            'container', 'parser_version', 'status', 'result', 'extracted_at'
        }
        assert columns == expected_columns

def test_metadata_repository_2_upsert_get():
    res = MetadataRepository.upsert(
        subject_type="EVIDENCE",
        subject_id="ev_1",
        case_id="case_1",
        container="MP4",
        parser_version="1",
        status="OK",
        result_dict={"hello": "world"},
        extracted_at="2026-10-08T00:00:00Z"
    )
    assert res['result'] == {"hello": "world"}
    
    fetched = MetadataRepository.get("EVIDENCE", "ev_1")
    assert fetched['result'] == {"hello": "world"}

def test_metadata_repository_3_upsert_twice():
    MetadataRepository.upsert(
        subject_type="EVIDENCE",
        subject_id="ev_2",
        case_id="case_1",
        container="MP4",
        parser_version="1",
        status="OK",
        result_dict={"first": True},
        extracted_at="2026-10-08T00:00:00Z"
    )
    first_get = MetadataRepository.get("EVIDENCE", "ev_2")
    first_id = first_get['metadata_id']
    
    MetadataRepository.upsert(
        subject_type="EVIDENCE",
        subject_id="ev_2",
        case_id="case_2",
        container="MP4",
        parser_version="2",
        status="PARTIAL",
        result_dict={"second": True},
        extracted_at="2026-10-08T01:00:00Z"
    )
    second_get = MetadataRepository.get("EVIDENCE", "ev_2")
    assert second_get['metadata_id'] == first_id
    assert second_get['status'] == "PARTIAL"
    assert second_get['result'] == {"second": True}
    assert second_get['parser_version'] == "2"

def test_metadata_repository_4_two_subjects():
    MetadataRepository.upsert("EVIDENCE", "ev_3", "c", "MP4", "1", "OK", {}, "2026Z")
    MetadataRepository.upsert("EVIDENCE", "ev_4", "c", "MP4", "1", "OK", {}, "2026Z")
    
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM metadata_extractions WHERE subject_type='EVIDENCE' AND subject_id IN ('ev_3', 'ev_4')")
        assert cursor.fetchone()[0] == 2

def test_metadata_repository_5_unknown():
    assert MetadataRepository.get("EVIDENCE", "ev_unknown") is None

def test_metadata_repository_6_hostile_text():
    hostile = "'; DROP TABLE metadata_extractions;--"
    res = MetadataRepository.upsert(
        subject_type="EVIDENCE",
        subject_id="ev_hostile",
        case_id="case_1",
        container="MP4",
        parser_version="1",
        status="OK",
        result_dict={"evil": hostile},
        extracted_at="2026Z"
    )
    fetched = MetadataRepository.get("EVIDENCE", "ev_hostile")
    assert fetched['result']['evil'] == hostile
    
    # Verify table still exists
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM metadata_extractions")
        assert cursor.fetchone()[0] >= 1

def test_metadata_repository_7_upgrade(tmp_path, monkeypatch):
    from app.db import database
    import sqlite3
    
    db_path = tmp_path / "forensic_x.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database._schema_initialized = False
    
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                case_name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                description TEXT,
                source TEXT,
                acquisition_time TEXT,
                status TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                stored_size INTEGER,
                size_matches_declared INTEGER,
                ingested_at TEXT,
                stored_path TEXT,
                hash_algorithm TEXT,
                sha256 TEXT,
                hashed_at TEXT,
                format_detection TEXT,
                vendor_detection TEXT,
                FOREIGN KEY(case_id) REFERENCES cases(case_id)
            )
        ''')
        # Note: evidence created WITHOUT filesystem_analysis and WITHOUT artifact_hash
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                http_status INTEGER NOT NULL,
                case_id TEXT NULL,
                evidence_id TEXT NULL,
                actor TEXT NOT NULL DEFAULT 'UNAUTHENTICATED',
                details TEXT NOT NULL
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS recovered_artifacts (
                artifact_id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                source_offset INTEGER NOT NULL,
                recovered_size INTEGER NOT NULL,
                detected_type TEXT NOT NULL,
                recovery_timestamp TEXT NOT NULL,
                output_path TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
            )
        ''')
        
        conn.execute("INSERT INTO cases VALUES ('c1', 'n1', 'd1', 't1', 'OPEN')")
        conn.execute("INSERT INTO evidence VALUES ('e1', 'c1', 'f1', 't1', 1, 'd', 's', 'a', 's', 'r', 1, 1, 'i', 'p', 'h', 's', 'h', 'f', 'v')")
        conn.execute("INSERT INTO audit_log (timestamp, action, outcome, http_status, case_id, evidence_id, actor, details) VALUES ('t', 'a', 'o', 200, 'c', 'e', 'a', 'd')")
        conn.execute("INSERT INTO recovered_artifacts VALUES ('a1', 'e1', 'c1', 0, 1, 't', 't', 'p', 's')")
        
        conn.execute("PRAGMA user_version = 6")
        conn.commit()
        
    with database.get_connection() as conn:
        cursor = conn.execute("PRAGMA user_version")
        assert cursor.fetchone()[0] == 7
        
        cursor = conn.execute("PRAGMA table_info(metadata_extractions)")
        assert len(cursor.fetchall()) > 0
        
        cursor = conn.execute("SELECT * FROM cases")
        assert cursor.fetchone()['case_id'] == 'c1'
        
        cursor = conn.execute("SELECT * FROM evidence")
        assert cursor.fetchone()['evidence_id'] == 'e1'
        
        cursor = conn.execute("SELECT * FROM audit_log")
        assert cursor.fetchone()['action'] == 'a'
        
        cursor = conn.execute("SELECT * FROM recovered_artifacts")
        assert cursor.fetchone()['artifact_id'] == 'a1'
        
        cursor = conn.execute("PRAGMA table_info(evidence)")
        cols = {row['name'] for row in cursor.fetchall()}
        # The older steps (version < 3 and version < 5) DO NOT run when upgrading from version 6.
        # Therefore, filesystem_analysis is NOT added.
        assert 'filesystem_analysis' not in cols

def test_metadata_repository_8_older_tables():
    with get_connection() as conn:
        for table in ['cases', 'evidence', 'audit_log', 'recovered_artifacts']:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            assert len(cursor.fetchall()) > 0

