import hashlib
import json
from app.db.database import get_connection
from app.repositories.metadata_repository import MetadataRepository

DISCLAIMER = ("A gap means no evidence file in this case covers that time. It does not prove deletion, "
              "overwriting or tampering. Times are container claims, corrected only where a calibration exists. "
              "A file is assumed to start at its creation_time and to last its duration. Files with unknown "
              "length or time are listed separately and are not used.")
NODUR = object()
GAP_KEYS = {"gap_id", "group_label", "start", "end", "length_seconds", "length_min_seconds",
            "length_max_seconds", "certainty", "before_evidence_id", "after_evidence_id"}
GROUP_KEYS = {"evidence_id", "case_id", "group_label", "is_default", "set_at"}


def T(hms, day="2025-06-01"):
    return f"{day}T{hms}Z"


def case(client):
    r = client.post("/api/cases", json={"case_name": "C"})
    assert r.status_code == 201
    return r.json()["case_id"]


def ev(client, cid, name="secretvideo.mp4"):
    r = client.post(f"/api/cases/{cid}/evidence",
                    json={"original_filename": name, "evidence_type": "BIN", "file_size": 10})
    assert r.status_code == 201
    return r.json()["evidence_id"]


def claim(name, interp, raw=1, note=None, offset=44):
    return {"field": name, "raw_value": raw, "interpreted_value": interp,
            "source": "mp4:moov/mvhd", "byte_offset": offset, "note": note}


def meta_raw(eid, cid, fields):
    r = {"container": "MP4", "parser_version": "1", "status": "OK", "fields": fields, "errors": []}
    MetadataRepository.upsert("EVIDENCE", eid, cid, "MP4", "1", "OK", r, "2026-01-01T00:04:00Z")


def meta(eid, cid, start, dur=NODUR):
    fields = []
    if start is not None:
        fields.append(claim("creation_time", start))
    if dur is not NODUR:
        fields.append({"field": "duration", "raw_value": 1, "interpreted_value": dur,
                       "source": "mp4:moov/mvhd", "byte_offset": 60, "note": None})
    meta_raw(eid, cid, fields)


def setgroup(client, eid, label):
    return client.put(f"/api/evidence/{eid}/group", json={"group_label": label})


def getgroup(client, eid):
    return client.get(f"/api/evidence/{eid}/group")


def setcal(client, eid, **o):
    b = {"device_time": "2026-01-01T10:00:00Z", "reference_time": "2026-01-01T10:00:00Z", "uncertainty_seconds": 0}
    b.update(o)
    r = client.post(f"/api/evidence/{eid}/calibration", json=b)
    assert r.status_code == 201, r.text
    return r


def mk(client, cid, start, dur=NODUR, group=None, name="secretvideo.mp4"):
    e = ev(client, cid, name)
    meta(e, cid, start, dur)
    if group is not None:
        assert setgroup(client, e, group).status_code == 200
    return e


def gaps(client, cid, **p):
    return client.get(f"/api/cases/{cid}/gaps", params=p)


def G(client, cid, **p):
    r = gaps(client, cid, **p)
    assert r.status_code == 200, r.text
    return r.json()


def group_audit(client, eid):
    rows = client.get(f"/api/audit-log?evidence_id={eid}&limit=500").json()
    return [a for a in rows if a["action"] == "GROUP_SET"]


def test_g01_unknown_ids(client):
    r = gaps(client, "nope")
    assert r.status_code == 404 and r.json()["detail"] == "Case not found"
    r = setgroup(client, "nope", "CamA")
    assert r.status_code == 404 and r.json()["detail"] == "Evidence not found"
    r = getgroup(client, "nope")
    assert r.status_code == 404 and r.json()["detail"] == "Evidence not found"
    rows = group_audit(client, "nope")
    assert len(rows) == 1 and rows[0]["outcome"] == "NOT_FOUND" and rows[0]["details"]["reason"] == "UNKNOWN_EVIDENCE"


