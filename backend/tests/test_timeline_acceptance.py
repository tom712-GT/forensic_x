import json
import pytest
from app.db.database import get_connection
from app.repositories.metadata_repository import MetadataRepository

DISCLAIMER = ("Timestamps are not corrected. TOOL_CLOCK = this tool's clock; USER_DECLARED = typed by a person; "
              "CONTAINER_CLAIM = value stored inside the file. None is proof of when the real event happened.")


def case(client, name="C"):
    r = client.post("/api/cases", json={"case_name": name})
    assert r.status_code == 201
    return r.json()["case_id"]


def ev(client, cid, name="a.mp4"):
    r = client.post(f"/api/cases/{cid}/evidence", json={"original_filename": name, "evidence_type": "BIN", "file_size": 10})
    assert r.status_code == 201
    return r.json()["evidence_id"]


def sql(q, args=()):
    with get_connection() as conn:
        conn.execute(q, args)


def setcol(eid, **cols):
    for k, v in cols.items():
        sql(f"UPDATE evidence SET {k} = ? WHERE evidence_id = ?", (v, eid))


def art(eid, cid, offset, ts, typ="JPEG", status="RECOVERED"):
    sql("INSERT INTO recovered_artifacts (artifact_id, evidence_id, case_id, source_offset, recovered_size, "
        "detected_type, recovery_timestamp, output_path, status, artifact_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (f"art-{eid[:8]}-{offset}", eid, cid, offset, 10, typ, ts, "SECRET_PATH_X", status, "h"))


def claim(name, interp, raw=1, note=None, offset=44):
    return {"field": name, "raw_value": raw, "interpreted_value": interp,
            "source": "mp4:moov/mvhd", "byte_offset": offset, "note": note}


def meta(eid, cid, fields, extracted_at="2026-01-01T00:04:00Z", result=None):
    r = result if result is not None else {"container": "MP4", "parser_version": "1", "status": "OK",
                                            "fields": fields, "errors": []}
    MetadataRepository.upsert("EVIDENCE", eid, cid, "MP4", "1", "OK", r, extracted_at)


def tl(client, cid, **params):
    return client.get(f"/api/cases/{cid}/timeline", params=params)


def kinds_of(client, cid, **params):
    r = tl(client, cid, **params)
    assert r.status_code == 200, r.text
    return [e["kind"] for e in r.json()["events"]]


def full(client):
    cid = case(client)
    eid = ev(client, cid)
    setcol(eid,
           registered_at="2026-01-01T00:00:00+00:00",
           ingested_at="2026-01-01T00:01:00Z",
           hashed_at="2026-01-01T00:02:00.500000+00:00",
           acquisition_time="2025-12-31T18:00:00-05:00",
           format_detection=json.dumps({"detected_format": "AVI", "detected_at": "2026-01-01T00:03:00+00:00"}),
           vendor_detection=json.dumps({"vendor": "UNKNOWN", "detected_at": "2026-01-01T00:03:30+00:00"}))
    meta(eid, cid, [claim("creation_time", "2025-06-01T10:00:00Z", offset=44),
                    claim("modification_time", "2025-06-01T11:00:00Z", offset=48)])
    art(eid, cid, 100, "2026-01-01T00:05:00+00:00")
    return cid, eid


FULL_ORDER = [
    ("CONTAINER_CREATION_TIME", "2025-06-01T10:00:00Z", "CONTAINER_CLAIM"),
    ("CONTAINER_MODIFICATION_TIME", "2025-06-01T11:00:00Z", "CONTAINER_CLAIM"),
    ("ACQUISITION_DECLARED", "2025-12-31T23:00:00Z", "USER_DECLARED"),
    ("EVIDENCE_REGISTERED", "2026-01-01T00:00:00Z", "TOOL_CLOCK"),
    ("EVIDENCE_INGESTED", "2026-01-01T00:01:00Z", "TOOL_CLOCK"),
    ("EVIDENCE_HASHED", "2026-01-01T00:02:00.500000Z", "TOOL_CLOCK"),
    ("FORMAT_DETECTED", "2026-01-01T00:03:00Z", "TOOL_CLOCK"),
    ("VENDOR_DETECTED", "2026-01-01T00:03:30Z", "TOOL_CLOCK"),
    ("METADATA_EXTRACTED", "2026-01-01T00:04:00Z", "TOOL_CLOCK"),
    ("ARTIFACT_RECOVERED", "2026-01-01T00:05:00Z", "TOOL_CLOCK"),
]


def test_t01_unknown_case_404(client):
    r = tl(client, "nope")
    assert r.status_code == 404 and r.json()["detail"] == "Case not found"
    r = tl(client, "nope", kind="BAD")
    assert r.status_code == 404


def test_t02_empty_case(client):
    cid = case(client)
    r = tl(client, cid)
    assert r.status_code == 200
    j = r.json()
    assert j["case_id"] == cid and j["disclaimer"] == DISCLAIMER
    assert j["events"] == [] and j["undated"] == []
    assert j["summary"] == {"event_count": 0, "undated_count": 0, "earliest": None, "latest": None,
                            "by_kind": {}, "by_source": {}, "truncated": False}
    assert j["page"] == {"limit": 100, "offset": 0, "total": 0}


def test_t03_shape_and_sources(client):
    cid, eid = full(client)
    j = tl(client, cid).json()
    assert set(j) == {"case_id", "disclaimer", "events", "undated", "summary", "page"}
    assert set(j["summary"]) == {"event_count", "undated_count", "earliest", "latest", "by_kind", "by_source", "truncated"}
    assert set(j["page"]) == {"limit", "offset", "total"}
    by = {e["kind"]: e for e in j["events"]}
    for e in j["events"]:
        assert set(e) == {"event_id", "timestamp", "kind", "time_source", "evidence_id", "source", "raw_value", "flags", "detail"}
        assert set(e["source"]) == {"table", "field", "origin", "byte_offset"}
        assert e["flags"] == []
    assert by["EVIDENCE_REGISTERED"]["source"] == {"table": "evidence", "field": "registered_at", "origin": None, "byte_offset": None}
    assert by["EVIDENCE_REGISTERED"]["raw_value"] == "2026-01-01T00:00:00+00:00"
    assert by["EVIDENCE_REGISTERED"]["detail"] == {}
    assert by["ACQUISITION_DECLARED"]["source"]["field"] == "acquisition_time"
    assert by["FORMAT_DETECTED"]["source"] == {"table": "evidence", "field": "format_detection.detected_at", "origin": None, "byte_offset": None}
    assert by["VENDOR_DETECTED"]["source"]["field"] == "vendor_detection.detected_at"
    assert by["METADATA_EXTRACTED"]["source"] == {"table": "metadata_extractions", "field": "extracted_at", "origin": None, "byte_offset": None}
    assert by["CONTAINER_CREATION_TIME"]["source"] == {"table": "metadata_extractions", "field": "creation_time", "origin": "mp4:moov/mvhd", "byte_offset": 44}
    assert by["CONTAINER_MODIFICATION_TIME"]["source"]["byte_offset"] == 48
    assert by["CONTAINER_CREATION_TIME"]["raw_value"] == 1
    assert by["CONTAINER_CREATION_TIME"]["detail"] == {"note": None}
    assert by["ARTIFACT_RECOVERED"]["source"] == {"table": "recovered_artifacts", "field": "recovery_timestamp", "origin": None, "byte_offset": None}
    assert by["ARTIFACT_RECOVERED"]["detail"] == {"artifact_id": f"art-{eid[:8]}-100", "detected_type": "JPEG",
                                                  "status": "RECOVERED", "source_offset": 100}
    # undated shape
    cid2 = case(client)
    e2 = ev(client, cid2)
    setcol(e2, acquisition_time="garbage")
    u = tl(client, cid2).json()["undated"]
    assert len(u) == 1
    assert set(u[0]) == {"event_id", "kind", "time_source", "evidence_id", "source", "raw_value", "reason", "detail"}
    assert set(u[0]["source"]) == {"table", "field", "origin", "byte_offset"}


def test_t04_full_order(client):
    cid, eid = full(client)
    r = tl(client, cid)
    assert r.status_code == 200
    j = r.json()
    assert [(e["kind"], e["timestamp"], e["time_source"]) for e in j["events"]] == FULL_ORDER
    assert all(e["evidence_id"] == eid for e in j["events"])
    assert all(e["flags"] == [] for e in j["events"])
    assert j["undated"] == []


def test_t05_tie_break_and_determinism(client):
    cid = case(client)
    eid = ev(client, cid)
    setcol(eid, registered_at="2026-02-01T00:00:00Z", acquisition_time="2026-02-01T00:00:00+00:00")
    meta(eid, cid, [claim("creation_time", "2026-02-01T00:00:00Z")], extracted_at="2026-02-01T00:00:00Z")
    r1 = tl(client, cid).json()
    r2 = tl(client, cid).json()
    assert r1 == r2
    assert [e["kind"] for e in r1["events"]] == ["EVIDENCE_REGISTERED", "METADATA_EXTRACTED",
                                                 "ACQUISITION_DECLARED", "CONTAINER_CREATION_TIME"]
    ids = [e["event_id"] for e in r1["events"]]
    assert len(set(ids)) == 4
    for i in ids:
        assert len(i) == 16 and i == i.lower() and int(i, 16) >= 0


def test_t06_undated(client):
    cid = case(client)
    eid = ev(client, cid)
    setcol(eid, registered_at="2026-01-01T00:00:00Z", acquisition_time="yesterday evening")
    meta(eid, cid, [claim("creation_time", None, raw=0, note="NOT_SET: container value is zero"),
                    claim("modification_time", None, raw=99999999999, note="OUT_OF_RANGE")])
    j = tl(client, cid).json()
    assert sorted(e["kind"] for e in j["events"]) == ["EVIDENCE_REGISTERED", "METADATA_EXTRACTED"]
    got = {u["kind"]: (u["reason"], u["raw_value"], u["time_source"]) for u in j["undated"]}
    assert got == {
        "ACQUISITION_DECLARED": ("UNPARSEABLE_TIMESTAMP", "yesterday evening", "USER_DECLARED"),
        "CONTAINER_CREATION_TIME": ("NOT_SET", 0, "CONTAINER_CLAIM"),
        "CONTAINER_MODIFICATION_TIME": ("OUT_OF_RANGE", 99999999999, "CONTAINER_CLAIM"),
    }
    assert j["summary"]["event_count"] == 2 and j["summary"]["undated_count"] == 3
    j2 = tl(client, cid, kind="CONTAINER_CREATION_TIME").json()
    assert j2["events"] == [] and len(j2["undated"]) == 1 and j2["summary"]["undated_count"] == 1


def test_t07_naive_timestamp(client):
    cid = case(client)
    eid = ev(client, cid)
    setcol(eid, registered_at="2026-03-01T09:00:00+00:00", acquisition_time="2026-03-01T10:00:00")
    meta(eid, cid, [claim("creation_time", "2026-03-01T08:00:00Z")])
    by = {e["kind"]: e for e in tl(client, cid).json()["events"]}
    assert by["ACQUISITION_DECLARED"]["timestamp"] == "2026-03-01T10:00:00Z"
    assert "TIMEZONE_ASSUMED_UTC" in by["ACQUISITION_DECLARED"]["flags"]
    assert by["EVIDENCE_REGISTERED"]["flags"] == []
    assert by["CONTAINER_CREATION_TIME"]["flags"] == []


def test_t08_after_ingest_flag(client):
    cid = case(client)
    a, b, c = ev(client, cid), ev(client, cid), ev(client, cid)
    setcol(a, ingested_at="2026-01-01T00:00:00Z", acquisition_time="2027-01-01T00:00:00Z")
    meta(a, cid, [claim("creation_time", "2030-01-01T00:00:00Z"), claim("modification_time", "2025-01-01T00:00:00Z")])
    setcol(b, ingested_at="2026-01-01T00:00:00Z", acquisition_time="2026-01-01T00:00:00Z")
    setcol(c, acquisition_time="2099-01-01T00:00:00Z")
    j = tl(client, cid).json()["events"]
    flags = {(e["evidence_id"], e["kind"]): e["flags"] for e in j}
    assert flags[(a, "ACQUISITION_DECLARED")] == ["AFTER_INGEST"]
    assert flags[(a, "CONTAINER_CREATION_TIME")] == ["AFTER_INGEST"]
    assert flags[(a, "CONTAINER_MODIFICATION_TIME")] == []
    assert flags[(b, "ACQUISITION_DECLARED")] == []
    assert flags[(c, "ACQUISITION_DECLARED")] == []
    assert flags[(a, "EVIDENCE_INGESTED")] == []


def test_t09_plausible_range(client):
    cid = case(client)
    cases = {"1989-12-31T23:59:59Z": True, "1990-01-01T00:00:00Z": False,
             "2100-12-31T23:59:59Z": False, "2101-01-01T00:00:00Z": True}
    ids = {}
    for ts, flagged in cases.items():
        e = ev(client, cid)
        setcol(e, acquisition_time=ts)
        ids[e] = (ts, flagged)
    j = tl(client, cid, kind="ACQUISITION_DECLARED").json()["events"]
    assert len(j) == 4
    for e in j:
        ts, flagged = ids[e["evidence_id"]]
        assert e["timestamp"] == ts
        assert (e["flags"] == ["OUT_OF_PLAUSIBLE_RANGE"]) is flagged
        if not flagged:
            assert e["flags"] == []


def test_t10_unparseable_and_overflow(client):
    cid = case(client)
    bad = ["not a date", "2026-13-45T00:00:00Z", "0000-01-01T00:00:00Z",
           "9999-12-31T23:59:59-05:00", "0001-01-01T00:00:00+05:00"]
    for v in bad:
        setcol(ev(client, cid), acquisition_time=v)
    setcol(ev(client, cid), acquisition_time="")
    setcol(ev(client, cid), acquisition_time="   ")
    r = tl(client, cid, kind="ACQUISITION_DECLARED")
    assert r.status_code == 200
    j = r.json()
    assert j["events"] == []
    assert sorted(u["raw_value"] for u in j["undated"]) == sorted(bad)
    assert all(u["reason"] == "UNPARSEABLE_TIMESTAMP" for u in j["undated"])


def test_t11_hostile_values_and_no_leaks(client):
    cid = case(client)
    eid = ev(client, cid, "SECRETNAME.mp4")
    setcol(eid, acquisition_time="<script>alert(1)</script>" + "A" * 5000,
           stored_path="C:\\SECRET_DIR\\file", sha256="abc123secrethash")
    art(eid, cid, 5, "2026-01-01T00:05:00+00:00")
    r = tl(client, cid)
    assert r.status_code == 200
    for bad in ("SECRETNAME", "SECRET_PATH_X", "SECRET_DIR", "stored_path", "output_path", "abc123secrethash"):
        assert bad not in r.text
    j = r.json()
    assert len(j["undated"]) == 1
    rv = j["undated"][0]["raw_value"]
    assert rv.startswith("<script>") and len(rv) <= 200
    assert any(e["kind"] == "ARTIFACT_RECOVERED" for e in j["events"])


def test_t12_filters(client):
    cid, eid = full(client)
    other = ev(client, cid, "b.mp4")
    setcol(other, registered_at="2026-01-02T00:00:00Z")
    k = lambda **p: kinds_of(client, cid, **p)
    two = ["EVIDENCE_INGESTED", "EVIDENCE_HASHED"]
    assert k(kind="EVIDENCE_INGESTED") == ["EVIDENCE_INGESTED"]
    assert k(kind="EVIDENCE_INGESTED,EVIDENCE_HASHED") == two
    assert k(kind=" EVIDENCE_INGESTED , EVIDENCE_HASHED ") == two
    for bad in ("evidence_ingested", "NOPE", "EVIDENCE_INGESTED,NOPE"):
        r = tl(client, cid, kind=bad)
        assert r.status_code == 400 and r.json()["detail"] == "Invalid kind"
    assert k(time_source="CONTAINER_CLAIM") == ["CONTAINER_CREATION_TIME", "CONTAINER_MODIFICATION_TIME"]
    r = tl(client, cid, time_source="BAD")
    assert r.status_code == 400 and r.json()["detail"] == "Invalid time_source"
    r = tl(client, cid, evidence_id="nope")
    assert r.status_code == 200 and r.json()["events"] == [] and r.json()["undated"] == []
    assert len(tl(client, cid, evidence_id=eid).json()["events"]) == 10
    assert len(tl(client, cid).json()["events"]) == 11
    A, B = "2026-01-01T00:01:00Z", "2026-01-01T00:03:00+00:00"
    exp3 = ["EVIDENCE_INGESTED", "EVIDENCE_HASHED", "FORMAT_DETECTED"]
    assert k(start=A, end=B, evidence_id=eid) == exp3
    assert k(start="2026-01-01T01:01:00+01:00", end=B, evidence_id=eid) == exp3
    assert k(start="2026-01-01T00:01:00", end=B, evidence_id=eid) == exp3
    assert k(start="2026-01-01T00:04:00Z", evidence_id=eid) == ["METADATA_EXTRACTED", "ARTIFACT_RECOVERED"]
    assert k(end="2025-06-01T10:00:00Z") == ["CONTAINER_CREATION_TIME"]
    assert k(start=A, end=A, evidence_id=eid) == ["EVIDENCE_INGESTED"]
    assert k(kind="EVIDENCE_HASHED,EVIDENCE_INGESTED", start=A, end="2026-01-01T00:02:00.500000Z") == two
    r = tl(client, cid, start="garbage")
    assert r.status_code == 400 and r.json()["detail"] == "Invalid start"
    r = tl(client, cid, end="garbage")
    assert r.status_code == 400 and r.json()["detail"] == "Invalid end"
    r = tl(client, cid, start="2026-01-02T00:00:00Z", end="2026-01-01T00:00:00Z")
    assert r.status_code == 400 and r.json()["detail"] == "start must not be after end"


def test_t13_pagination(client):
    cid, eid = full(client)
    full_ids = [e["event_id"] for e in tl(client, cid).json()["events"]]
    assert len(full_ids) == 10
    got = []
    for off, n in ((0, 3), (3, 3), (6, 3), (9, 1)):
        j = tl(client, cid, limit=3, offset=off).json()
        assert j["page"] == {"limit": 3, "offset": off, "total": 10}
        assert j["summary"]["event_count"] == 10
        assert len(j["events"]) == n
        got += [e["event_id"] for e in j["events"]]
    assert got == full_ids
    j = tl(client, cid, offset=100).json()
    assert j["events"] == [] and j["page"]["total"] == 10
    assert tl(client, cid).json()["page"] == {"limit": 100, "offset": 0, "total": 10}
    for p in ({"limit": 0}, {"limit": 1001}, {"offset": -1}):
        assert tl(client, cid, **p).status_code == 422
    assert tl(client, cid, limit=1000).status_code == 200


def test_t14_summary(client):
    cid, eid = full(client)
    s = tl(client, cid, limit=2).json()["summary"]
    assert s["event_count"] == 10 and s["undated_count"] == 0 and s["truncated"] is False
    assert s["earliest"] == "2025-06-01T10:00:00Z" and s["latest"] == "2026-01-01T00:05:00Z"
    assert s["by_kind"] == {k: 1 for k, _, _ in FULL_ORDER}
    assert s["by_source"] == {"TOOL_CLOCK": 7, "USER_DECLARED": 1, "CONTAINER_CLAIM": 2}
    s2 = tl(client, cid, time_source="CONTAINER_CLAIM").json()["summary"]
    assert s2["event_count"] == 2 and s2["by_source"] == {"CONTAINER_CLAIM": 2}
    assert s2["earliest"] == "2025-06-01T10:00:00Z" and s2["latest"] == "2025-06-01T11:00:00Z"


def test_t15_case_isolation(client):
    ca, ea = full(client)
    cb, eb = full(client)
    ja, jb = tl(client, ca).json(), tl(client, cb).json()
    assert {e["evidence_id"] for e in ja["events"]} == {ea}
    assert {e["evidence_id"] for e in jb["events"]} == {eb}
    assert not ({e["event_id"] for e in ja["events"]} & {e["event_id"] for e in jb["events"]})


def snap():
    with get_connection() as c:
        out = {}
        for t in ("cases", "evidence", "metadata_extractions", "recovered_artifacts", "audit_log"):
            out[t] = [tuple(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY rowid")]
        out["v"] = c.execute("PRAGMA user_version").fetchone()[0]
        out["tables"] = sorted(r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    return out


def test_t16_no_side_effects(client):
    cid, eid = full(client)
    before = snap()
    assert before["v"] == 8
    tl(client, cid)
    tl(client, cid, kind="EVIDENCE_HASHED", limit=1)
    tl(client, cid, kind="BAD")
    tl(client, "nope")
    tl(client, cid, start="x")
    after = snap()
    assert before == after
    assert not any("timeline" in t for t in after["tables"])
    n = len(client.get("/api/audit-log?limit=500").json())
    tl(client, cid)
    assert len(client.get("/api/audit-log?limit=500").json()) == n


def test_t17_row_cap(client, monkeypatch):
    import app.services.timeline_service as ts_mod
    cid = case(client)
    eid = ev(client, cid)
    for i in range(3):
        art(eid, cid, i, f"2026-01-01T00:0{i}:00Z")
    base = tl(client, cid, kind="ARTIFACT_RECOVERED").json()
    assert len(base["events"]) == 3 and base["summary"]["truncated"] is False
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 2)
    j = tl(client, cid, kind="ARTIFACT_RECOVERED").json()
    assert len(j["events"]) == 2 and j["summary"]["truncated"] is True
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 3)
    j = tl(client, cid, kind="ARTIFACT_RECOVERED").json()
    assert len(j["events"]) == 3 and j["summary"]["truncated"] is False


def test_t18_malformed_metadata(client):
    cid = case(client)
    e1, e2, e3 = ev(client, cid), ev(client, cid), ev(client, cid)
    setcol(e1, registered_at="2026-01-01T00:00:00Z")
    meta(e1, cid, [5, None, "x", {"field": "creation_time"},
                   {"field": "modification_time", "raw_value": 1, "interpreted_value": 12345},
                   {"field": "unknown_field", "interpreted_value": "2026-01-01T00:00:00Z"}])
    meta(e2, cid, None, result=[1, 2])
    meta(e3, cid, None, result={"fields": "notalist"})
    r = tl(client, cid)
    assert r.status_code == 200
    j = r.json()
    und = [u for u in j["undated"] if u["evidence_id"] == e1]
    assert len(und) == 2 and all(u["reason"] == "UNPARSEABLE_TIMESTAMP" for u in und)
    assert len({u["event_id"] for u in und}) == 2
    assert not [u for u in j["undated"] if u["evidence_id"] in (e2, e3)]
    assert kinds_of(client, cid, kind="METADATA_EXTRACTED") == ["METADATA_EXTRACTED"] * 3
    assert not any(e["kind"].startswith("CONTAINER_") for e in j["events"])


def test_t19_corrupt_columns(client):
    cid = case(client)
    e = [ev(client, cid) for _ in range(5)]
    pairs = [("{bad", "[1,2]"),
             ('{"detected_at": 12345}', '"just a string"'),
             ('{"detected_at": ""}', '{"detected_at": null}'),
             ('{"detected_at": "2026-01-01T00:00:00+00:00"}', None),
             ('{"detected_at": "garbage"}', None)]
    for eid, (f, v) in zip(e, pairs):
        sql("UPDATE evidence SET format_detection = ?, vendor_detection = ? WHERE evidence_id = ?", (f, v, eid))
    r = tl(client, cid)
    assert r.status_code == 200
    j = r.json()
    fd = [x for x in j["events"] if x["kind"] == "FORMAT_DETECTED"]
    assert [x["evidence_id"] for x in fd] == [e[3]]
    assert not [x for x in j["events"] if x["kind"] == "VENDOR_DETECTED"]
    assert len([x for x in j["events"] if x["kind"] == "EVIDENCE_REGISTERED"]) == 5
    assert [(u["kind"], u["evidence_id"], u["reason"]) for u in j["undated"]] == [
        ("FORMAT_DETECTED", e[4], "UNPARSEABLE_TIMESTAMP")]


def test_t20_bulk_sorting(client):
    cid = case(client)
    expected = []
    for i in range(60):
        e = ev(client, cid)
        ts = f"2026-05-01T10:{59 - i:02d}:00Z"
        setcol(e, registered_at=ts)
        expected.append(ts)
    r = tl(client, cid, kind="EVIDENCE_REGISTERED", limit=1000)
    assert r.status_code == 200
    j = r.json()
    assert [x["timestamp"] for x in j["events"]] == sorted(expected)
    assert j["page"]["total"] == 60 and j["summary"]["by_kind"] == {"EVIDENCE_REGISTERED": 60}
