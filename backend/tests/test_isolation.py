from pathlib import Path
import app.services.evidence_service as evidence_svc

def test_raw_storage_is_isolated(tmp_path):
    # Ensure RAW_STORAGE_ROOT is inside tmp_path (from pytest autouse fixture)
    assert str(tmp_path) in str(evidence_svc.RAW_STORAGE_ROOT)
    
    # Ensure it's not the real path
    real_path = Path("D:/FORENSIC-X/data/raw")
    assert evidence_svc.RAW_STORAGE_ROOT.resolve() != real_path.resolve()