def test_g02_empty_case(client):
    cid = case(client)
    j = G(client, cid)
    assert j == {"case_id": cid, "disclaimer": DISCLAIMER, "groups": [], "gaps": [], "unknown_length": [],
                 "unplaced": [], "summary": {"gap_count": 0, "total_gap_seconds": 0.0, "longest_gap_seconds": 0.0,
                                             "truncated": False},
                 "page": {"limit": 100, "offset": 0, "total": 0}}


def test_g03_group_set_get(client):
    cid = case(client)
    e = ev(client, cid)
    g = getgroup(client, e)
    assert g.status_code == 200
    assert g.json() == {"evidence_id": e, "case_id": cid, "group_label": "DEFAULT", "is_default": True, "set_at": None}
    r = setgroup(client, e, "  CamA  ")
    assert r.status_code == 200
    j = r.json()
    assert set(j) == GROUP_KEYS
    assert j["evidence_id"] == e and j["case_id"] == cid
    assert j["group_label"] == "CamA" and j["is_default"] is False and j["set_at"].endswith("Z")
    assert getgroup(client, e).json() == j
    j2 = setgroup(client, e, "CamB").json()
    assert j2["group_label"] == "CamB" and getgroup(client, e).json() == j2
    j3 = setgroup(client, e, "DEFAULT").json()
    assert j3["group_label"] == "DEFAULT" and j3["is_default"] is False
    with get_connection() as c:
        n = c.execute("SELECT COUNT(*) FROM evidence_groups WHERE evidence_id = ?", (e,)).fetchone()[0]
    assert n == 1


def test_g04_group_validation_and_audit(client):
    cid = case(client)
    e = ev(client, cid)
    for bad in ({}, {"group_label": ""}, {"group_label": 5}, {"group_label": None}, {"group_label": "x" * 65}):
        assert client.put(f"/api/evidence/{e}/group", json=bad).status_code == 422, bad
    assert client.put(f"/api/evidence/{e}/group", content="not json",
                      headers={"content-type": "application/json"}).status_code == 422
    r = setgroup(client, e, "   ")
    assert r.status_code == 400 and r.json()["detail"] == "Invalid group_label"
    assert getgroup(client, e).json()["is_default"] is True
    assert setgroup(client, e, "a" * 64).status_code == 200
    hostile = "<b>'; DROP TABLE x;--"
    assert setgroup(client, e, hostile).json()["group_label"] == hostile
    assert getgroup(client, e).json()["group_label"] == hostile
    rows = group_audit(client, e)
    assert [(a["outcome"], a["http_status"]) for a in rows] == [("REJECTED", 400), ("SUCCESS", 200), ("SUCCESS", 200)]
    assert rows[0]["details"]["reason"] == "INVALID_GROUP_LABEL"
    assert all(a["details"] == {} for a in rows[1:])
    assert all(a["case_id"] == cid and a["evidence_id"] == e for a in rows)
    assert "DROP TABLE" not in json.dumps(rows)


def test_g05_basic_gap(client):
    cid = case(client)
    a = mk(client, cid, T("10:00:00"), 1800)
    b = mk(client, cid, T("10:45:00"), 600)
    j = G(client, cid)
    assert set(j) == {"case_id", "disclaimer", "groups", "gaps", "unknown_length", "unplaced", "summary", "page"}
    assert j["disclaimer"] == DISCLAIMER and j["case_id"] == cid
    assert len(j["gaps"]) == 1
    g = j["gaps"][0]
    assert set(g) == GAP_KEYS
    assert g["group_label"] == "DEFAULT" and g["start"] == T("10:30:00") and g["end"] == T("10:45:00")
    assert g["length_seconds"] == 900.0 and g["length_min_seconds"] == 900.0 and g["length_max_seconds"] == 900.0
    assert g["certainty"] == "CERTAIN" and g["before_evidence_id"] == a and g["after_evidence_id"] == b
    assert len(g["gap_id"]) == 16 and g["gap_id"] == g["gap_id"].lower()
    assert j["summary"] == {"gap_count": 1, "total_gap_seconds": 900.0, "longest_gap_seconds": 900.0, "truncated": False}
    assert j["groups"] == [{"group_label": "DEFAULT", "interval_count": 2, "gap_count": 1}]
    assert j["page"] == {"limit": 100, "offset": 0, "total": 1}
    assert j["unknown_length"] == [] and j["unplaced"] == []


