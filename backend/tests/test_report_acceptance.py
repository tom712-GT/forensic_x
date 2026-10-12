import hashlib
import json

from app.db.database import get_connection
from app.repositories.metadata_repository import MetadataRepository

LIMITS = ["Timestamps inside files are claims made by the file and are not proof of when events happened.",
          "Calibration is a user-supplied estimate that assumes a constant clock offset.",
          "A gap means no evidence file covers that time; it does not prove deletion or tampering.",
          "Temporal overlap is not proof that cameras show the same event, place or person.",
          "The audit hash chain does not detect a full rewrite or deletion of the newest rows unless an anchor was saved outside this system.",
          "Hashes shown are stored baselines; this report does not re-verify files. Use the verify endpoint for that."]
DISC = ("This report summarises stored analysis results for one case. It does not itself prove the authenticity "
        "of any evidence. The report hash only shows that this JSON was not changed after generation, if the hash "
        "was stored somewhere else.")
VDISC = ("A valid result means the report content matches the supplied hash. It does not prove the report is "
         "accurate or that the hash itself was not replaced.")
CANON = "JSON with sorted keys, separators (',', ':'), ASCII escapes, UTF-8, SHA-256"
TOP = {"report", "report_sha256", "algorithm", "canonicalization"}
REPORT_KEYS = {"report_version", "generated_at", "case", "evidence", "evidence_truncated", "sections",
               "limitations", "disclaimer"}
EV_KEYS = {"evidence_id", "evidence_type", "status", "file_size", "stored_size", "hash_algorithm", "sha256",
           "registered_at", "ingested_at", "hashed_at", "format", "vendor", "group_label", "metadata_status",
           "calibrated"}
SECTION_KEYS = {"timeline", "calibration", "gaps", "correlation", "audit_chain"}
NODUR = object()


