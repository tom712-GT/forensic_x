import pytest
import sqlite3
import json
from datetime import datetime, timezone
from app.db import database
from app.db.database import get_connection
from app.repositories.audit_repository import AuditRepository

def test_audit_schema_exists(tmp_path, monkeypatch):
    test_db = tmp_path / "test_audit_x.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database._schema_initialized = False
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        assert cursor.fetchone() is not None
        
        # Check triggers
        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='prevent_audit_log_update'")
        assert cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='prevent_audit_log_delete'")
        assert cursor.fetchone() is not None
        
        # Check version
        cursor.execute("PRAGMA user_version")
        assert cursor.fetchone()[0] == 2

def test_upgrade_from_v1(tmp_path, monkeypatch):
    test_db = tmp_path / "test_upgrade_x.db"
    
    # Create v1 DB manually
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            case_name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    cursor.execute("""
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
    """)
    cursor.execute("INSERT INTO cases (case_id, case_name, created_at, status) VALUES ('case-1', 'C1', '2023-01-01T00:00:00Z', 'OPEN')")
    cursor.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database._schema_initialized = False
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA user_version")
        assert cursor.fetchone()[0] == 2
        
        cursor.execute("SELECT case_name FROM cases WHERE case_id = 'case-1'")
        assert cursor.fetchone()[0] == 'C1'
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        assert cursor.fetchone() is not None

def test_audit_log_is_append_only(tmp_path, monkeypatch):
    test_db = tmp_path / "test_append_x.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database._schema_initialized = False
    
    AuditRepository.insert(
        timestamp="2023-01-01T00:00:00Z",
        action="CASE_CREATE",
        outcome="SUCCESS",
        http_status=201,
        actor="UNAUTHENTICATED",
        details={},
        case_id="case-xyz"
    )
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT audit_id FROM audit_log LIMIT 1")
        audit_id = cursor.fetchone()[0]
        
        with pytest.raises(sqlite3.DatabaseError) as exc_update:
            cursor.execute("UPDATE audit_log SET outcome = 'REJECTED' WHERE audit_id = ?", (audit_id,))
        print(f"\nUpdate Exception: {exc_update.type.__name__}")
        
        with pytest.raises(sqlite3.DatabaseError) as exc_delete:
            cursor.execute("DELETE FROM audit_log WHERE audit_id = ?", (audit_id,))
        print(f"\nDelete Exception: {exc_delete.type.__name__}")
        
        cursor.execute("SELECT outcome FROM audit_log WHERE audit_id = ?", (audit_id,))
        assert cursor.fetchone()[0] == 'SUCCESS'

def test_audit_insert_is_parameterized(tmp_path, monkeypatch):
    test_db = tmp_path / "test_param_x.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database._schema_initialized = False
    
    malicious_id = "x'; DROP TABLE audit_log;--"
    long_id = "x" * 300
    
    AuditRepository.insert(
        timestamp="2023-01-01T00:00:00Z",
        action="TEST", outcome="SUCCESS", http_status=200, actor="UNAUTHENTICATED", details={},
        evidence_id=malicious_id
    )
    
    AuditRepository.insert(
        timestamp="2023-01-01T00:00:00Z",
        action="TEST", outcome="SUCCESS", http_status=200, actor="UNAUTHENTICATED", details={},
        evidence_id=long_id
    )
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        assert cursor.fetchone() is not None
        
        cursor.execute("SELECT evidence_id FROM audit_log ORDER BY audit_id ASC")
        rows = cursor.fetchall()
        
        assert rows[0][0] == malicious_id
        assert rows[1][0] == "x" * 100
