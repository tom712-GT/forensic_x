import json
from app.db.database import get_connection
from app.repositories.metadata_repository import MetadataRepository

DISCLAIMER = ("Calibration is a user-supplied estimate. Corrected times are ranges derived from one reference "
              "and assume a constant clock offset. They are not proof of when the real event happened.")
REC_KEYS = {"reference_id", "evidence_id", "case_id", "device_time", "reference_time", "offset_seconds",
            "uncertainty_seconds", "note", "flags", "entered_at", "entered_by", "superseded_at", "status"}
ITEM_KEYS = {"event_id", "evidence_id", "kind", "original_timestamp", "flags", "correction_status",
             "calibration", "corrected", "effective_timestamp"}


def case(client):
    r = client.post("/api/cases", json={"case_name": "C"})
    assert r.status_code == 201
    return r.json()["case_id"]


def ev(client, cid, name="secretvideo.mp4"):
    r = client.post(f"/api/cases/{cid}/evidence",
                    json={"original_filename": name, "evidence_type": "BIN", "file_size": 10})
    assert r.status_code == 201
    return r.json()["evidence_id"]


def body(**o):
    b = {"device_time": "2026-01-01T10:00:00Z", "reference_time": "2026-01-01T10:00:05Z",
         "uncertainty_seconds": 1}
    b.update(o)
    return b


def setcal(client, eid, **o):
    return client.post(f"/api/evidence/{eid}/calibration", json=body(**o))


def getcal(client, eid):
    return client.get(f"/api/evidence/{eid}/calibration")


def claim(name, interp, raw=1, note=None, offset=44):
    return {"field": name, "raw_value": raw, "interpreted_value": interp,
            "source": "mp4:moov/mvhd", "byte_offset": offset, "note": note}


def meta(eid, cid, fields, extracted_at="2026-01-01T00:04:00Z"):
    r = {"container": "MP4", "parser_version": "1", "status": "OK", "fields": fields, "errors": []}
    MetadataRepository.upsert("EVIDENCE", eid, cid, "MP4", "1", "OK", r, extracted_at)


def ct(client, cid, **p):
    return client.get(f"/api/cases/{cid}/calibrated-times", params=p)


def cal_audit(client, eid):
    rows = client.get(f"/api/audit-log?evidence_id={eid}&limit=500").json()
    return [a for a in rows if a["action"] == "CALIBRATION_SET"]


def item(j, eid, kind="CONTAINER_CREATION_TIME"):
    got = [i for i in j["items"] if i["evidence_id"] == eid and i["kind"] == kind]
    assert len(got) == 1, got
    return got[0]


def test_c01_unknown_evidence(client):
    r = client.post("/api/evidence/nope/calibration", json=body())
    assert r.status_code == 404 and r.json()["detail"] == "Evidence not found"
    r = getcal(client, "nope")
    assert r.status_code == 404 and r.json()["detail"] == "Evidence not found"
    rows = cal_audit(client, "nope")
    assert len(rows) == 1 and rows[0]["outcome"] == "NOT_FOUND" and rows[0]["details"]["reason"] == "UNKNOWN_EVIDENCE"


def test_c02_post_happy_path(client):
    cid = case(client)
    e = ev(client, cid)
    r = setcal(client, e)
    assert r.status_code == 201
    j = r.json()
    assert set(j) == REC_KEYS
    assert j["evidence_id"] == e and j["case_id"] == cid
    assert j["device_time"] == "2026-01-01T10:00:00Z" and j["reference_time"] == "2026-01-01T10:00:05Z"
    assert j["offset_seconds"] == 5.0 and j["uncertainty_seconds"] == 1.0
    assert j["note"] is None and j["flags"] == [] and j["superseded_at"] is None
    assert j["status"] == "ACTIVE" and j["entered_by"] == "UNAUTHENTICATED"
    assert j["entered_at"].endswith("Z") and isinstance(j["reference_id"], str) and len(j["reference_id"]) > 10
    g = getcal(client, e).json()
    assert set(g) == {"evidence_id", "disclaimer", "active", "history"}
    assert g["disclaimer"] == DISCLAIMER and g["active"] == j and g["history"] == [j]