def test_g06_touching_overlap_and_running_max(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800)
    mk(client, cid, T("10:30:00"), 60)
    assert G(client, cid)["gaps"] == []
    cid2 = case(client)
    a = mk(client, cid2, T("10:00:00"), 7200)
    mk(client, cid2, T("10:30:00"), 60)
    mk(client, cid2, T("11:00:00"), 60)
    d = mk(client, cid2, T("12:30:00"), 60)
    j = G(client, cid2)
    assert len(j["gaps"]) == 1
    g = j["gaps"][0]
    assert g["start"] == T("12:00:00") and g["end"] == T("12:30:00") and g["length_seconds"] == 1800.0
    assert g["before_evidence_id"] == a and g["after_evidence_id"] == d


def test_g07_groups_are_independent(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 600, "CamA")
    mk(client, cid, T("10:20:00"), 600, "CamA")
    mk(client, cid, T("10:00:00"), 600, "CamB")
    mk(client, cid, T("10:10:00"), 600, "CamB")
    j = G(client, cid)
    assert len(j["gaps"]) == 1
    g = j["gaps"][0]
    assert g["group_label"] == "CamA" and g["start"] == T("10:10:00") and g["end"] == T("10:20:00")
    assert g["length_seconds"] == 600.0
    assert j["groups"] == [{"group_label": "CamA", "interval_count": 2, "gap_count": 1},
                           {"group_label": "CamB", "interval_count": 2, "gap_count": 0}]
    assert j["summary"]["gap_count"] == 1


def test_g08_group_filter(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 600, "CamA")
    mk(client, cid, T("10:20:00"), 600, "CamA")
    mk(client, cid, T("10:00:00"), 600, "CamB")
    mk(client, cid, T("10:10:00"), 600, "CamB")
    j = G(client, cid, group="CamA")
    assert len(j["gaps"]) == 1 and j["groups"] == [{"group_label": "CamA", "interval_count": 2, "gap_count": 1}]
    j = G(client, cid, group="CamB")
    assert j["gaps"] == [] and j["groups"] == [{"group_label": "CamB", "interval_count": 2, "gap_count": 0}]
    j = G(client, cid, group="nope")
    assert j["gaps"] == [] and j["groups"] == [] and j["unknown_length"] == [] and j["unplaced"] == []
    assert j["page"]["total"] == 0 and j["summary"]["gap_count"] == 0
    assert G(client, cid, group="cama")["gaps"] == []


def test_g09_unknown_length(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 60)
    none_field = mk(client, cid, T("09:00:00"))
    none_value = mk(client, cid, T("09:00:00"), None)
    neg = mk(client, cid, T("09:00:00"), -5)
    text = mk(client, cid, T("09:00:00"), "abc")
    boolean = mk(client, cid, T("09:00:00"), True)
    huge = mk(client, cid, T("09:00:00"), 3153600001)
    nan = mk(client, cid, T("09:00:00"), float("nan"))
    j = G(client, cid)
    got = {u["evidence_id"]: u["reason"] for u in j["unknown_length"]}
    assert got == {none_field: "NO_DURATION", none_value: "NO_DURATION", neg: "INVALID_DURATION",
                   text: "INVALID_DURATION", boolean: "INVALID_DURATION", huge: "INVALID_DURATION",
                   nan: "INVALID_DURATION"}
    for u in j["unknown_length"]:
        assert set(u) == {"evidence_id", "group_label", "reason", "start"}
        assert u["start"] == T("09:00:00") and u["group_label"] == "DEFAULT"
    ids = [u["evidence_id"] for u in j["unknown_length"]]
    assert ids == sorted(ids)
    assert j["gaps"] == [] and j["groups"] == [{"group_label": "DEFAULT", "interval_count": 1, "gap_count": 0}]


