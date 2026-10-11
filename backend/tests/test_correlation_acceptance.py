import hashlib
import json
from app.db.database import get_connection
from app.repositories.metadata_repository import MetadataRepository

DISCLAIMER = ("Temporal overlap means files from different groups claim to cover the same time. It is not proof "
              "that they show the same event, place or person. Times are container claims, corrected only where a "
              "calibration exists. Overlap is computed from nominal times; a window marked uncertain involves a "
              "calibration with non-zero uncertainty. Files with unknown length or time are listed separately and "
              "are not used.")
NODUR = object()
WIN_KEYS = {"window_id", "start", "end", "length_seconds", "groups", "group_count", "members", "uncertain"}


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


def corr(client, cid, **p):
    return client.get(f"/api/cases/{cid}/correlation", params=p)


def C(client, cid, **p):
    r = corr(client, cid, **p)
    assert r.status_code == 200, r.text
    return r.json()


def wid(groups, start):
    return hashlib.sha256(("OVERLAP|" + "|".join(groups) + "|" + start).encode()).hexdigest()[:16]


def test_x01_unknown_case_and_422(client):
    r = corr(client, "nope")
    assert r.status_code == 404 and r.json()["detail"] == "Case not found"
    cid = case(client)
    for p in ({"min_groups": 1}, {"min_groups": 51}, {"min_overlap_seconds": -1},
              {"min_overlap_seconds": 31536001}, {"limit": 0}, {"limit": 1001}, {"offset": -1}):
        assert corr(client, cid, **p).status_code == 422, p
        assert corr(client, "nope", **p).status_code == 422, p
    assert corr(client, cid, min_groups=50, limit=1000).status_code == 200


def test_x02_empty_case(client):
    cid = case(client)
    assert C(client, cid) == {
        "case_id": cid, "disclaimer": DISCLAIMER, "groups": [], "windows": [], "unknown_length": [], "unplaced": [],
        "summary": {"window_count": 0, "total_overlap_seconds": 0.0, "longest_overlap_seconds": 0.0,
                    "max_simultaneous_groups": 0, "truncated": False},
        "page": {"limit": 100, "offset": 0, "total": 0}}


def test_x03_basic_overlap(client):
    cid = case(client)
    a = mk(client, cid, T("10:00:00"), 1800, "CamA")
    b = mk(client, cid, T("10:20:00"), 1800, "CamB")
    j = C(client, cid)
    assert set(j) == {"case_id", "disclaimer", "groups", "windows", "unknown_length", "unplaced", "summary", "page"}
    assert j["disclaimer"] == DISCLAIMER
    assert len(j["windows"]) == 1
    w = j["windows"][0]
    assert set(w) == WIN_KEYS
    assert w["start"] == T("10:20:00") and w["end"] == T("10:30:00") and w["length_seconds"] == 600.0
    assert w["groups"] == ["CamA", "CamB"] and w["group_count"] == 2 and w["uncertain"] is False
    assert w["members"] == [{"group_label": "CamA", "evidence_ids": [a]}, {"group_label": "CamB", "evidence_ids": [b]}]
    assert w["window_id"] == wid(["CamA", "CamB"], T("10:20:00"))
    assert j["summary"] == {"window_count": 1, "total_overlap_seconds": 600.0, "longest_overlap_seconds": 600.0,
                            "max_simultaneous_groups": 2, "truncated": False}
    assert j["groups"] == [{"group_label": "CamA", "interval_count": 1}, {"group_label": "CamB", "interval_count": 1}]
    assert j["page"] == {"limit": 100, "offset": 0, "total": 1}


def test_x04_touching_across_groups_is_not_overlap(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800, "CamA")
    mk(client, cid, T("10:30:00"), 600, "CamB")
    j = C(client, cid)
    assert j["windows"] == [] and j["summary"]["window_count"] == 0


def test_x05_containment(client):
    cid = case(client)
    a = mk(client, cid, T("10:00:00"), 3600, "CamA")
    b = mk(client, cid, T("10:10:00"), 600, "CamB")
    w = C(client, cid)["windows"][0]
    assert (w["start"], w["end"], w["length_seconds"]) == (T("10:10:00"), T("10:20:00"), 600.0)
    assert w["members"] == [{"group_label": "CamA", "evidence_ids": [a]}, {"group_label": "CamB", "evidence_ids": [b]}]


def test_x06_same_group_never_correlates(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800, "CamA")
    mk(client, cid, T("10:10:00"), 1800, "CamA")
    j = C(client, cid)
    assert j["windows"] == [] and j["groups"] == [{"group_label": "CamA", "interval_count": 2}]


