import pytest
from app.forensic.timeline_builder import parse_timestamp, build_event_id, sort_key
from app.services.timeline_service import TimelineService

def test_parse_timestamp():
    assert parse_timestamp("2026-01-01T00:00:00Z") == ("2026-01-01T00:00:00Z", "")
    assert parse_timestamp("2026-01-01T00:00:00+05:30") == ("2025-12-31T18:30:00Z", "")
    assert parse_timestamp("2026-01-01T00:00:00-08:00") == ("2026-01-01T08:00:00Z", "")
    assert parse_timestamp("2026-01-01T00:00:00") == ("2026-01-01T00:00:00Z", "TIMEZONE_ASSUMED_UTC")
    
    assert parse_timestamp("2026-01-01T00:00:00.123Z") == ("2026-01-01T00:00:00.123000Z", "")
    assert parse_timestamp("2026-01-01T00:00:00.123456Z") == ("2026-01-01T00:00:00.123456Z", "")
    
    assert parse_timestamp("   2026-01-01T00:00:00Z   ") == ("2026-01-01T00:00:00Z", "")
    assert parse_timestamp("2026-03-01") == ("2026-03-01T00:00:00Z", "TIMEZONE_ASSUMED_UTC")
    
    assert parse_timestamp("") == (None, "ABSENT")
    assert parse_timestamp("   ") == (None, "ABSENT")
    assert parse_timestamp(None) == (None, "ABSENT")
    assert parse_timestamp(123) == (None, "UNPARSEABLE_TIMESTAMP")
    assert parse_timestamp([1, 2]) == (None, "UNPARSEABLE_TIMESTAMP")
    
    assert parse_timestamp("A" * 10000) == (None, "UNPARSEABLE_TIMESTAMP")
    
    assert parse_timestamp("2026-02-30T00:00:00Z") == (None, "UNPARSEABLE_TIMESTAMP")
    assert parse_timestamp("2026-01-01T23:59:60Z") == (None, "UNPARSEABLE_TIMESTAMP")
    
    assert parse_timestamp("-0001-01-01T00:00:00Z") == (None, "UNPARSEABLE_TIMESTAMP")
    assert parse_timestamp("10000-01-01T00:00:00Z") == (None, "UNPARSEABLE_TIMESTAMP")
    
    assert parse_timestamp("0001-01-01T00:00:00Z") == ("0001-01-01T00:00:00Z", "")
    assert parse_timestamp("9999-12-31T23:59:59Z") == ("9999-12-31T23:59:59Z", "")

def test_event_id():
    id1 = build_event_id("K", "E", "S")
    assert id1 == build_event_id("K", "E", "S")
    assert id1 != build_event_id("K2", "E", "S")
    assert id1 != build_event_id("K", "E2", "S")
    assert id1 != build_event_id("K", "E", "S2")
    assert len(id1) == 16
    assert all(c in "0123456789abcdef" for c in id1)

def test_sort_key():
    e1 = {"timestamp": "A", "time_source": "TOOL_CLOCK", "kind": "B", "event_id": "1"}
    e2 = {"timestamp": "A", "time_source": "USER_DECLARED", "kind": "A", "event_id": "1"}
    assert sort_key(e1) < sort_key(e2)
    
    e3 = {"timestamp": "A", "time_source": "TOOL_CLOCK", "kind": "C", "event_id": "1"}
    assert sort_key(e1) < sort_key(e3)
    
    e4 = {"timestamp": "A", "time_source": "TOOL_CLOCK", "kind": "B", "event_id": "2"}
    assert sort_key(e1) < sort_key(e4)

def test_imports():
    import sys
    with open("app/forensic/timeline_builder.py") as f:
        content = f.read()
    assert "import sqlite3" not in content
    assert "import os" not in content
    assert "import pathlib" not in content
    assert "open(" not in content

