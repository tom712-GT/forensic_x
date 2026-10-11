import hashlib
import json
import sqlite3
import threading

import pytest

from app.db.database import get_connection
from app.forensic.audit_chain import GENESIS_HASH, compute_row_hash, verify_chain

DISCLAIMER = ("A hash chain shows that audit rows from the first chained row onward were not changed, removed "
              "from the middle or reordered after they were written, unless the whole chain was rewritten. "
              "Rows written before the chain started are not verified. Deleting the newest rows is only "
              "detectable with an anchor saved outside this system.")
VERIFY_KEYS = {"disclaimer", "status", "total_count", "pre_chain_count", "chained_count", "verified_count",
               "first_break", "anchor", "anchor_check"}
COLS = "audit_id, timestamp, action, outcome, http_status, case_id, evidence_id, actor, details, prev_hash, row_hash"


def H(r):
    s = json.dumps(["FORENSIC-X-AUDIT-V1", r["prev_hash"], r["timestamp"], r["action"], r["outcome"],
                    r["http_status"], r["case_id"], r["evidence_id"], r["actor"], r["details"]],
                   separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def rows():
    with get_connection() as c:
        return [dict(x) for x in c.execute(f"SELECT {COLS} FROM audit_log ORDER BY audit_id")]


def chained():
    return [r for r in rows() if r["row_hash"] is not None]


def sql(q, args=()):
    with get_connection() as c:
        c.execute(q, args)


def untrigger():
    with get_connection() as c:
        c.execute("DROP TRIGGER IF EXISTS prevent_audit_log_update")
        c.execute("DROP TRIGGER IF EXISTS prevent_audit_log_delete")


def raw_insert(prev=None, rh=None, outcome="SUCCESS"):
    sql("INSERT INTO audit_log (timestamp, action, outcome, http_status, case_id, evidence_id, actor, details, "
        "prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("2026-01-01T00:00:00Z", "FORGED", outcome, 200, None, None, "UNAUTHENTICATED", "{}", prev, rh))


def activity(client, name="a.mp4"):
    cid = client.post("/api/cases", json={"case_name": "C"}).json()["case_id"]
    for n in (name, "b.mp4"):
        client.post(f"/api/cases/{cid}/evidence",
                    json={"original_filename": n, "evidence_type": "BIN", "file_size": 10})
    client.post("/api/evidence/nope/extract-metadata")
    assert len(chained()) >= 4
    return cid


def V(client, **p):
    r = client.get("/api/audit-log/verify", params=p)
    assert r.status_code == 200, r.text
    return r.json()


def test_h01_schema(client):
    with get_connection() as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 10
        cols = {r[1] for r in c.execute("PRAGMA table_info(audit_log)")}
        idx = {r[1] for r in c.execute("PRAGMA index_list(audit_log)")}
        trig = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='audit_log'")}
    assert {"audit_id", "timestamp", "action", "outcome", "http_status", "case_id", "evidence_id", "actor",
            "details", "prev_hash", "row_hash"} <= cols
    assert "idx_audit_prev_hash" in idx
    assert {"prevent_audit_log_update", "prevent_audit_log_delete"} <= trig


def test_h02_empty_log(client):
    assert V(client) == {"disclaimer": DISCLAIMER, "status": "OK", "total_count": 0, "pre_chain_count": 0,
                         "chained_count": 0, "verified_count": 0, "first_break": None, "anchor": None,
                         "anchor_check": None}


def test_h03_chain_is_built(client):
    activity(client)
    r = rows()
    assert len(r) >= 4
    assert r[0]["prev_hash"] == GENESIS_HASH
    for i, x in enumerate(r):
        assert len(x["row_hash"]) == 64 and all(ch in "0123456789abcdef" for ch in x["row_hash"])
        assert x["row_hash"] == H(x)
        if i > 0:
            assert x["prev_hash"] == r[i - 1]["row_hash"]
    assert len({x["row_hash"] for x in r}) == len(r)


def test_h04_verify_ok_shape(client):
    activity(client)
    r = chained()
    j = V(client)
    assert set(j) == VERIFY_KEYS
    assert j["disclaimer"] == DISCLAIMER and j["status"] == "OK"
    assert j["total_count"] == len(r) and j["chained_count"] == len(r) and j["verified_count"] == len(r)
    assert j["pre_chain_count"] == 0 and j["first_break"] is None and j["anchor_check"] is None
    assert j["anchor"] == {"audit_id": r[-1]["audit_id"], "row_hash": r[-1]["row_hash"]}


def test_h05_pre_chain_rows(client):
    for _ in range(3):
        raw_insert()
    activity(client)
    r = chained()
    j = V(client)
    assert j["status"] == "OK" and j["pre_chain_count"] == 3
    assert j["chained_count"] == len(r) and j["verified_count"] == len(r) and j["total_count"] == 3 + len(r)
    assert r[0]["prev_hash"] == GENESIS_HASH
    assert rows()[0]["row_hash"] is None


def test_h06_content_tamper(client):
    activity(client)
    untrigger()
    r = chained()
    sql("UPDATE audit_log SET outcome = 'SUCCESS_FORGED' WHERE audit_id = ?", (r[1]["audit_id"],))
    j = V(client)
    assert j["status"] == "BROKEN"
    assert j["first_break"] == {"audit_id": r[1]["audit_id"], "reason": "ROW_HASH_MISMATCH"}
    assert j["verified_count"] == 1 and j["chained_count"] == len(r)


def test_h07_single_row_recomputed(client):
    activity(client)
    untrigger()
    r = chained()
    new = dict(r[1], outcome="SUCCESS_FORGED")
    sql("UPDATE audit_log SET outcome = ?, row_hash = ? WHERE audit_id = ?",
        ("SUCCESS_FORGED", H(new), r[1]["audit_id"]))
    j = V(client)
    assert j["status"] == "BROKEN"
    assert j["first_break"] == {"audit_id": r[2]["audit_id"], "reason": "PREV_HASH_MISMATCH"}
    assert j["verified_count"] == 2


def test_h08_delete_middle_row(client):
    activity(client)
    untrigger()
    r = chained()
    sql("DELETE FROM audit_log WHERE audit_id = ?", (r[1]["audit_id"],))
    j = V(client)
    assert j["status"] == "BROKEN"
    assert j["first_break"] == {"audit_id": r[2]["audit_id"], "reason": "PREV_HASH_MISMATCH"}
    assert j["verified_count"] == 1 and j["total_count"] == len(r) - 1


def test_h09_delete_first_chained_row(client):
    activity(client)
    untrigger()
    r = chained()
    sql("DELETE FROM audit_log WHERE audit_id = ?", (r[0]["audit_id"],))
    j = V(client)
    assert j["first_break"] == {"audit_id": r[1]["audit_id"], "reason": "GENESIS_MISMATCH"}
    assert j["verified_count"] == 0


def test_h10_delete_last_row_needs_anchor(client):
    activity(client)
    r = chained()
    a = V(client)["anchor"]
    untrigger()
    sql("DELETE FROM audit_log WHERE audit_id = ?", (r[-1]["audit_id"],))
    j = V(client, anchor=a["row_hash"])
    assert j["status"] == "OK" and j["verified_count"] == len(r) - 1
    assert j["anchor_check"] == {"matched": False, "audit_id": None, "rows_after_anchor": None}
    assert j["anchor"]["row_hash"] == r[-2]["row_hash"]


def test_h11_forged_row_without_hashes(client):
    activity(client)
    r = chained()
    raw_insert()
    new_id = rows()[-1]["audit_id"]
    j = V(client)
    assert j["status"] == "BROKEN"
    assert j["first_break"] == {"audit_id": new_id, "reason": "MISSING_HASH"}
    assert j["verified_count"] == len(r) and j["pre_chain_count"] == 0
    assert j["chained_count"] == len(r) and j["total_count"] == len(r) + 1


def test_h12_forged_row_with_garbage_hashes(client):
    activity(client)
    r = chained()
    raw_insert(prev="a" * 64, rh="b" * 64)
    new_id = rows()[-1]["audit_id"]
    j = V(client)
    assert j["first_break"] == {"audit_id": new_id, "reason": "PREV_HASH_MISMATCH"}
    assert j["verified_count"] == len(r) and j["chained_count"] == len(r) + 1


def test_h13_missing_row_hash_on_chained_row(client):
    activity(client)
    untrigger()
    r = chained()
    sql("UPDATE audit_log SET row_hash = NULL WHERE audit_id = ?", (r[2]["audit_id"],))
    j = V(client)
    assert j["first_break"] == {"audit_id": r[2]["audit_id"], "reason": "MISSING_HASH"}
    assert j["verified_count"] == 2 and j["chained_count"] == len(r)


def test_h14_full_rewrite_needs_anchor(client):
    activity(client)
    a = V(client)["anchor"]
    untrigger()
    prev = GENESIS_HASH
    for i, x in enumerate(chained()):
        x = dict(x)
        if i == 0:
            x["action"] = "FORGED"
        x["prev_hash"] = prev
        x["row_hash"] = H(x)
        sql("UPDATE audit_log SET action = ?, prev_hash = ?, row_hash = ? WHERE audit_id = ?",
            (x["action"], x["prev_hash"], x["row_hash"], x["audit_id"]))
        prev = x["row_hash"]
    j = V(client, anchor=a["row_hash"])
    assert j["status"] == "OK" and j["first_break"] is None
    assert j["anchor"]["row_hash"] != a["row_hash"]
    assert j["anchor_check"] == {"matched": False, "audit_id": None, "rows_after_anchor": None}


def test_h15_anchor_match(client):
    activity(client)
    a = V(client)["anchor"]
    n1 = len(chained())
    client.post("/api/cases", json={"case_name": "D"})
    client.post("/api/evidence/nope/extract-metadata")
    n2 = len(chained())
    assert n2 - n1 == 2
    j = V(client, anchor=a["row_hash"])
    assert j["anchor_check"] == {"matched": True, "audit_id": a["audit_id"], "rows_after_anchor": 2}
    assert j["status"] == "OK"


def test_h16_anchor_validation(client):
    for bad in ("A" * 64, "a" * 63, "a" * 65, "g" * 64, ""):
        assert client.get("/api/audit-log/verify", params={"anchor": bad}).status_code == 422, bad
    j = V(client, anchor="0" * 64)
    assert j["anchor_check"] == {"matched": False, "audit_id": None, "rows_after_anchor": None}


def test_h17_only_first_break_reported(client):
    activity(client)
    untrigger()
    r = chained()
    sql("UPDATE audit_log SET outcome = 'X1' WHERE audit_id = ?", (r[1]["audit_id"],))
    sql("UPDATE audit_log SET outcome = 'X3' WHERE audit_id = ?", (r[3]["audit_id"],))
    j = V(client)
    assert j["first_break"] == {"audit_id": r[1]["audit_id"], "reason": "ROW_HASH_MISMATCH"}
    assert j["chained_count"] == len(r)


def test_h18_verify_is_read_only(client):
    activity(client)
    before = rows()
    n = len(client.get("/api/audit-log?limit=500").json())
    V(client)
    V(client, anchor="0" * 64)
    V(client, anchor=before[0]["row_hash"])
    assert rows() == before
    assert len(client.get("/api/audit-log?limit=500").json()) == n
    with get_connection() as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 10


def test_h19_no_leaks(client):
    activity(client, name="SECRETNAME.mp4")
    t = client.get("/api/audit-log/verify").text
    assert "SECRETNAME" not in t and "details" not in t
    entries = client.get("/api/audit-log?limit=500").json()
    assert entries and all("prev_hash" not in e and "row_hash" not in e for e in entries)


def test_h20_compute_row_hash_formula():
    assert GENESIS_HASH == "0" * 64
    args = dict(prev_hash=GENESIS_HASH, timestamp="2026-01-01T00:00:00Z", action="A", outcome="SUCCESS",
                http_status=200, case_id="c", evidence_id="e", actor="UNAUTHENTICATED", details='{"k":1}')
    base = compute_row_hash(**args)
    assert base == H(args) and len(base) == 64 and base == base.lower()
    changes = dict(prev_hash="1" * 64, timestamp="2026-01-01T00:00:01Z", action="B", outcome="REJECTED",
                   http_status=201, case_id="d", evidence_id="f", actor="X", details='{"k":2}')
    for k, v in changes.items():
        other = dict(args)
        other[k] = v
        assert compute_row_hash(**other) != base, k
    a_none, a_empty = dict(args, case_id=None), dict(args, case_id="")
    assert compute_row_hash(**a_none) != compute_row_hash(**a_empty)
    assert compute_row_hash(**a_none) == H(a_none)


def mkchain(n):
    out, prev = [], GENESIS_HASH
    for i in range(n):
        r = {"audit_id": i + 1, "timestamp": "2026-01-01T00:00:00Z", "action": "A", "outcome": "SUCCESS",
             "http_status": 200, "case_id": None, "evidence_id": None, "actor": "U", "details": "{}",
             "prev_hash": prev, "row_hash": None}
        r["row_hash"] = H(r)
        prev = r["row_hash"]
        out.append(r)
    return out


def test_h21_verify_chain_pure():
    assert verify_chain([]) == {"total_count": 0, "pre_chain_count": 0, "chained_count": 0, "verified_count": 0,
                                "first_break": None, "anchor": None}
    pre = [dict(mkchain(1)[0], prev_hash=None, row_hash=None), dict(mkchain(1)[0], audit_id=2, prev_hash=None, row_hash=None)]
    assert verify_chain(pre) == {"total_count": 2, "pre_chain_count": 2, "chained_count": 0, "verified_count": 0,
                                 "first_break": None, "anchor": None}
    good = mkchain(3)
    snapshot = json.dumps(good, sort_keys=True)
    res = verify_chain(iter(good))
    assert res == {"total_count": 3, "pre_chain_count": 0, "chained_count": 3, "verified_count": 3,
                   "first_break": None, "anchor": {"audit_id": 3, "row_hash": good[2]["row_hash"]}}
    assert json.dumps(good, sort_keys=True) == snapshot
    bad = mkchain(3)
    bad[1]["outcome"] = "X"
    res = verify_chain(bad)
    assert res["first_break"] == {"audit_id": 2, "reason": "ROW_HASH_MISMATCH"} and res["verified_count"] == 1
    assert res["chained_count"] == 3 and res["anchor"]["audit_id"] == 3
    mixed = pre[:1] + mkchain(2)
    mixed[1]["audit_id"], mixed[2]["audit_id"] = 2, 3
    res = verify_chain(mixed)
    assert res["pre_chain_count"] == 1 and res["verified_count"] == 2 and res["first_break"] is None


def test_h22_concurrent_writers(client):
    from app.services.audit_service import AuditService

    def work(k):
        for i in range(10):
            AuditService.record(action="T", outcome="SUCCESS", http_status=200, details={"k": k, "i": i})

    threads = [threading.Thread(target=work, args=(k,)) for k in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    r = chained()
    assert len(r) == 40
    assert len({x["prev_hash"] for x in r}) == 40
    j = V(client)
    assert j["status"] == "OK" and j["chained_count"] == 40 and j["verified_count"] == 40


def test_h23_hash_failure_leaves_no_partial_row(client, monkeypatch):
    import app.repositories.audit_repository as ar
    from app.services.audit_service import AuditService
    activity(client)
    before = rows()

    original = ar.compute_row_hash

    def boom(*a, **k):
        raise RuntimeError("secret C:\\x")

    monkeypatch.setattr(ar, "compute_row_hash", boom)
    AuditService.record(action="T", outcome="SUCCESS", http_status=200, details={})
    assert rows() == before
    monkeypatch.setattr(ar, "compute_row_hash", original)
    AuditService.record(action="T", outcome="SUCCESS", http_status=200, details={})
    j = V(client)
    assert j["status"] == "OK" and j["chained_count"] == len(before) + 1


def test_h24_migration_from_v9(client, tmp_path, monkeypatch):
    import app.db.database as database
    from app.services.audit_service import AuditService
    p = tmp_path / "v9.db"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE audit_log (audit_id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, "
                "action TEXT NOT NULL, outcome TEXT NOT NULL, http_status INTEGER NOT NULL, case_id TEXT NULL, "
                "evidence_id TEXT NULL, actor TEXT NOT NULL DEFAULT 'UNAUTHENTICATED', details TEXT NOT NULL)")
    con.execute("CREATE TRIGGER prevent_audit_log_update BEFORE UPDATE ON audit_log BEGIN "
                "SELECT RAISE(ABORT, 'audit_log is append-only'); END;")
    con.execute("CREATE TRIGGER prevent_audit_log_delete BEFORE DELETE ON audit_log BEGIN "
                "SELECT RAISE(ABORT, 'audit_log is append-only'); END;")
    for i in range(2):
        con.execute("INSERT INTO audit_log (timestamp, action, outcome, http_status, details) VALUES (?,?,?,?,?)",
                    ("2025-01-01T00:00:00Z", "OLD", "SUCCESS", 200, "{}"))
    con.execute("PRAGMA user_version = 9")
    con.commit()
    con.close()
    monkeypatch.setattr(database, "DB_PATH", p)
    database._schema_initialized = False
    j = V(client)
    assert j["total_count"] == 2 and j["pre_chain_count"] == 2 and j["chained_count"] == 0
    assert j["status"] == "OK" and j["anchor"] is None
    with get_connection() as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 10
    AuditService.record(action="NEW", outcome="SUCCESS", http_status=200, details={})
    j = V(client)
    assert j["pre_chain_count"] == 2 and j["chained_count"] == 1 and j["verified_count"] == 1 and j["status"] == "OK"
    r = rows()
    assert r[0]["row_hash"] is None and r[-1]["prev_hash"] == GENESIS_HASH


def test_h25_triggers_still_block(client):
    activity(client)
    before = rows()
    with pytest.raises(sqlite3.Error):
        sql("UPDATE audit_log SET outcome = 'X'")
    with pytest.raises(sqlite3.Error):
        sql("DELETE FROM audit_log")
    assert rows() == before


def test_h26_unique_prev_hash(client):
    activity(client)
    with pytest.raises(sqlite3.IntegrityError):
        raw_insert(prev=GENESIS_HASH, rh="c" * 64)
    raw_insert()
    raw_insert()


def test_h27_failed_requests_are_chained_too(client):
    assert client.post("/api/evidence/nope/extract-metadata").status_code == 404
    r = rows()
    assert len(r) == 1 and r[0]["outcome"] == "NOT_FOUND"
    assert r[0]["prev_hash"] == GENESIS_HASH and r[0]["row_hash"] == H(r[0])
    assert V(client)["status"] == "OK"
