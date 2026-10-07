from pathlib import Path
import app.services.evidence_service as evidence_svc
import app.services.recovery_service as recovery_service

def test_raw_storage_is_isolated(tmp_path):
    # Ensure RAW_STORAGE_ROOT is inside tmp_path (from pytest autouse fixture)
    assert str(tmp_path) in str(evidence_svc.RAW_STORAGE_ROOT)
    
    # Ensure it's not the real path
    real_path = Path("D:/FORENSIC-X/data/raw")
    assert evidence_svc.RAW_STORAGE_ROOT.resolve() != real_path.resolve()

def test_recovered_storage_is_isolated(tmp_path):
    assert recovery_service.RECOVERED_STORAGE_ROOT.is_relative_to(tmp_path)