def test_c03_offsets_and_timezones(client):
    cid = case(client)
    e = ev(client, cid)
    j = setcal(client, e, device_time="2026-01-01T10:00:10Z", reference_time="2026-01-01T10:00:07.5Z").json()
    assert j["offset_seconds"] == -2.5 and j["reference_time"] == "2026-01-01T10:00:07.500000Z"
    j = setcal(client, e, device_time="2026-01-01T15:30:00+05:30", reference_time="2026-01-01T10:00:00Z").json()
    assert j["offset_seconds"] == 0.0 and j["device_time"] == "2026-01-01T10:00:00Z" and j["flags"] == []
    j = setcal(client, e, device_time="2026-01-01T10:00:00-02:00", reference_time="2026-01-01T12:00:30Z").json()
    assert j["offset_seconds"] == 30.0 and j["device_time"] == "2026-01-01T12:00:00Z"


def test_c04_naive_flags(client):
    cid = case(client)
    e = ev(client, cid)
    j = setcal(client, e, device_time="2026-01-01T10:00:00", reference_time="2026-01-01T10:00:03Z").json()
    assert j["flags"] == ["TIMEZONE_ASSUMED_UTC"] and j["offset_seconds"] == 3.0
    j = setcal(client, e, device_time="2026-01-01T10:00:00", reference_time="2026-01-01T10:00:03").json()
    assert j["flags"] == ["TIMEZONE_ASSUMED_UTC"]
    j = setcal(client, e, device_time="2026-01-01", reference_time="2026-01-01T00:00:02+00:00").json()
    assert j["flags"] == ["TIMEZONE_ASSUMED_UTC"] and j["offset_seconds"] == 2.0


def test_c05_pydantic_422(client):
    cid = case(client)
    e = ev(client, cid)
    for k in ("device_time", "reference_time", "uncertainty_seconds"):
        b = body()
        del b[k]
        assert client.post(f"/api/evidence/{e}/calibration", json=b).status_code == 422, k
    for bad in ({"uncertainty_seconds": -1}, {"uncertainty_seconds": 31536001}, {"uncertainty_seconds": "abc"},
                {"note": "x" * 501}, {"device_time": 5}, {"reference_time": None}):
        assert setcal(client, e, **bad).status_code == 422, bad
    assert client.post(f"/api/evidence/{e}/calibration", content="not json",
                       headers={"content-type": "application/json"}).status_code == 422
    g = getcal(client, e).json()
    assert g["active"] is None and g["history"] == []
    assert cal_audit(client, e) == []


def test_c06_validation_400_and_bounds(client):
    cid = case(client)
    e = ev(client, cid)
    bad = [
        ({"device_time": "garbage"}, "Invalid device_time", "INVALID_DEVICE_TIME"),
        ({"device_time": ""}, "Invalid device_time", "INVALID_DEVICE_TIME"),
        ({"device_time": "   "}, "Invalid device_time", "INVALID_DEVICE_TIME"),
        ({"device_time": "9999-12-31T23:59:59-05:00"}, "Invalid device_time", "INVALID_DEVICE_TIME"),
        ({"reference_time": "garbage"}, "Invalid reference_time", "INVALID_REFERENCE_TIME"),
        ({"device_time": "x", "reference_time": "y"}, "Invalid device_time", "INVALID_DEVICE_TIME"),
        ({"device_time": "1980-01-01T00:00:00Z", "reference_time": "1980-01-01T00:00:00Z"},
         "Time out of plausible range", "TIME_OUT_OF_RANGE"),
        ({"reference_time": "2101-01-01T00:00:00Z"}, "Time out of plausible range", "TIME_OUT_OF_RANGE"),
        ({"device_time": "2026-01-01T00:00:00Z", "reference_time": "2035-12-30T00:00:01Z"},
         "Offset too large", "OFFSET_TOO_LARGE"),
        ({"device_time": "2035-12-30T00:00:01Z", "reference_time": "2026-01-01T00:00:00Z"},
         "Offset too large", "OFFSET_TOO_LARGE"),
    ]
    for o, msg, reason in bad:
        r = setcal(client, e, **o)
        assert r.status_code == 400 and r.json()["detail"] == msg, (o, r.text)
    g = getcal(client, e).json()
    assert g["active"] is None and g["history"] == []
    rows = cal_audit(client, e)
    assert len(rows) == len(bad) and all(a["outcome"] == "REJECTED" for a in rows)
    assert [a["details"]["reason"] for a in rows] == [b[2] for b in bad]
    r = setcal(client, e, device_time="2026-01-01T00:00:00Z", reference_time="2035-12-30T00:00:00Z")
    assert r.status_code == 201 and r.json()["offset_seconds"] == 315360000.0
    r = setcal(client, e, device_time="1990-01-01T00:00:00Z", reference_time="1990-01-01T00:00:00Z")
    assert r.status_code == 201 and r.json()["offset_seconds"] == 0.0
    r = setcal(client, e, device_time="2100-12-31T23:59:59Z", reference_time="2100-12-31T23:59:59Z")
    assert r.status_code == 201