def H(rep):
    return hashlib.sha256(json.dumps(rep, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                          .encode("utf-8")).hexdigest()


def T(hms, day="2025-06-01"):
    return f"{day}T{hms}Z"


def case(client, name="C"):
    r = client.post("/api/cases", json={"case_name": name})
    assert r.status_code == 201
    return r.json()["case_id"]


def ev(client, cid, name="secretvideo.mp4"):
    r = client.post(f"/api/cases/{cid}/evidence",
                    json={"original_filename": name, "evidence_type": "BIN", "file_size": 10})
    assert r.status_code == 201
    return r.json()["evidence_id"]


def meta_raw(eid, cid, fields, status="OK"):
    r = {"container": "MP4", "parser_version": "1", "status": status, "fields": fields, "errors": []}
    MetadataRepository.upsert("EVIDENCE", eid, cid, "MP4", "1", status, r, "2026-01-01T00:04:00Z")


def meta(eid, cid, start, dur=NODUR):
    fields = []
    if start is not None:
        fields.append({"field": "creation_time", "raw_value": 1, "interpreted_value": start,
                       "source": "mp4:moov/mvhd", "byte_offset": 44, "note": None})
    if dur is not NODUR:
        fields.append({"field": "duration", "raw_value": 1, "interpreted_value": dur,
                       "source": "mp4:moov/mvhd", "byte_offset": 60, "note": None})
    meta_raw(eid, cid, fields)


def setgroup(client, eid, label):
    assert client.put(f"/api/evidence/{eid}/group", json={"group_label": label}).status_code == 200


def setcal(client, eid, **o):
    b = {"device_time": "2026-01-01T10:00:00Z", "reference_time": "2026-01-01T10:00:05Z", "uncertainty_seconds": 1}
    b.update(o)
    r = client.post(f"/api/evidence/{eid}/calibration", json=b)
    assert r.status_code == 201, r.text
    return r.json()


def mk(client, cid, start, dur=NODUR, group=None, name="secretvideo.mp4"):
    e = ev(client, cid, name)
    meta(e, cid, start, dur)
    if group is not None:
        setgroup(client, e, group)
    return e


def get(client, cid):
    r = client.get(f"/api/cases/{cid}/report")
    assert r.status_code == 200, r.text
    return r.json()


def rep(client, cid):
    return get(client, cid)["report"]


def report_audit(client, cid):
    rows = client.get(f"/api/audit-log?case_id={cid}&limit=500").json()
    return [a for a in rows if a["action"] == "REPORT_GENERATE"]


def count_audit(client):
    return len(client.get("/api/audit-log?limit=500").json())


def test_r01_unknown_case(client):
    r = client.get("/api/cases/nope/report")
    assert r.status_code == 404 and r.json()["detail"] == "Case not found"
    rows = report_audit(client, "nope")
    assert len(rows) == 1 and rows[0]["outcome"] == "NOT_FOUND" and rows[0]["details"]["reason"] == "UNKNOWN_CASE"
    assert rows[0]["http_status"] == 404


def test_r02_empty_case_shape(client):
    cid = case(client)
    j = get(client, cid)
    assert set(j) == TOP and j["algorithm"] == "SHA-256" and j["canonicalization"] == CANON
    r = j["report"]
    assert set(r) == REPORT_KEYS and r["report_version"] == "1" and r["generated_at"].endswith("Z")
    assert r["evidence"] == [] and r["evidence_truncated"] is False
    assert r["limitations"] == LIMITS and r["disclaimer"] == DISC
    assert j["report_sha256"] == H(r) and len(j["report_sha256"]) == 64
    s = r["sections"]
    assert set(s) == SECTION_KEYS
    assert s["timeline"] == {"event_count": 0, "undated_count": 0, "earliest": None, "latest": None, "truncated": False}
    assert s["calibration"] == {"calibrated_evidence_count": 0, "references": []}
    assert s["gaps"] == {"gap_count": 0, "total_gap_seconds": 0.0, "longest_gap_seconds": 0.0,
                         "unknown_length_count": 0, "unplaced_count": 0, "truncated": False}
    assert s["correlation"] == {"window_count": 0, "total_overlap_seconds": 0.0, "longest_overlap_seconds": 0.0,
                                "max_simultaneous_groups": 0, "truncated": False}
    assert set(s["audit_chain"]) == {"status", "total_count", "pre_chain_count", "chained_count",
                                     "verified_count", "first_break", "anchor"}


def test_r03_case_block(client):
    cid = case(client, "My Case")
    c = rep(client, cid)["case"]
    assert set(c) == {"case_id", "case_name", "description", "status", "created_at"}
    assert c["case_id"] == cid and c["case_name"] == "My Case" and c["status"] == "OPEN"
    assert isinstance(c["created_at"], str) and c["created_at"]


def test_r04_registered_evidence_entry(client):
    cid = case(client)
    e = ev(client, cid)
    r = rep(client, cid)
    assert len(r["evidence"]) == 1
    x = r["evidence"][0]
    assert set(x) == EV_KEYS
    assert x["evidence_id"] == e and x["evidence_type"] == "BIN" and x["status"] == "REGISTERED"
    assert x["file_size"] == 10 and x["stored_size"] is None and x["sha256"] is None
    assert x["ingested_at"] is None and x["hashed_at"] is None
    assert x["format"] is None and x["vendor"] is None and x["group_label"] == "DEFAULT"
    assert x["metadata_status"] is None and x["calibrated"] is False


def test_r05_hashed_evidence_entry(client):
    cid = case(client)
    e = ev(client, cid)
    data = b"hello forensic world" * 5
    assert client.post(f"/api/evidence/{e}/file", files={"file": ("x.bin", data)}).status_code == 200
    assert client.post(f"/api/evidence/{e}/hash").status_code == 200
    assert client.post(f"/api/evidence/{e}/detect-format").status_code == 200
    with get_connection() as c:
        algo = c.execute("SELECT hash_algorithm FROM evidence WHERE evidence_id = ?", (e,)).fetchone()[0]
    x = rep(client, cid)["evidence"][0]
    assert x["status"] == "HASHED" and x["sha256"] == hashlib.sha256(data).hexdigest()
    assert x["hash_algorithm"] == algo and x["stored_size"] == len(data)
    assert x["ingested_at"] and x["hashed_at"]
    assert isinstance(x["format"], str) and x["format"]


def test_r06_order_group_metadata_calibration(client):
    cid = case(client)
    a = mk(client, cid, T("10:00:00"), 60, "CamA")
    b = ev(client, cid)
    c = mk(client, cid, T("11:00:00"), 60)
    setcal(client, c)
    meta_raw(b, cid, [], status="PARTIAL")
    got = rep(client, cid)["evidence"]
    assert [x["evidence_id"] for x in got] == [a, b, c]
    assert [x["group_label"] for x in got] == ["CamA", "DEFAULT", "DEFAULT"]
    assert [x["metadata_status"] for x in got] == ["OK", "PARTIAL", "OK"]
    assert [x["calibrated"] for x in got] == [False, False, True]


def test_r07_corrupt_detection_columns(client):
    cid = case(client)
    e1, e2, e3 = ev(client, cid), ev(client, cid), ev(client, cid)
    with get_connection() as c:
        c.execute("UPDATE evidence SET format_detection='{bad', vendor_detection='[1,2]' WHERE evidence_id=?", (e1,))
        c.execute("UPDATE evidence SET format_detection='{\"detected_format\": 5}', vendor_detection='\"x\"' WHERE evidence_id=?", (e2,))
        c.execute("UPDATE evidence SET format_detection='{\"detected_format\": \"AVI\"}', vendor_detection='{\"vendor\": \"DAHUA\"}' WHERE evidence_id=?", (e3,))
    got = rep(client, cid)["evidence"]
    assert [(x["format"], x["vendor"]) for x in got] == [(None, None), (None, None), ("AVI", "DAHUA")]


def test_r08_sections_match_endpoints(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800, "CamA")
    mk(client, cid, T("10:45:00"), 600, "CamA")
    mk(client, cid, T("10:00:00"), 3600, "CamB")
    mk(client, cid, T("09:00:00"), group="CamA")
    nocreate = ev(client, cid)
    meta(nocreate, cid, None, 60)
    s = rep(client, cid)["sections"]
    tl = client.get(f"/api/cases/{cid}/timeline").json()["summary"]
    assert s["timeline"] == {k: tl[k] for k in ("event_count", "undated_count", "earliest", "latest", "truncated")}
    g = client.get(f"/api/cases/{cid}/gaps").json()
    assert s["gaps"] == {"gap_count": g["summary"]["gap_count"], "total_gap_seconds": g["summary"]["total_gap_seconds"],
                         "longest_gap_seconds": g["summary"]["longest_gap_seconds"],
                         "unknown_length_count": len(g["unknown_length"]), "unplaced_count": len(g["unplaced"]),
                         "truncated": g["summary"]["truncated"]}
    assert s["gaps"]["gap_count"] == 1 and s["gaps"]["total_gap_seconds"] == 900.0
    assert s["gaps"]["unknown_length_count"] == 1 and s["gaps"]["unplaced_count"] == 1
    co = client.get(f"/api/cases/{cid}/correlation").json()["summary"]
    assert s["correlation"] == {k: co[k] for k in ("window_count", "total_overlap_seconds", "longest_overlap_seconds",
                                                    "max_simultaneous_groups", "truncated")}
    assert s["correlation"]["window_count"] >= 1 and s["correlation"]["max_simultaneous_groups"] == 2


def test_r09_calibration_section(client):
    cid = case(client)
    a = mk(client, cid, T("10:00:00"), 60)
    b = mk(client, cid, T("11:00:00"), 60)
    ref_b = setcal(client, b, uncertainty_seconds=2)
    setcal(client, a)
    ref_a = setcal(client, a, reference_time="2026-01-01T10:00:09Z", uncertainty_seconds=3)
    s = rep(client, cid)["sections"]["calibration"]
    assert s["calibrated_evidence_count"] == 2
    assert s["references"] == [
        {"evidence_id": a, "reference_id": ref_a["reference_id"], "offset_seconds": 9.0,
         "uncertainty_seconds": 3.0, "entered_at": ref_a["entered_at"]},
        {"evidence_id": b, "reference_id": ref_b["reference_id"], "offset_seconds": 5.0,
         "uncertainty_seconds": 2.0, "entered_at": ref_b["entered_at"]}]


def test_r10_audit_section_is_state_before_report(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 60)
    v = client.get("/api/audit-log/verify").json()
    a = rep(client, cid)["sections"]["audit_chain"]
    assert a == {k: v[k] for k in ("status", "total_count", "pre_chain_count", "chained_count",
                                    "verified_count", "first_break", "anchor")}
    assert a["status"] == "OK" and a["total_count"] >= 1 and a["anchor"] is not None


def test_r11_audit_row_written(client):
    cid = case(client)
    before = count_audit(client)
    j = get(client, cid)
    assert count_audit(client) == before + 1
    rows = report_audit(client, cid)
    assert len(rows) == 1
    a = rows[0]
    assert a["outcome"] == "SUCCESS" and a["http_status"] == 200 and a["case_id"] == cid
    assert a["evidence_id"] is None
    assert a["details"] == {"report_sha256": j["report_sha256"]}
    get(client, cid)
    assert len(report_audit(client, cid)) == 2
    v = client.get("/api/audit-log/verify").json()
    assert v["status"] == "OK" and v["first_break"] is None


def test_r12_no_leaks(client):
    cid = case(client)
    e = mk(client, cid, T("10:00:00"), 60, name="SECRETNAME.mp4")
    with get_connection() as c:
        c.execute("UPDATE evidence SET stored_path='C:\\SECRET_DIR\\f', description='SECRETDESC' WHERE evidence_id=?", (e,))
        c.execute("INSERT INTO recovered_artifacts (artifact_id, evidence_id, case_id, source_offset, recovered_size, "
                  "detected_type, recovery_timestamp, output_path, status, artifact_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("art-1", e, cid, 1, 1, "JPEG", "2026-01-01T00:05:00Z", "SECRET_PATH_X", "RECOVERED", "h"))
    t = client.get(f"/api/cases/{cid}/report").text
    for bad in ("SECRETNAME", "SECRET_DIR", "SECRETDESC", "SECRET_PATH_X", "stored_path", "output_path",
                "original_filename"):
        assert bad not in t


def snap():
    out = {}
    with get_connection() as c:
        for t in ("cases", "evidence", "metadata_extractions", "recovered_artifacts", "calibration_references",
                  "evidence_groups"):
            out[t] = [tuple(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY rowid")]
        out["v"] = c.execute("PRAGMA user_version").fetchone()[0]
        out["tables"] = sorted(r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    return out


def test_r13_no_side_effects(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 60, "CamA")
    before = snap()
    assert before["v"] == 10
    get(client, cid)
    client.get("/api/cases/nope/report")
    assert snap() == before
    assert not any("report" in t for t in before["tables"])


def test_r14_deterministic_apart_from_time_and_audit(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 600, "CamA")
    mk(client, cid, T("10:05:00"), 600, "CamB")
    r1, r2 = rep(client, cid), rep(client, cid)
    for r in (r1, r2):
        del r["generated_at"]
        del r["sections"]["audit_chain"]
    assert r1 == r2


def test_r15_truncation(client, monkeypatch):
    import app.services.timeline_service as ts_mod
    cid = case(client)
    for h in (10, 11, 12):
        mk(client, cid, T(f"{h}:00:00"), 60, "CamA")
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 2)
    r = rep(client, cid)
    assert len(r["evidence"]) == 2 and r["evidence_truncated"] is True
    assert r["sections"]["timeline"]["truncated"] is True and r["sections"]["gaps"]["truncated"] is True
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 3)
    r = rep(client, cid)
    assert len(r["evidence"]) == 3 and r["evidence_truncated"] is False
    assert r["sections"]["timeline"]["truncated"] is False and r["sections"]["gaps"]["truncated"] is False


def test_r16_unexpected_error(client, monkeypatch):
    import app.services.report_service as rs
    cid = case(client)

    def boom(*a, **k):
        raise RuntimeError("secret C:\\x")

    monkeypatch.setattr(rs.TimelineService, "get_timeline", boom)
    r = client.get(f"/api/cases/{cid}/report")
    assert r.status_code == 500 and r.json() == {"detail": "Internal error while generating report"}
    assert "secret" not in r.text
    rows = report_audit(client, cid)
    assert len(rows) == 1 and rows[0]["outcome"] == "ERROR" and rows[0]["details"]["reason"] == "INTERNAL_ERROR"
    assert rows[0]["http_status"] == 500


def vbody(rep_, h=None):
    return {"report": rep_, "report_sha256": h if h is not None else H(rep_)}


def test_r17_verify_roundtrip(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 60)
    j = get(client, cid)
    n = count_audit(client)
    r = client.post("/api/reports/verify", json={"report": j["report"], "report_sha256": j["report_sha256"],
                                                  "extra": "ignored"})
    assert r.status_code == 200
    assert r.json() == {"valid": True, "computed_sha256": j["report_sha256"], "algorithm": "SHA-256",
                        "disclaimer": VDISC}
    assert count_audit(client) == n


def test_r18_verify_detects_tampering(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 60)
    j = get(client, cid)
    good = j["report_sha256"]

    def check(mut, expect):
        r = json.loads(json.dumps(j["report"]))
        mut(r)
        out = client.post("/api/reports/verify", json={"report": r, "report_sha256": good})
        assert out.status_code == 200 and out.json()["valid"] is expect
        return out.json()

    check(lambda r: r["case"].update(case_name="X"), False)
    check(lambda r: r["evidence"][0].update(sha256="0" * 64), False)
    check(lambda r: r.update(extra_key=1), False)
    check(lambda r: r.pop("limitations"), False)
    check(lambda r: r["sections"]["gaps"].update(gap_count=99), False)
    out = check(lambda r: None, True)
    assert out["computed_sha256"] == good
    wrong = client.post("/api/reports/verify", json=vbody(j["report"], "f" * 64)).json()
    assert wrong["valid"] is False and wrong["computed_sha256"] == good
    reordered = {k: j["report"][k] for k in reversed(list(j["report"]))}
    assert client.post("/api/reports/verify", json=vbody(reordered, good)).json()["valid"] is True


def test_r19_verify_validation(client):
    ok = {"a": 1}
    for bad in ({"report": ok}, {"report_sha256": "a" * 64}, {"report": ok, "report_sha256": "A" * 64},
                {"report": ok, "report_sha256": "a" * 63}, {"report": ok, "report_sha256": "g" * 64},
                {"report": [1], "report_sha256": "a" * 64}, {"report": "x", "report_sha256": "a" * 64},
                {"report": None, "report_sha256": "a" * 64}):
        assert client.post("/api/reports/verify", json=bad).status_code == 422, bad
    assert client.post("/api/reports/verify", content="nope",
                       headers={"content-type": "application/json"}).status_code == 422
    r = client.post("/api/reports/verify", json=vbody({}))
    assert r.status_code == 200 and r.json()["valid"] is True


def test_r20_pure_functions():
    from app.forensic.report_hash import canonical_json, compute_report_hash
    d = {"b": 1, "a": {"y": None, "x": [1, 2.5, "é"]}}
    assert canonical_json(d) == '{"a":{"x":[1,2.5,"\\u00e9"],"y":null},"b":1}'
    assert compute_report_hash(d) == H(d) == hashlib.sha256(canonical_json(d).encode("utf-8")).hexdigest()
    assert compute_report_hash({"a": 1, "b": 2}) == compute_report_hash({"b": 2, "a": 1})
    assert compute_report_hash({"a": 1}) != compute_report_hash({"a": 2})
