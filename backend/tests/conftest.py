import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import os
import app.services.case_service as case_svc
import app.services.evidence_service as evidence_service
import app.db.database as database
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, tmp_path):
    # Point raw storage to pytest's tmp_path
    monkeypatch.setattr(evidence_service, "RAW_STORAGE_ROOT", tmp_path / "raw")
    
    # Monkeypatch DB_PATH to tmp_path
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    
    # Reset schema initialized flag for isolated test db
    database._schema_initialized = False
    
    yield