def test_c07_supersede_history(client):
    cid = case(client)
    e = ev(client, cid)
    r1 = setcal(client, e, reference_time="2026-01-01T10:00:01Z").json()
    r2 = setcal(client, e, reference_time="2026-01-01T10:00:02Z").json()
    r3 = setcal(client, e, reference_time="2026-01-01T10:00:03Z").json()
    assert len({r1["reference_id"], r2["reference_id"], r3["reference_id"]}) == 3
    g = getcal(client, e).json()
    assert g["active"]["reference_id"] == r3["reference_id"] and g["active"]["status"] == "ACTIVE"
    assert [h["reference_id"] for h in g["history"]] == [r3["reference_id"], r2["reference_id"], r1["reference_id"]]
    assert [h["status"] for h in g["history"]] == ["ACTIVE", "SUPERSEDED", "SUPERSEDED"]
    assert g["history"][1]["superseded_at"] is not None and g["history"][2]["superseded_at"] is not None
    assert g["history"][0]["superseded_at"] is None
    assert [h["offset_seconds"] for h in g["history"]] == [3.0, 2.0, 1.0]
    with get_connection() as c:
        n = c.execute("SELECT COUNT(*) FROM calibration_references WHERE evidence_id = ? AND superseded_at IS NULL", (e,)).fetchone()[0]
        t = c.execute("SELECT COUNT(*) FROM calibration_references WHERE evidence_id = ?", (e,)).fetchone()[0]
        by = c.execute("SELECT superseded_by FROM calibration_references WHERE reference_id = ?", (r1["reference_id"],)).fetchone()[0]
    assert n == 1 and t == 3 and by == r2["reference_id"]


def test_c08_get_empty(client):
    cid = case(client)
    e = ev(client, cid)
    g = getcal(client, e)
    assert g.status_code == 200
    assert g.json() == {"evidence_id": e, "disclaimer": DISCLAIMER, "active": None, "history": []}


def test_c09_note_handling(client):
    cid = case(client)
    e = ev(client, cid)
    assert setcal(client, e, note="  hello  ").json()["note"] == "hello"
    assert setcal(client, e, note="   ").json()["note"] is None
    assert setcal(client, e, note="").json()["note"] is None
    assert setcal(client, e).json()["note"] is None
    hostile = "<script>alert(1)</script> '; DROP TABLE calibration_references;--"
    assert setcal(client, e, note=hostile).json()["note"] == hostile
    assert getcal(client, e).json()["active"]["note"] == hostile
    assert setcal(client, e, note="n" * 500).status_code == 201
    for a in cal_audit(client, e):
        assert "script" not in json.dumps(a["details"]) and "hello" not in json.dumps(a["details"])


def test_c10_any_status_allowed(client):
    cid = case(client)
    e = ev(client, cid)
    assert client.get(f"/api/evidence/{e}").json()["status"] == "REGISTERED"
    assert setcal(client, e).status_code == 201