def test_g10_unplaced(client):
    cid = case(client)
    e1 = ev(client, cid)
    e2 = ev(client, cid)
    meta(e2, cid, None, 60)
    e3 = ev(client, cid)
    meta_raw(e3, cid, [claim("creation_time", None, raw=0, note="NOT_SET: container value is zero")])
    e4 = mk(client, cid, "9999-12-31T00:00:00Z", 60)
    setcal(client, e4, device_time="2026-01-01T00:00:00Z", reference_time="2026-01-02T03:46:40Z")
    j = G(client, cid)
    got = {u["evidence_id"]: u["reason"] for u in j["unplaced"]}
    assert got == {e1: "NO_CREATION_TIME", e2: "NO_CREATION_TIME", e3: "NO_CREATION_TIME",
                   e4: "CALIBRATION_OUT_OF_RANGE"}
    for u in j["unplaced"]:
        assert set(u) == {"evidence_id", "group_label", "reason"} and u["group_label"] == "DEFAULT"
    ids = [u["evidence_id"] for u in j["unplaced"]]
    assert ids == sorted(ids)
    assert j["gaps"] == [] and j["unknown_length"] == []


def test_g11_calibration_is_applied(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800)
    b = mk(client, cid, T("10:45:00"), 600)
    setcal(client, b, device_time="2026-01-01T10:00:00Z", reference_time="2026-01-01T10:01:00Z")
    g = G(client, cid)["gaps"][0]
    assert g["start"] == T("10:30:00") and g["end"] == T("10:46:00")
    assert g["length_seconds"] == 960.0 and g["length_min_seconds"] == 960.0 and g["length_max_seconds"] == 960.0
    assert g["certainty"] == "CERTAIN"


def test_g12_uncertainty_ranges(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800)
    b = mk(client, cid, T("10:45:00"), 600)
    setcal(client, b, uncertainty_seconds=30)
    g = G(client, cid)["gaps"][0]
    assert (g["length_seconds"], g["length_min_seconds"], g["length_max_seconds"]) == (900.0, 870.0, 930.0)
    assert g["certainty"] == "CERTAIN"
    cid2 = case(client)
    mk(client, cid2, T("10:00:00"), 1800)
    b2 = mk(client, cid2, T("10:31:00"), 600)
    setcal(client, b2, uncertainty_seconds=120)
    g2 = G(client, cid2)["gaps"][0]
    assert (g2["length_seconds"], g2["length_min_seconds"], g2["length_max_seconds"]) == (60.0, 0.0, 180.0)
    assert g2["certainty"] == "UNCERTAIN"
    cid3 = case(client)
    a3 = mk(client, cid3, T("10:00:00"), 1800)
    mk(client, cid3, T("10:45:00"), 600)
    setcal(client, a3, uncertainty_seconds=10)
    g3 = G(client, cid3)["gaps"][0]
    assert (g3["length_seconds"], g3["length_min_seconds"], g3["length_max_seconds"]) == (900.0, 890.0, 910.0)
    assert g3["certainty"] == "CERTAIN"


