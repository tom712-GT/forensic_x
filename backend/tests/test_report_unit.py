import inspect
from app.db.database import get_connection


def test_unit_canonical_json_key_order():
    from app.forensic.report_hash import canonical_json
    d = {"z": 1, "a": {"k": 2, "b": 3}, "m": 4}
    assert canonical_json(d) == '{"a":{"b":3,"k":2},"m":4,"z":1}'


def test_unit_canonical_json_unicode_escaping():
    from app.forensic.report_hash import canonical_json
    d = {"text": "café", "symbol": "\u2713"}
    assert canonical_json(d) == '{"symbol":"\\u2713","text":"caf\\u00e9"}'


def test_unit_canonical_json_nested_lists():
    from app.forensic.report_hash import canonical_json
    d = {"items": [{"b": 1, "a": 2}, [3, 4], {"y": 10, "x": 20}]}
    assert canonical_json(d) == '{"items":[{"a":2,"b":1},[3,4],{"x":20,"y":10}]}'


def test_unit_canonical_json_none():
    from app.forensic.report_hash import canonical_json
    d = {"a": None, "b": {"c": None}}
    assert canonical_json(d) == '{"a":null,"b":{"c":null}}'


def test_unit_canonical_json_floats():
    from app.forensic.report_hash import canonical_json
    d = {"total": 900.0, "frac": 12.34}
    assert canonical_json(d) == '{"frac":12.34,"total":900.0}'


def test_unit_compute_report_hash_length_and_lowercase():
    from app.forensic.report_hash import compute_report_hash
    h = compute_report_hash({"test": 123})
    assert len(h) == 64
    assert h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)


def test_unit_module_source_pure():
    import app.forensic.report_hash as mod
    src = inspect.getsource(mod)
    assert "sqlite3" not in src
    assert "import os" not in src and "from os" not in src
    assert "pathlib" not in src
    assert "open(" not in src


def test_unit_report_repository_evidence_query_case_restricted_and_cap(client):
    from app.repositories.report_repository import ReportRepository
    cid1 = client.post("/api/cases", json={"case_name": "C1"}).json()["case_id"]
    cid2 = client.post("/api/cases", json={"case_name": "C2"}).json()["case_id"]
    client.post(f"/api/cases/{cid1}/evidence", json={"original_filename": "f1.bin", "evidence_type": "BIN", "file_size": 1})
    client.post(f"/api/cases/{cid1}/evidence", json={"original_filename": "f2.bin", "evidence_type": "BIN", "file_size": 2})
    client.post(f"/api/cases/{cid1}/evidence", json={"original_filename": "f3.bin", "evidence_type": "BIN", "file_size": 3})
    client.post(f"/api/cases/{cid2}/evidence", json={"original_filename": "f4.bin", "evidence_type": "BIN", "file_size": 4})
    rows = ReportRepository.get_case_evidence(cid1, limit=2)
    assert len(rows) == 2
    assert all(r["evidence_id"] != "" for r in rows)
    rows2 = ReportRepository.get_case_evidence(cid2, limit=10)
    assert len(rows2) == 1


def test_unit_report_repository_evidence_row_has_exact_keys(client):
    from app.repositories.report_repository import ReportRepository
    cid = client.post("/api/cases", json={"case_name": "KeysCase"}).json()["case_id"]
    client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "secret_name.bin", "evidence_type": "BIN", "file_size": 1, "description": "secret description"})
    rows = ReportRepository.get_case_evidence(cid, limit=10)
    assert len(rows) == 1
    expected = {
        "evidence_id", "evidence_type", "status", "file_size", "stored_size",
        "hash_algorithm", "sha256", "registered_at", "ingested_at", "hashed_at",
        "format_detection", "vendor_detection", "group_label", "metadata_status",
        "calibrated",
    }
    assert set(rows[0].keys()) == expected
    for forbidden in ("original_filename", "stored_path", "output_path", "description"):
        assert forbidden not in rows[0]


def test_unit_evidence_entry_builder_corrupt_detection_json():
    from app.services.report_service import _parse_format, _parse_vendor
    assert _parse_format(None) is None
    assert _parse_format("{bad json") is None
    assert _parse_format("[1, 2]") is None
    assert _parse_format('{"detected_format": 123}') is None
    assert _parse_format('{"detected_format": "MP4"}') == "MP4"
    assert _parse_vendor(None) is None
    assert _parse_vendor('"string"') is None
    assert _parse_vendor('{"vendor": 99}') is None
    assert _parse_vendor('{"vendor": "SONY"}') == "SONY"


