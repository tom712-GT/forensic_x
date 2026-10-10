import pytest
from app.services.timeline_service import TimelineService
from app.forensic.timeline_builder import build_event_id, parse_to_datetime
import app.services.timeline_service as ts_module
import json

def test_m6_m13_row_cap_truncation(monkeypatch):
    monkeypatch.setattr(ts_module, "TIMELINE_MAX_ROWS", 2)
    
    def fake_get_evidence(cid, cap):
        # cap should be TIMELINE_MAX_ROWS
        # If the code incorrectly passes 1000000 instead of TIMELINE_MAX_ROWS, it fails.
        # If it returns cap+1 it should set truncated to True.
        assert cap == 2
        return [
            {"evidence_id": "e1", "registered_at": "2026-01-01T00:00:00Z", "ingested_at": "2026-01-01T00:00:00Z", "hashed_at": "2026-01-01T00:00:00Z", "acquisition_time": None, "format_detection": None, "vendor_detection": None},
            {"evidence_id": "e2", "registered_at": "2026-01-01T00:00:00Z", "ingested_at": "2026-01-01T00:00:00Z", "hashed_at": "2026-01-01T00:00:00Z", "acquisition_time": None, "format_detection": None, "vendor_detection": None},
            {"evidence_id": "e3", "registered_at": "2026-01-01T00:00:00Z", "ingested_at": "2026-01-01T00:00:00Z", "hashed_at": "2026-01-01T00:00:00Z", "acquisition_time": None, "format_detection": None, "vendor_detection": None}
        ]

    def fake_get_metadata(cid, cap):
        return []

    def fake_get_artifacts(cid, cap):
        return []

    from app.repositories.timeline_repository import TimelineRepository
    monkeypatch.setattr(TimelineRepository, "get_evidence", fake_get_evidence)
    monkeypatch.setattr(TimelineRepository, "get_metadata", fake_get_metadata)
    monkeypatch.setattr(TimelineRepository, "get_artifacts", fake_get_artifacts)
    
    r = TimelineService.get_timeline("c1", None, None, None, None, None, limit=10, offset=0)
    assert r["summary"]["truncated"] is True
    # cap is 2, so evidence rows is sliced to 2. Each has 3 events (reg, ing, hash) => 6 events
    assert r["summary"]["event_count"] == 6

def test_m13_exact_cap(monkeypatch):
    monkeypatch.setattr(ts_module, "TIMELINE_MAX_ROWS", 2)
    def fake_get_evidence(cid, cap):
        # exactly cap
        return [
            {"evidence_id": "e1", "registered_at": "2026-01-01T00:00:00Z", "ingested_at": "2026-01-01T00:00:00Z", "hashed_at": "2026-01-01T00:00:00Z", "acquisition_time": None, "format_detection": None, "vendor_detection": None},
            {"evidence_id": "e2", "registered_at": "2026-01-01T00:00:00Z", "ingested_at": "2026-01-01T00:00:00Z", "hashed_at": "2026-01-01T00:00:00Z", "acquisition_time": None, "format_detection": None, "vendor_detection": None}
        ]
    def fake_get_metadata(cid, cap): return []
    def fake_get_artifacts(cid, cap): return []
    
    from app.repositories.timeline_repository import TimelineRepository
    monkeypatch.setattr(TimelineRepository, "get_evidence", fake_get_evidence)
    monkeypatch.setattr(TimelineRepository, "get_metadata", fake_get_metadata)
    monkeypatch.setattr(TimelineRepository, "get_artifacts", fake_get_artifacts)
    
    r = TimelineService.get_timeline("c1", None, None, None, None, None, limit=10, offset=0)
    assert r["summary"]["truncated"] is False

def test_m12_different_event_ids_for_same_field(monkeypatch):
    def fake_get_evidence(cid, cap): return []
    def fake_get_artifacts(cid, cap): return []
    def fake_get_metadata(cid, cap):
        return [{
            "evidence_id": "e1",
            "extracted_at": "2026-01-01T00:00:00Z",
            "result_dict": json.dumps({
                "fields": [
                    {"field": "creation_time", "raw_value": "2026-01-01T00:00:00Z", "interpreted_value": "2026-01-01T00:00:00Z"},
                    {"field": "creation_time", "raw_value": "2026-01-02T00:00:00Z", "interpreted_value": "2026-01-02T00:00:00Z"}
                ]
            })
        }]
    from app.repositories.timeline_repository import TimelineRepository
    monkeypatch.setattr(TimelineRepository, "get_evidence", fake_get_evidence)
    monkeypatch.setattr(TimelineRepository, "get_metadata", fake_get_metadata)
    monkeypatch.setattr(TimelineRepository, "get_artifacts", fake_get_artifacts)
    
    r = TimelineService.get_timeline("c1", None, None, None, None, None, limit=10, offset=0)
    claims = [e for e in r["events"] if e["kind"] == "CONTAINER_CREATION_TIME"]
    assert len(claims) == 2
    assert claims[0]["event_id"] != claims[1]["event_id"]

def test_m15_summary_counts_all_events(monkeypatch):
    def fake_get_evidence(cid, cap):
        return [
            {"evidence_id": "e1", "registered_at": "2026-01-01T00:00:00Z", "ingested_at": "2026-01-01T00:00:00Z", "hashed_at": "2026-01-01T00:00:00Z", "acquisition_time": None, "format_detection": None, "vendor_detection": None}
        ]
    def fake_get_metadata(cid, cap): return []
    def fake_get_artifacts(cid, cap): return []
    from app.repositories.timeline_repository import TimelineRepository
    monkeypatch.setattr(TimelineRepository, "get_evidence", fake_get_evidence)
    monkeypatch.setattr(TimelineRepository, "get_metadata", fake_get_metadata)
    monkeypatch.setattr(TimelineRepository, "get_artifacts", fake_get_artifacts)
    
    # 3 events total. Limit 1.
    r = TimelineService.get_timeline("c1", None, None, None, None, None, limit=1, offset=0)
    assert r["summary"]["event_count"] == 3
    assert len(r["events"]) == 1
    assert r["page"]["total"] == 3
    
def test_string_comparison_filter(monkeypatch):
    def fake_get_evidence(cid, cap):
        return [
            {"evidence_id": "e1", "registered_at": "2026-01-01T00:02:00Z", "ingested_at": "2026-01-01T00:02:00Z", "hashed_at": "2026-01-01T00:02:00Z", "acquisition_time": None, "format_detection": None, "vendor_detection": None}
        ]
    def fake_get_metadata(cid, cap): return []
    def fake_get_artifacts(cid, cap): return []
    from app.repositories.timeline_repository import TimelineRepository
    monkeypatch.setattr(TimelineRepository, "get_evidence", fake_get_evidence)
    monkeypatch.setattr(TimelineRepository, "get_metadata", fake_get_metadata)
    monkeypatch.setattr(TimelineRepository, "get_artifacts", fake_get_artifacts)
    
    start_dt, _ = parse_to_datetime("2026-01-01T00:02:00.250000Z")
    r = TimelineService.get_timeline("c1", None, None, None, start_dt, None, limit=10, offset=0)
    assert len(r["events"]) == 0