def test_x07_union_inside_group(client):
    cid = case(client)
    a1 = mk(client, cid, T("10:00:00"), 600, "CamA")
    a2 = mk(client, cid, T("10:10:00"), 600, "CamA")
    b = mk(client, cid, T("10:05:00"), 1800, "CamB")
    j = C(client, cid)
    assert len(j["windows"]) == 1
    w = j["windows"][0]
    assert (w["start"], w["end"], w["length_seconds"]) == (T("10:05:00"), T("10:20:00"), 900.0)
    assert w["members"] == [{"group_label": "CamA", "evidence_ids": sorted([a1, a2])},
                            {"group_label": "CamB", "evidence_ids": [b]}]


def test_x08_three_groups_split_windows(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 3600, "CamA")
    mk(client, cid, T("10:10:00"), 1800, "CamB")
    mk(client, cid, T("10:20:00"), 600, "CamC")
    j = C(client, cid)
    got = [(w["start"], w["end"], w["groups"], w["group_count"], w["length_seconds"]) for w in j["windows"]]
    assert got == [(T("10:10:00"), T("10:20:00"), ["CamA", "CamB"], 2, 600.0),
                   (T("10:20:00"), T("10:30:00"), ["CamA", "CamB", "CamC"], 3, 600.0),
                   (T("10:30:00"), T("10:40:00"), ["CamA", "CamB"], 2, 600.0)]
    assert len({w["window_id"] for w in j["windows"]}) == 3
    assert j["summary"] == {"window_count": 3, "total_overlap_seconds": 1800.0, "longest_overlap_seconds": 600.0,
                            "max_simultaneous_groups": 3, "truncated": False}
    j3 = C(client, cid, min_groups=3)
    assert [(w["start"], w["groups"]) for w in j3["windows"]] == [(T("10:20:00"), ["CamA", "CamB", "CamC"])]
    assert j3["summary"]["max_simultaneous_groups"] == 3
    assert C(client, cid, min_groups=4)["windows"] == []


def test_x09_min_overlap_filter(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800, "CamA")
    mk(client, cid, T("10:20:00"), 1800, "CamB")
    n = lambda **p: len(C(client, cid, **p)["windows"])
    assert n() == 1 and n(min_overlap_seconds=0) == 1 and n(min_overlap_seconds=600) == 1
    assert n(min_overlap_seconds=600.5) == 0
    j = C(client, cid, min_overlap_seconds=601)
    assert j["summary"]["window_count"] == 0 and j["page"]["total"] == 0
    assert j["groups"] == [{"group_label": "CamA", "interval_count": 1}, {"group_label": "CamB", "interval_count": 1}]


def test_x10_groups_filter(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800, "CamA")
    mk(client, cid, T("10:20:00"), 3600, "CamB")
    mk(client, cid, T("11:00:00"), 600, "CamC")
    assert len(C(client, cid)["windows"]) == 2
    j = C(client, cid, groups="CamA,CamB")
    assert [(w["start"], w["groups"]) for w in j["windows"]] == [(T("10:20:00"), ["CamA", "CamB"])]
    assert [g["group_label"] for g in j["groups"]] == ["CamA", "CamB"]
    j = C(client, cid, groups=" CamB , CamC ")
    assert [(w["start"], w["groups"]) for w in j["windows"]] == [(T("11:00:00"), ["CamB", "CamC"])]
    j = C(client, cid, groups="CamA")
    assert j["windows"] == [] and j["groups"] == [{"group_label": "CamA", "interval_count": 1}]
    j = C(client, cid, groups="nope")
    assert j["windows"] == [] and j["groups"] == []
    assert len(C(client, cid, groups="CamA,CamA,CamB")["windows"]) == 1
    for bad in ("CamA,", "", ",", "CamA,,CamB", "   "):
        r = corr(client, cid, groups=bad)
        assert r.status_code == 400 and r.json()["detail"] == "Invalid groups", bad
    assert C(client, cid, groups="cama")["windows"] == []