def test_g13_min_gap_filter(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 600)
    mk(client, cid, T("10:20:00"), 60)
    mk(client, cid, T("10:22:00"), 60)
    lens = lambda **p: [g["length_seconds"] for g in G(client, cid, **p)["gaps"]]
    assert lens() == [600.0, 60.0]
    assert lens(min_gap_seconds=0) == [600.0, 60.0]
    assert lens(min_gap_seconds=60) == [600.0, 60.0]
    assert lens(min_gap_seconds=60.5) == [600.0]
    assert lens(min_gap_seconds=100) == [600.0]
    assert lens(min_gap_seconds=600) == [600.0]
    assert lens(min_gap_seconds=600.5) == []
    s = G(client, cid, min_gap_seconds=100)
    assert s["summary"]["gap_count"] == 1 and s["page"]["total"] == 1
    assert s["groups"] == [{"group_label": "DEFAULT", "interval_count": 3, "gap_count": 1}]
    assert gaps(client, cid, min_gap_seconds=-1).status_code == 422
    assert gaps(client, cid, min_gap_seconds=31536001).status_code == 422


def test_g14_paging(client):
    cid = case(client)
    for h in range(10, 16):
        mk(client, cid, T(f"{h}:00:00"), 60)
    full = G(client, cid)
    assert len(full["gaps"]) == 5 and all(g["length_seconds"] == 3540.0 for g in full["gaps"])
    assert [g["start"] for g in full["gaps"]] == [T(f"{h}:01:00") for h in range(10, 15)]
    ids = [g["gap_id"] for g in full["gaps"]]
    assert len(set(ids)) == 5
    got = []
    for off, n in ((0, 2), (2, 2), (4, 1)):
        j = G(client, cid, limit=2, offset=off)
        assert j["page"] == {"limit": 2, "offset": off, "total": 5} and len(j["gaps"]) == n
        assert j["summary"] == {"gap_count": 5, "total_gap_seconds": 17700.0, "longest_gap_seconds": 3540.0,
                                "truncated": False}
        got += [g["gap_id"] for g in j["gaps"]]
    assert got == ids
    assert G(client, cid, offset=100)["gaps"] == []
    for p in ({"limit": 0}, {"limit": 1001}, {"offset": -1}):
        assert gaps(client, cid, **p).status_code == 422
    assert gaps(client, cid, limit=1000).status_code == 200


def test_g15_sort_by_group_then_time(client):
    cid = case(client)
    mk(client, cid, T("12:00:00"), 60, "CamA")
    mk(client, cid, T("13:00:00"), 60, "CamA")
    mk(client, cid, T("09:00:00"), 60, "CamB")
    mk(client, cid, T("10:00:00"), 60, "CamB")
    assert [g["group_label"] for g in G(client, cid)["gaps"]] == ["CamA", "CamB"]


def test_g16_order_comes_from_time_not_registration(client):
    cid = case(client)
    late = mk(client, cid, T("10:45:00"), 600)
    early = mk(client, cid, T("10:00:00"), 1800)
    g = G(client, cid)["gaps"][0]
    assert g["before_evidence_id"] == early and g["after_evidence_id"] == late
    assert g["start"] == T("10:30:00") and g["end"] == T("10:45:00")


def test_g17_deterministic_ids(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 60)
    mk(client, cid, T("11:00:00"), 60)
    j1, j2 = G(client, cid), G(client, cid)
    assert j1 == j2
    g = j1["gaps"][0]
    exp = hashlib.sha256(f"GAP|{g['group_label']}|{g['before_evidence_id']}|{g['after_evidence_id']}".encode()).hexdigest()[:16]
    assert g["gap_id"] == exp