def test_c11_isolation(client):
    c1, c2 = case(client), case(client)
    a, b, other = ev(client, c1), ev(client, c1), ev(client, c2)
    for e, cid in ((a, c1), (b, c1), (other, c2)):
        meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    setcal(client, a, reference_time="2026-01-01T10:00:09Z")
    j = ct(client, c1).json()
    assert item(j, a)["correction_status"] == "CALIBRATED"
    assert item(j, b)["correction_status"] == "NOT_CALIBRATED"
    assert not [i for i in j["items"] if i["evidence_id"] == other]
    assert getcal(client, b).json()["active"] is None and getcal(client, other).json()["active"] is None
    assert item(ct(client, c2).json(), other)["correction_status"] == "NOT_CALIBRATED"


def snap():
    out = {}
    with get_connection() as c:
        for t in ("cases", "evidence", "metadata_extractions", "recovered_artifacts"):
            out[t] = [tuple(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY rowid")]
    return out


def test_c12_no_side_effects(client):
    cid = case(client)
    e = ev(client, cid)
    meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    before, tl_before = snap(), client.get(f"/api/cases/{cid}/timeline").json()
    n = len(client.get("/api/audit-log?limit=500").json())
    assert setcal(client, e).status_code == 201
    assert snap() == before
    assert client.get(f"/api/cases/{cid}/timeline").json() == tl_before
    assert len(client.get("/api/audit-log?limit=500").json()) == n + 1
    getcal(client, e)
    ct(client, cid)
    assert len(client.get("/api/audit-log?limit=500").json()) == n + 1


def test_c13_calibrated_times_happy(client):
    cid = case(client)
    e = ev(client, cid)
    meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z", offset=44),
                  claim("modification_time", "2025-06-01T11:00:00Z", offset=48)])
    setcal(client, e, uncertainty_seconds=2)
    r = ct(client, cid)
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"case_id", "disclaimer", "items", "summary"} and j["case_id"] == cid
    assert j["disclaimer"] == DISCLAIMER
    assert set(j["summary"]) == {"item_count", "by_status", "truncated"}
    assert j["summary"] == {"item_count": 2, "by_status": {"CALIBRATED": 2}, "truncated": False}
    it = item(j, e)
    assert set(it) == ITEM_KEYS
    assert it["original_timestamp"] == "2025-06-01T10:00:00Z" and it["flags"] == []
    assert it["correction_status"] == "CALIBRATED"
    assert it["corrected"] == {"nominal": "2025-06-01T10:00:05Z", "earliest": "2025-06-01T10:00:03Z",
                               "latest": "2025-06-01T10:00:07Z"}
    assert it["effective_timestamp"] == "2025-06-01T10:00:05Z"
    ref = getcal(client, e).json()["active"]
    assert it["calibration"] == {"reference_id": ref["reference_id"], "offset_seconds": 5.0, "uncertainty_seconds": 2.0}
    m = item(j, e, "CONTAINER_MODIFICATION_TIME")
    assert m["corrected"]["nominal"] == "2025-06-01T11:00:05Z"
    assert ct(client, cid).json() == j


def test_c14_uncalibrated(client):
    cid = case(client)
    e = ev(client, cid)
    meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    j = ct(client, cid).json()
    it = item(j, e)
    assert set(it) == ITEM_KEYS
    assert it["correction_status"] == "NOT_CALIBRATED" and it["calibration"] is None and it["corrected"] is None
    assert it["effective_timestamp"] == it["original_timestamp"] == "2025-06-01T10:00:00Z"
    assert j["summary"] == {"item_count": 1, "by_status": {"NOT_CALIBRATED": 1}, "truncated": False}


