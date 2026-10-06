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