def snap():
    out = {}
    with get_connection() as c:
        for t in ("cases", "evidence", "metadata_extractions", "recovered_artifacts", "calibration_references",
                  "evidence_groups", "audit_log"):
            out[t] = [tuple(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY rowid")]
    return out


def test_g18_no_side_effects(client):
    cid = case(client)
    a = mk(client, cid, T("10:00:00"), 60, "CamA")
    mk(client, cid, T("11:00:00"), 60, "CamA")
    before = snap()
    G(client, cid)
    G(client, cid, group="CamA", min_gap_seconds=5, limit=1, offset=0)
    gaps(client, "nope")
    gaps(client, cid, limit=0)
    getgroup(client, a)
    getgroup(client, "nope")
    assert snap() == before


def test_g19_no_leaks(client):
    cid = case(client)
    e = mk(client, cid, T("10:00:00"), 60, name="SECRETNAME.mp4")
    mk(client, cid, T("11:00:00"), 60)
    with get_connection() as c:
        c.execute("UPDATE evidence SET stored_path='C:\\SECRET_DIR\\f', sha256='abc123secrethash' WHERE evidence_id=?", (e,))
    texts = [gaps(client, cid).text, setgroup(client, e, "CamA").text, getgroup(client, e).text]
    for t in texts:
        for bad in ("SECRETNAME", "SECRET_DIR", "abc123secrethash", "stored_path", "output_path", "original_filename"):
            assert bad not in t


def test_g20_truncation(client, monkeypatch):
    import app.services.timeline_service as ts_mod
    cid = case(client)
    for h in (10, 11, 12):
        mk(client, cid, T(f"{h}:00:00"), 60)
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 2)
    assert G(client, cid)["summary"]["truncated"] is True
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 3)
    j = G(client, cid)
    assert j["summary"]["truncated"] is False and j["summary"]["gap_count"] == 2


def test_g21_schema(client):
    with get_connection() as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 10
        info = list(c.execute("PRAGMA table_info(evidence_groups)"))
        idx = {r[1] for r in c.execute("PRAGMA index_list(evidence_groups)")}
    assert {r[1] for r in info} == {"evidence_id", "case_id", "group_label", "set_at", "set_by"}
    assert {r[1] for r in info if r[5]} == {"evidence_id"}
    assert "idx_evidence_groups_case" in idx


def test_g22_case_isolation(client):
    ids = []
    for _ in range(2):
        cid = case(client)
        a = mk(client, cid, T("10:00:00"), 60, "CamA")
        b = mk(client, cid, T("11:00:00"), 60, "CamA")
        ids.append((cid, a, b))
    for cid, a, b in ids:
        j = G(client, cid)
        assert len(j["gaps"]) == 1
        assert j["gaps"][0]["before_evidence_id"] == a and j["gaps"][0]["after_evidence_id"] == b
        assert j["groups"] == [{"group_label": "CamA", "interval_count": 2, "gap_count": 1}]


def test_g23_group_change_changes_gaps(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 60)
    b = mk(client, cid, T("11:00:00"), 60)
    assert len(G(client, cid)["gaps"]) == 1
    setgroup(client, b, "X")
    j = G(client, cid)
    assert j["gaps"] == []
    assert j["groups"] == [{"group_label": "DEFAULT", "interval_count": 1, "gap_count": 0},
                           {"group_label": "X", "interval_count": 1, "gap_count": 0}]
    setgroup(client, b, "DEFAULT")
    assert len(G(client, cid)["gaps"]) == 1


def test_g24_fractional_and_zero_duration(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 0)
    mk(client, cid, "2025-06-01T10:00:00.500000Z", 1)
    g = G(client, cid)["gaps"][0]
    assert g["start"] == T("10:00:00") and g["end"] == "2025-06-01T10:00:00.500000Z"
    assert (g["length_seconds"], g["length_min_seconds"], g["length_max_seconds"]) == (0.5, 0.5, 0.5)
    assert g["certainty"] == "CERTAIN"


def test_g25_overflow_and_max_duration(client):
    cid = case(client)
    over = mk(client, cid, "9999-12-30T00:00:00Z", 315360000)
    ok = mk(client, cid, T("10:00:00"), 315360000)
    j = G(client, cid)
    assert [(u["evidence_id"], u["reason"], u["start"]) for u in j["unknown_length"]] == [
        (over, "TIME_OUT_OF_RANGE", "9999-12-30T00:00:00Z")]
    assert j["groups"] == [{"group_label": "DEFAULT", "interval_count": 1, "gap_count": 0}]
    assert j["gaps"] == [] and j["unplaced"] == []
    assert ok not in [u["evidence_id"] for u in j["unknown_length"]]