def test_c15_ordering_by_effective_time(client):
    cid = case(client)
    a, b = ev(client, cid), ev(client, cid)
    meta(a, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    meta(b, cid, [claim("creation_time", "2025-06-01T10:30:00Z")])
    setcal(client, a, device_time="2026-01-01T10:00:00Z", reference_time="2026-01-01T11:00:00Z", uncertainty_seconds=0)
    j = ct(client, cid).json()
    assert [i["evidence_id"] for i in j["items"]] == [b, a]
    assert [i["effective_timestamp"] for i in j["items"]] == ["2025-06-01T10:30:00Z", "2025-06-01T11:00:00Z"]
    assert j["summary"]["by_status"] == {"CALIBRATED": 1, "NOT_CALIBRATED": 1}


def test_c16_only_container_claims(client):
    cid = case(client)
    e = ev(client, cid)
    with get_connection() as c:
        c.execute("UPDATE evidence SET registered_at='2026-01-01T00:00:00Z', acquisition_time='2026-01-01T00:00:00Z' WHERE evidence_id=?", (e,))
        c.execute("INSERT INTO recovered_artifacts (artifact_id, evidence_id, case_id, source_offset, recovered_size, "
                  "detected_type, recovery_timestamp, output_path, status, artifact_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("art-1", e, cid, 1, 1, "JPEG", "2026-01-01T00:05:00Z", "SECRET_PATH_X", "RECOVERED", "h"))
    meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z"),
                  claim("modification_time", None, raw=0, note="NOT_SET: container value is zero")])
    j = ct(client, cid).json()
    assert [i["kind"] for i in j["items"]] == ["CONTAINER_CREATION_TIME"]
    assert j["summary"]["item_count"] == 1
    assert "SECRET_PATH_X" not in json.dumps(j)


def test_c17_case_404_and_filter(client):
    r = ct(client, "nope")
    assert r.status_code == 404 and r.json()["detail"] == "Case not found"
    cid = case(client)
    a, b = ev(client, cid), ev(client, cid)
    for e in (a, b):
        meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    assert [i["evidence_id"] for i in ct(client, cid, evidence_id=a).json()["items"]] == [a]
    j = ct(client, cid, evidence_id="nope")
    assert j.status_code == 200
    assert j.json()["items"] == [] and j.json()["summary"] == {"item_count": 0, "by_status": {}, "truncated": False}
    empty = ct(client, case(client)).json()
    assert empty["items"] == [] and empty["summary"]["item_count"] == 0


def test_c18_fractional_seconds(client):
    cid = case(client)
    e = ev(client, cid)
    meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    setcal(client, e, device_time="2026-01-01T10:00:00Z", reference_time="2026-01-01T10:00:00.250000Z",
           uncertainty_seconds=0.5)
    it = item(ct(client, cid).json(), e)
    assert it["corrected"] == {"nominal": "2025-06-01T10:00:00.250000Z", "earliest": "2025-06-01T09:59:59.750000Z",
                               "latest": "2025-06-01T10:00:00.750000Z"}
    assert it["calibration"]["offset_seconds"] == 0.25 and it["calibration"]["uncertainty_seconds"] == 0.5


def test_c19_overflow_is_out_of_range(client):
    cid = case(client)
    e = ev(client, cid)
    meta(e, cid, [claim("creation_time", "9999-12-31T00:00:00Z")])
    setcal(client, e, device_time="2026-01-01T00:00:00Z", reference_time="2026-01-02T03:46:40Z", uncertainty_seconds=0)
    j = ct(client, cid).json()
    it = item(j, e)
    assert it["correction_status"] == "OUT_OF_RANGE" and it["corrected"] is None
    assert it["calibration"]["offset_seconds"] == 100000.0
    assert it["effective_timestamp"] == it["original_timestamp"] == "9999-12-31T00:00:00Z"
    assert j["summary"]["by_status"] == {"OUT_OF_RANGE": 1}
    e2 = ev(client, cid)
    meta(e2, cid, [claim("creation_time", "9999-12-31T23:00:00Z")])
    setcal(client, e2, device_time="2026-01-01T00:00:00Z", reference_time="2026-01-01T00:00:00Z", uncertainty_seconds=7200)
    assert item(ct(client, cid).json(), e2)["correction_status"] == "OUT_OF_RANGE"