def test_unit_calibration_references_only_active_and_ordered(client):
    from app.repositories.report_repository import ReportRepository
    cid = client.post("/api/cases", json={"case_name": "CalCase"}).json()["case_id"]
    e1 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "e1.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    e2 = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": "e2.bin", "evidence_type": "BIN", "file_size": 1}).json()["evidence_id"]
    ref2 = client.post(f"/api/evidence/{e2}/calibration", json={"device_time": "2026-01-01T10:00:00Z", "reference_time": "2026-01-01T10:00:02Z", "uncertainty_seconds": 1}).json()
    client.post(f"/api/evidence/{e1}/calibration", json={"device_time": "2026-01-01T10:00:00Z", "reference_time": "2026-01-01T10:00:03Z", "uncertainty_seconds": 1})
    ref1_active = client.post(f"/api/evidence/{e1}/calibration", json={"device_time": "2026-01-01T10:00:00Z", "reference_time": "2026-01-01T10:00:05Z", "uncertainty_seconds": 2}).json()

    refs = ReportRepository.get_calibration_references(cid)
    assert len(refs) == 2
    assert [r["reference_id"] for r in refs] == [ref1_active["reference_id"], ref2["reference_id"]]
    assert refs[0]["offset_seconds"] == 5.0
    assert refs[0]["uncertainty_seconds"] == 2.0


def test_unit_verify_endpoint_with_extra_fields(client):
    from app.forensic.report_hash import compute_report_hash
    body_data = {"key": "value"}
    h = compute_report_hash(body_data)
    r = client.post("/api/reports/verify", json={"report": body_data, "report_sha256": h, "extra_foo": "bar", "unknown": 123})
    assert r.status_code == 200
    res = r.json()
    assert res["valid"] is True
    assert res["computed_sha256"] == h


def test_unit_evidence_truncated_exact_cap_vs_cap_plus_one(client, monkeypatch):
    import app.services.timeline_service as ts_mod
    from app.services.report_service import ReportService
    cid = client.post("/api/cases", json={"case_name": "CapCase"}).json()["case_id"]
    for i in range(3):
        client.post(f"/api/cases/{cid}/evidence", json={"original_filename": f"f{i}.bin", "evidence_type": "BIN", "file_size": 1})

    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 3)
    c_obj = client.get(f"/api/cases/{cid}").json()
    rep = ReportService.build_report(cid, c_obj)
    assert len(rep["evidence"]) == 3
    assert rep["evidence_truncated"] is False

    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 2)
    rep2 = ReportService.build_report(cid, c_obj)
    assert len(rep2["evidence"]) == 2
    assert rep2["evidence_truncated"] is True


def test_unit_report_service_does_not_mutate_service_results(client):
    from app.services.report_service import ReportService
    cid = client.post("/api/cases", json={"case_name": "MutCase"}).json()["case_id"]
    c_obj = client.get(f"/api/cases/{cid}").json()
    rep = ReportService.build_report(cid, c_obj)
    assert set(rep["sections"]["timeline"].keys()) == {"event_count", "undated_count", "earliest", "latest", "truncated"}
    assert set(rep["sections"]["gaps"].keys()) == {"gap_count", "total_gap_seconds", "longest_gap_seconds", "unknown_length_count", "unplaced_count", "truncated"}
    assert set(rep["sections"]["correlation"].keys()) == {"window_count", "total_overlap_seconds", "longest_overlap_seconds", "max_simultaneous_groups", "truncated"}
    assert set(rep["sections"]["audit_chain"].keys()) == {"status", "total_count", "pre_chain_count", "chained_count", "verified_count", "first_break", "anchor"}


def test_unit_audit_details_exactly_report_sha256(client):
    cid = client.post("/api/cases", json={"case_name": "AuditCase"}).json()["case_id"]
    r = client.get(f"/api/cases/{cid}/report")
    assert r.status_code == 200
    expected_hash = r.json()["report_sha256"]
    rows = client.get(f"/api/audit-log?case_id={cid}&limit=10").json()
    gen_rows = [a for a in rows if a["action"] == "REPORT_GENERATE"]
    assert len(gen_rows) == 1
    assert gen_rows[0]["details"] == {"report_sha256": expected_hash}
    assert gen_rows[0]["outcome"] == "SUCCESS"
    assert gen_rows[0]["case_id"] == cid
    assert gen_rows[0]["evidence_id"] is None