def test_builder_logic(monkeypatch):
    import json
    
    def fake_get_evidence(cid, cap):
        return [{
            "evidence_id": "e1",
            "registered_at": "2026-01-01T00:00:00Z",
            "ingested_at": "2026-01-01T00:00:00Z",
            "hashed_at": "2026-01-01T00:00:00Z",
            "acquisition_time": "2030-01-01T00:00:00Z", # AFTER_INGEST
            "format_detection": '{"detected_at": "2026-01-01T00:00:00Z"}',
            "vendor_detection": '{"detected_at": "2026-01-01T00:00:00Z"}'
        }, {
            "evidence_id": "e2",
            "registered_at": "2026-01-01T00:00:00Z",
            "ingested_at": "2026-01-01T00:00:00Z",
            "hashed_at": "2026-01-01T00:00:00Z",
            "acquisition_time": "1980-01-01T00:00:00Z", # OUT_OF_PLAUSIBLE_RANGE
            "format_detection": "invalid json", # Malformed string
            "vendor_detection": '["not a dict"]' # Malformed structure
        }, {
            "evidence_id": "e3",
            "registered_at": "2026-01-01T00:00:00Z",
            "ingested_at": "2026-01-01T00:00:00Z",
            "hashed_at": "2026-01-01T00:00:00Z",
            "acquisition_time": "A" * 201, # truncation
            "format_detection": None,
            "vendor_detection": None
        }]

    def fake_get_metadata(cid, cap):
        return [{
            "evidence_id": "e1",
            "extracted_at": "2026-01-01T00:00:00Z",
            "result_dict": json.dumps({
                "fields": [
                    {"field": "creation_time", "raw_value": "2026-01-01T00:00:00Z", "interpreted_value": "2026-01-01T00:00:00Z"}
                ]
            })
        }, {
            "evidence_id": "e2",
            "extracted_at": "2026-01-01T00:00:00Z",
            "result_dict": 'invalid json'
        }, {
            "evidence_id": "e3",
            "extracted_at": "2026-01-01T00:00:00Z",
            "result_dict": json.dumps({
                "fields": "not a list"
            })
        }]
        
    def fake_get_artifacts(cid, cap):
        return []

    from app.repositories.timeline_repository import TimelineRepository
    monkeypatch.setattr(TimelineRepository, "get_evidence", fake_get_evidence)
    monkeypatch.setattr(TimelineRepository, "get_metadata", fake_get_metadata)
    monkeypatch.setattr(TimelineRepository, "get_artifacts", fake_get_artifacts)
    
    r = TimelineService.get_timeline("c1", None, None, None, None, None, limit=100, offset=0)
    
    acq1 = [e for e in r["events"] if e["evidence_id"] == "e1" and e["kind"] == "ACQUISITION_DECLARED"][0]
    assert "AFTER_INGEST" in acq1["flags"]
    assert "OUT_OF_PLAUSIBLE_RANGE" not in acq1["flags"]
    
    reg1 = [e for e in r["events"] if e["evidence_id"] == "e1" and e["kind"] == "EVIDENCE_REGISTERED"][0]
    assert "AFTER_INGEST" not in reg1["flags"] # Never for TOOL_CLOCK
    
    acq2 = [e for e in r["events"] if e["evidence_id"] == "e2" and e["kind"] == "ACQUISITION_DECLARED"][0]
    assert "OUT_OF_PLAUSIBLE_RANGE" in acq2["flags"]
    
    undated_acq3 = [u for u in r["undated"] if u["evidence_id"] == "e3" and u["kind"] == "ACQUISITION_DECLARED"][0]
    assert len(undated_acq3["raw_value"]) == 200
    assert undated_acq3["raw_value"] == "A" * 200
    
    assert r["summary"]["event_count"] == 17
    
    r2 = TimelineService.get_timeline("c1", None, None, None, None, None, limit=5, offset=0)
    assert r2["summary"]["event_count"] == 17
    assert len(r2["events"]) == 5

import datetime
from app.forensic.timeline_builder import parse_to_datetime