def test_c20_active_reference_is_used(client):
    cid = case(client)
    e = ev(client, cid)
    meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    setcal(client, e, reference_time="2026-01-01T10:00:05Z")
    assert item(ct(client, cid).json(), e)["corrected"]["nominal"] == "2025-06-01T10:00:05Z"
    r2 = setcal(client, e, reference_time="2026-01-01T10:00:20Z").json()
    it = item(ct(client, cid).json(), e)
    assert it["corrected"]["nominal"] == "2025-06-01T10:00:20Z"
    assert it["calibration"]["reference_id"] == r2["reference_id"]


def test_c21_audit(client):
    cid = case(client)
    e = ev(client, cid, "secretvideo.mp4")
    r = setcal(client, e, note="private note").json()
    rows = cal_audit(client, e)
    assert len(rows) == 1
    a = rows[0]
    assert a["outcome"] == "SUCCESS" and a["http_status"] == 201 and a["case_id"] == cid and a["evidence_id"] == e
    assert a["details"] == {"reference_id": r["reference_id"], "offset_seconds": 5.0, "uncertainty_seconds": 1.0}
    text = json.dumps(a)
    assert "private note" not in text and "secretvideo" not in text and "\\" not in text
    getcal(client, e)
    ct(client, cid)
    assert len(cal_audit(client, e)) == 1


def test_c22_schema(client):
    with get_connection() as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 9
        cols = {r[1] for r in c.execute("PRAGMA table_info(calibration_references)")}
        idx = {r[1] for r in c.execute("PRAGMA index_list(calibration_references)")}
        sqls = " ".join(r[0] or "" for r in c.execute("SELECT sql FROM sqlite_master WHERE tbl_name='calibration_references'"))
    assert cols == {"reference_id", "evidence_id", "case_id", "device_time", "reference_time", "offset_seconds",
                    "uncertainty_seconds", "note", "flags", "entered_at", "entered_by", "superseded_at", "superseded_by"}
    assert "idx_calibration_active" in idx and "idx_calibration_evidence" in idx
    assert "superseded_at IS NULL" in sqls


def test_c23_no_leaks(client):
    cid = case(client)
    e = ev(client, cid, "SECRETNAME.mp4")
    with get_connection() as c:
        c.execute("UPDATE evidence SET stored_path='C:\\SECRET_DIR\\f', sha256='abc123secrethash' WHERE evidence_id=?", (e,))
    meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    texts = [setcal(client, e).text, getcal(client, e).text, ct(client, cid).text]
    for t in texts:
        for bad in ("SECRETNAME", "SECRET_DIR", "abc123secrethash", "stored_path", "output_path", "original_filename"):
            assert bad not in t


def test_c24_truncation_flag(client, monkeypatch):
    import app.services.timeline_service as ts_mod
    cid = case(client)
    for _ in range(3):
        e = ev(client, cid)
        meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 2)
    assert ct(client, cid).json()["summary"]["truncated"] is True
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 3)
    j = ct(client, cid).json()
    assert j["summary"]["truncated"] is False and j["summary"]["item_count"] == 3


def test_c25_uncertainty_boundaries(client):
    cid = case(client)
    e = ev(client, cid)
    meta(e, cid, [claim("creation_time", "2025-06-01T10:00:00Z")])
    assert setcal(client, e, uncertainty_seconds=0).status_code == 201
    it = item(ct(client, cid).json(), e)
    assert it["corrected"]["earliest"] == it["corrected"]["nominal"] == it["corrected"]["latest"] == "2025-06-01T10:00:05Z"
    assert setcal(client, e, uncertainty_seconds=31536000).status_code == 201
    it = item(ct(client, cid).json(), e)
    assert it["corrected"]["earliest"] < it["corrected"]["nominal"] < it["corrected"]["latest"]
    assert it["corrected"]["earliest"].startswith("2024-") and it["corrected"]["latest"].startswith("2026-")
    assert setcal(client, e, uncertainty_seconds=31536000.5).status_code == 422
