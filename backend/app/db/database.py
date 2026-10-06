import sqlite3
from pathlib import Path
from contextlib import contextmanager
import threading

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "db" / "forensic_x.db"
_schema_initialized = False
_schema_lock = threading.Lock()

def _init_schema(conn):
    global _schema_initialized
    if _schema_initialized:
        return
    with _schema_lock:
        if _schema_initialized:
            return
        cursor = conn.cursor()
        cursor.execute("PRAGMA user_version")
        version = cursor.fetchone()[0]
        
        if version == 0:
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
            
            cursor.execute("PRAGMA user_version = 1")
            
        if version < 2:
            cursor.execute("""
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
            """)
            
            # Basic protection, NOT tamper-proof (someone with the database file can drop the triggers)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS prevent_audit_log_update
                BEFORE UPDATE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'audit_log is append-only');
                END;
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS prevent_audit_log_delete
                BEFORE DELETE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'audit_log is append-only');
                END;
            """)
            
            cursor.execute("PRAGMA user_version = 2")
            
        if version < 3:
            try:
                cursor.execute("ALTER TABLE evidence ADD COLUMN filesystem_analysis TEXT")
            except sqlite3.OperationalError:
                pass
            cursor.execute("PRAGMA user_version = 3")
            
        if version < 4:
            cursor.execute("""
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
            """)
            cursor.execute("PRAGMA user_version = 4")
            
        if version < 5:
            try:
                cursor.execute("ALTER TABLE recovered_artifacts ADD COLUMN artifact_hash TEXT")
            except sqlite3.OperationalError:
                pass
            cursor.execute("PRAGMA user_version = 5")
            
        conn.commit()
        _schema_initialized = True

@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