@pytest.mark.parametrize("ts, expected_dt, expected_flags", [
    ("2026-01-01T00:00:00Z", datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), ""),
    ("2026-01-01T00:00:00+05:30", datetime.datetime(2025, 12, 31, 18, 30, tzinfo=datetime.timezone.utc), ""),
    ("2026-01-01T00:00:00-08:00", datetime.datetime(2026, 1, 1, 8, 0, tzinfo=datetime.timezone.utc), ""),
    ("2026-01-01T00:00:00", datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), "TIMEZONE_ASSUMED_UTC"),
    ("2026-01-01T00:00:00.123Z", datetime.datetime(2026, 1, 1, 0, 0, 0, 123000, tzinfo=datetime.timezone.utc), ""),
    ("2026-01-01T00:00:00.123456Z", datetime.datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=datetime.timezone.utc), ""),
    ("   2026-01-01T00:00:00Z   ", datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), ""),
    ("2026-03-01", datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc), "TIMEZONE_ASSUMED_UTC"),
    ("", None, "ABSENT"),
    ("   ", None, "ABSENT"),
    (None, None, "ABSENT"),
    (123, None, "UNPARSEABLE_TIMESTAMP"),
    ([1, 2], None, "UNPARSEABLE_TIMESTAMP"),
    ("A" * 10000, None, "UNPARSEABLE_TIMESTAMP"),
    ("2026-02-30T00:00:00Z", None, "UNPARSEABLE_TIMESTAMP"),
    ("2026-01-01T23:59:60Z", None, "UNPARSEABLE_TIMESTAMP"),
    ("0000-01-01T00:00:00Z", None, "UNPARSEABLE_TIMESTAMP"),
    ("10000-01-01T00:00:00Z", None, "UNPARSEABLE_TIMESTAMP"),
    ("0001-01-01T00:00:00Z", datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc), ""),
    ("9999-12-31T23:59:59Z", datetime.datetime(9999, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc), ""),
    ("2026-01-01T00:00", datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), "TIMEZONE_ASSUMED_UTC"),
    ("2026-10-10", datetime.datetime(2026, 10, 10, tzinfo=datetime.timezone.utc), "TIMEZONE_ASSUMED_UTC"),
    ("2026-10-10T12:30", datetime.datetime(2026, 10, 10, 12, 30, tzinfo=datetime.timezone.utc), "TIMEZONE_ASSUMED_UTC"),
    ("2026-10-10T12:30:45", datetime.datetime(2026, 10, 10, 12, 30, 45, tzinfo=datetime.timezone.utc), "TIMEZONE_ASSUMED_UTC"),
    ("2026-10-10T12:30:45.1", datetime.datetime(2026, 10, 10, 12, 30, 45, 100000, tzinfo=datetime.timezone.utc), "TIMEZONE_ASSUMED_UTC")
])
def test_parse_to_datetime_extra(ts, expected_dt, expected_flags):
    dt, flags = parse_to_datetime(ts)
    assert dt == expected_dt
    assert flags == expected_flags

def test_r1_fractional_ordering_bug():
    try:
        from app.forensic.timeline_builder import parse_to_datetime
    except ImportError:
        parse_to_datetime = parse_timestamp  # to show it failing as it returns string

    # 1) Sorting whole vs fractional using actual return types
    e1_dt, _ = parse_to_datetime("2026-01-01T00:02:00Z")
    e2_dt, _ = parse_to_datetime("2026-01-01T00:02:00.500000Z")
    e1 = {"dt": e1_dt, "timestamp": e1_dt, "time_source": "TOOL_CLOCK", "kind": "B", "event_id": "1"}
    e2 = {"dt": e2_dt, "timestamp": e2_dt, "time_source": "TOOL_CLOCK", "kind": "B", "event_id": "2"}
    assert sort_key(e1) < sort_key(e2)

    # 2) Filter excludes whole second, includes fractional
    start_dt, _ = parse_to_datetime("2026-01-01T00:02:00.250000Z")
    assert e1["dt"] < start_dt
    assert e2["dt"] >= start_dt

    # 3) AFTER_INGEST flag with fractional declaration
    ingested_dt, _ = parse_to_datetime("2026-01-01T00:02:00Z")
    declared_dt, _ = parse_to_datetime("2026-01-01T00:02:00.500000Z")
    assert declared_dt > ingested_dt

    # 4) Year 0999 and 1000 don't crash, 0999 is OUT_OF_PLAUSIBLE_RANGE
    dt_999, _ = parse_to_datetime("0999-12-31T23:59:59Z")
    dt_1000, _ = parse_to_datetime("1000-01-01T00:00:00Z")
    assert dt_999.year == 999
    assert dt_1000.year == 1000