def test_x11_unplaced_and_unknown_length(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800, "CamA")
    mk(client, cid, T("10:20:00"), 1800, "CamB")
    nodur = mk(client, cid, T("09:00:00"), group="CamA")
    neg = mk(client, cid, T("09:00:00"), -5, "CamA")
    nocreate = ev(client, cid)
    meta(nocreate, cid, None, 60)
    oor = mk(client, cid, "9999-12-31T00:00:00Z", 60)
    setcal(client, oor, device_time="2026-01-01T00:00:00Z", reference_time="2026-01-02T03:46:40Z")
    j = C(client, cid)
    assert len(j["windows"]) == 1
    assert {u["evidence_id"]: u["reason"] for u in j["unknown_length"]} == {nodur: "NO_DURATION", neg: "INVALID_DURATION"}
    for u in j["unknown_length"]:
        assert set(u) == {"evidence_id", "group_label", "reason", "start"} and u["group_label"] == "CamA"
        assert u["start"] == T("09:00:00")
    assert {u["evidence_id"]: u["reason"] for u in j["unplaced"]} == {nocreate: "NO_CREATION_TIME",
                                                                       oor: "CALIBRATION_OUT_OF_RANGE"}
    for u in j["unplaced"]:
        assert set(u) == {"evidence_id", "group_label", "reason"} and u["group_label"] == "DEFAULT"
    assert j["groups"] == [{"group_label": "CamA", "interval_count": 1}, {"group_label": "CamB", "interval_count": 1}]


def test_x12_calibration_moves_overlap(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800, "CamA")
    b = mk(client, cid, T("10:20:00"), 1800, "CamB")
    setcal(client, b, reference_time="2026-01-01T10:10:00Z")
    assert C(client, cid)["windows"] == []
    setcal(client, b, reference_time="2026-01-01T09:50:00Z")
    w = C(client, cid)["windows"][0]
    assert (w["start"], w["end"], w["length_seconds"]) == (T("10:10:00"), T("10:30:00"), 1200.0)


def test_x13_uncertain_flag(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1800, "CamA")
    b = mk(client, cid, T("10:20:00"), 1800, "CamB")
    assert C(client, cid)["windows"][0]["uncertain"] is False
    setcal(client, b, uncertainty_seconds=0)
    assert C(client, cid)["windows"][0]["uncertain"] is False
    setcal(client, b, uncertainty_seconds=30)
    w = C(client, cid)["windows"][0]
    assert w["uncertain"] is True and w["start"] == T("10:20:00") and w["length_seconds"] == 600.0
    cid2 = case(client)
    mk(client, cid2, T("10:00:00"), 1800, "CamA")
    mk(client, cid2, T("10:20:00"), 1800, "CamB")
    far = mk(client, cid2, T("14:00:00"), 60, "CamA")
    setcal(client, far, uncertainty_seconds=30)
    assert C(client, cid2)["windows"][0]["uncertain"] is False


def test_x14_paging_and_summary(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 36000, "CamA")
    for h in range(11, 16):
        mk(client, cid, T(f"{h}:00:00"), 600, "CamB")
    full = C(client, cid)
    assert len(full["windows"]) == 5 and all(w["length_seconds"] == 600.0 for w in full["windows"])
    assert [w["start"] for w in full["windows"]] == [T(f"{h}:00:00") for h in range(11, 16)]
    ids = [w["window_id"] for w in full["windows"]]
    assert len(set(ids)) == 5
    got = []
    for off, n in ((0, 2), (2, 2), (4, 1)):
        j = C(client, cid, limit=2, offset=off)
        assert j["page"] == {"limit": 2, "offset": off, "total": 5} and len(j["windows"]) == n
        assert j["summary"] == {"window_count": 5, "total_overlap_seconds": 3000.0, "longest_overlap_seconds": 600.0,
                                "max_simultaneous_groups": 2, "truncated": False}
        got += [w["window_id"] for w in j["windows"]]
    assert got == ids
    assert C(client, cid, offset=100)["windows"] == []
    assert full["groups"] == [{"group_label": "CamA", "interval_count": 1}, {"group_label": "CamB", "interval_count": 5}]


def test_x15_sorted_by_start_time(client):
    cid = case(client)
    mk(client, cid, T("12:00:00"), 600, "CamA")
    mk(client, cid, T("12:00:00"), 600, "CamB")
    mk(client, cid, T("09:00:00"), 600, "CamC")
    mk(client, cid, T("09:00:00"), 600, "CamD")
    assert [(w["start"], w["groups"]) for w in C(client, cid)["windows"]] == [
        (T("09:00:00"), ["CamC", "CamD"]), (T("12:00:00"), ["CamA", "CamB"])]


def test_x16_deterministic(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 600, "CamA")
    mk(client, cid, T("10:00:00"), 600, "CamB")
    j1, j2 = C(client, cid), C(client, cid)
    assert j1 == j2
    assert j1["windows"][0]["window_id"] == wid(["CamA", "CamB"], T("10:00:00"))


def snap():
    out = {}
    with get_connection() as c:
        for t in ("cases", "evidence", "metadata_extractions", "recovered_artifacts", "calibration_references",
                  "evidence_groups", "audit_log"):
            out[t] = [tuple(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY rowid")]
        out["v"] = c.execute("PRAGMA user_version").fetchone()[0]
        out["tables"] = sorted(r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    return out


def test_x17_no_side_effects(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 600, "CamA")
    mk(client, cid, T("10:00:00"), 600, "CamB")
    before = snap()
    assert before["v"] == 9
    C(client, cid)
    C(client, cid, groups="CamA,CamB", min_groups=2, limit=1)
    corr(client, "nope")
    corr(client, cid, groups="")
    corr(client, cid, limit=0)
    assert snap() == before
    assert not any("correlation" in t for t in before["tables"])


def test_x18_no_leaks(client):
    cid = case(client)
    e = mk(client, cid, T("10:00:00"), 600, "CamA", name="SECRETNAME.mp4")
    mk(client, cid, T("10:00:00"), 600, "CamB")
    with get_connection() as c:
        c.execute("UPDATE evidence SET stored_path='C:\\SECRET_DIR\\f', sha256='abc123secrethash' WHERE evidence_id=?", (e,))
    t = corr(client, cid).text
    for bad in ("SECRETNAME", "SECRET_DIR", "abc123secrethash", "stored_path", "output_path", "original_filename"):
        assert bad not in t


def test_x19_truncation(client, monkeypatch):
    import app.services.timeline_service as ts_mod
    cid = case(client)
    for g in ("CamA", "CamB", "CamC"):
        mk(client, cid, T("10:00:00"), 600, g)
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 2)
    assert C(client, cid)["summary"]["truncated"] is True
    monkeypatch.setattr(ts_mod, "TIMELINE_MAX_ROWS", 3)
    j = C(client, cid)
    assert j["summary"]["truncated"] is False and j["summary"]["max_simultaneous_groups"] == 3


def test_x20_case_isolation(client):
    ids = []
    for _ in range(2):
        cid = case(client)
        a = mk(client, cid, T("10:00:00"), 600, "CamA")
        b = mk(client, cid, T("10:00:00"), 600, "CamB")
        ids.append((cid, a, b))
    for cid, a, b in ids:
        j = C(client, cid)
        assert len(j["windows"]) == 1
        assert j["windows"][0]["members"] == [{"group_label": "CamA", "evidence_ids": [a]},
                                              {"group_label": "CamB", "evidence_ids": [b]}]


def test_x21_fractional_seconds(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 1, "CamA")
    mk(client, cid, "2025-06-01T10:00:00.500000Z", 1, "CamB")
    w = C(client, cid)["windows"][0]
    assert w["start"] == "2025-06-01T10:00:00.500000Z" and w["end"] == T("10:00:01")
    assert w["length_seconds"] == 0.5
    assert w["window_id"] == wid(["CamA", "CamB"], "2025-06-01T10:00:00.500000Z")


def test_x22_zero_duration_has_no_overlap(client):
    cid = case(client)
    mk(client, cid, T("10:00:00"), 0, "CamA")
    mk(client, cid, T("10:00:00"), 60, "CamB")
    j = C(client, cid)
    assert j["windows"] == []
    assert j["groups"] == [{"group_label": "CamA", "interval_count": 1}, {"group_label": "CamB", "interval_count": 1}]


def test_x23_default_group_takes_part(client):
    cid = case(client)
    d = mk(client, cid, T("10:00:00"), 600)
    a = mk(client, cid, T("10:00:00"), 600, "CamA")
    w = C(client, cid)["windows"][0]
    assert w["groups"] == ["CamA", "DEFAULT"]
    assert w["members"] == [{"group_label": "CamA", "evidence_ids": [a]}, {"group_label": "DEFAULT", "evidence_ids": [d]}]


def test_x24_overflow_goes_to_unknown_length(client):
    cid = case(client)
    over = mk(client, cid, "9999-12-30T00:00:00Z", 315360000, "CamA")
    mk(client, cid, T("10:00:00"), 600, "CamB")
    j = C(client, cid)
    assert [(u["evidence_id"], u["reason"], u["start"]) for u in j["unknown_length"]] == [
        (over, "TIME_OUT_OF_RANGE", "9999-12-30T00:00:00Z")]
    assert j["windows"] == [] and j["groups"] == [{"group_label": "CamB", "interval_count": 1}]


def test_x25_registration_order_does_not_matter(client):
    cid = case(client)
    b = mk(client, cid, T("10:00:00"), 600, "CamB")
    a = mk(client, cid, T("10:00:00"), 600, "CamA")
    w = C(client, cid)["windows"][0]
    assert w["groups"] == ["CamA", "CamB"]
    assert [m["group_label"] for m in w["members"]] == ["CamA", "CamB"]
    assert w["members"][0]["evidence_ids"] == [a] and w["members"][1]["evidence_ids"] == [b]
