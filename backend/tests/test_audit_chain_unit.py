import hashlib
import json
import inspect
from pathlib import Path

import pytest
from app.forensic.audit_chain import GENESIS_HASH, compute_row_hash, verify_chain
from app.repositories.audit_chain_repository import AuditChainRepository
from app.repositories.audit_repository import AuditRepository
from app.db.database import get_connection


def _make_valid_row(audit_id, prev_hash, action="ACT", details="{}"):
    ts = "2026-01-01T00:00:00Z"
    rh = compute_row_hash(prev_hash, ts, action, "SUCCESS", 200, None, None, "UNAUTHENTICATED", details)
    return {
        "audit_id": audit_id,
        "timestamp": ts,
        "action": action,
        "outcome": "SUCCESS",
        "http_status": 200,
        "case_id": None,
        "evidence_id": None,
        "actor": "UNAUTHENTICATED",
        "details": details,
        "prev_hash": prev_hash,
        "row_hash": rh,
    }


def test_verify_chain_genesis_mismatch():
    row = _make_valid_row(1, "1" * 64)
    res = verify_chain([row])
    assert res["first_break"] == {"audit_id": 1, "reason": "GENESIS_MISMATCH"}
    assert res["verified_count"] == 0
    assert res["chained_count"] == 1


def test_verify_chain_prev_hash_mismatch():
    r1 = _make_valid_row(1, GENESIS_HASH)
    r2 = _make_valid_row(2, "f" * 64)
    res = verify_chain([r1, r2])
    assert res["first_break"] == {"audit_id": 2, "reason": "PREV_HASH_MISMATCH"}
    assert res["verified_count"] == 1
    assert res["chained_count"] == 2


def test_verify_chain_row_hash_mismatch():
    r1 = _make_valid_row(1, GENESIS_HASH)
    r2 = _make_valid_row(2, r1["row_hash"])
    r2["row_hash"] = "e" * 64
    res = verify_chain([r1, r2])
    assert res["first_break"] == {"audit_id": 2, "reason": "ROW_HASH_MISMATCH"}
    assert res["verified_count"] == 1
    assert res["chained_count"] == 2


def test_verify_chain_missing_hash_null_row_hash():
    r1 = _make_valid_row(1, GENESIS_HASH)
    r2 = _make_valid_row(2, r1["row_hash"])
    r2["row_hash"] = None
    res = verify_chain([r1, r2])
    assert res["first_break"] == {"audit_id": 2, "reason": "MISSING_HASH"}
    assert res["verified_count"] == 1
    assert res["chained_count"] == 2


def test_verify_chain_missing_hash_null_prev_hash_only():
    r1 = _make_valid_row(1, GENESIS_HASH)
    r2 = _make_valid_row(2, r1["row_hash"])
    r2["prev_hash"] = None
    res = verify_chain([r1, r2])
    assert res["first_break"] == {"audit_id": 2, "reason": "MISSING_HASH"}
    assert res["verified_count"] == 1
    assert res["chained_count"] == 2


def test_verify_chain_missing_hash_null_row_after_chain():
    r1 = _make_valid_row(1, GENESIS_HASH)
    r2 = _make_valid_row(2, None)
    r2["prev_hash"] = None
    r2["row_hash"] = None
    res = verify_chain([r1, r2])
    assert res["first_break"] == {"audit_id": 2, "reason": "MISSING_HASH"}
    assert res["verified_count"] == 1
    assert res["chained_count"] == 1
    assert res["total_count"] == 2


def test_verify_chain_pre_chain_rows_only():
    r1 = dict(_make_valid_row(1, None), prev_hash=None, row_hash=None)
    r2 = dict(_make_valid_row(2, None), prev_hash=None, row_hash=None)
    res = verify_chain([r1, r2])
    assert res == {
        "total_count": 2,
        "pre_chain_count": 2,
        "chained_count": 0,
        "verified_count": 0,
        "first_break": None,
        "anchor": None,
    }


def test_verify_chain_pre_chain_then_chain():
    r1 = dict(_make_valid_row(1, None), prev_hash=None, row_hash=None)
    r2 = _make_valid_row(2, GENESIS_HASH)
    r3 = _make_valid_row(3, r2["row_hash"])
    res = verify_chain([r1, r2, r3])
    assert res["total_count"] == 3
    assert res["pre_chain_count"] == 1
    assert res["chained_count"] == 2
    assert res["verified_count"] == 2
    assert res["first_break"] is None
    assert res["anchor"] == {"audit_id": 3, "row_hash": r3["row_hash"]}


def test_verify_chain_break_keeps_counting_chained_and_anchor():
    r1 = _make_valid_row(1, GENESIS_HASH)
    r2 = _make_valid_row(2, "bad" + "0" * 61)
    r3 = _make_valid_row(3, "bad2" + "0" * 60)
    res = verify_chain([r1, r2, r3])
    assert res["first_break"] == {"audit_id": 2, "reason": "PREV_HASH_MISMATCH"}
    assert res["chained_count"] == 3
    assert res["verified_count"] == 1
    assert res["anchor"] == {"audit_id": 3, "row_hash": r3["row_hash"]}


def test_verify_chain_generator_consumed_once():
    r1 = _make_valid_row(1, GENESIS_HASH)
    r2 = _make_valid_row(2, r1["row_hash"])
    consumed = []

    def gen():
        for r in [r1, r2]:
            consumed.append(r["audit_id"])
            yield r

    res = verify_chain(gen())
    assert res["verified_count"] == 2
    assert consumed == [1, 2]


def test_verify_chain_rows_not_mutated():
    r1 = _make_valid_row(1, GENESIS_HASH)
    r1_orig = json.dumps(r1, sort_keys=True)
    res = verify_chain([r1])
    assert json.dumps(r1, sort_keys=True) == r1_orig


def test_compute_row_hash_none_vs_empty_case_id():
    h_none = compute_row_hash(GENESIS_HASH, "2026-01-01T00:00:00Z", "A", "SUCCESS", 200, None, None, "ACTOR", "{}")
    h_empty = compute_row_hash(GENESIS_HASH, "2026-01-01T00:00:00Z", "A", "SUCCESS", 200, "", None, "ACTOR", "{}")
    assert h_none != h_empty


def test_compute_row_hash_unicode_in_details():
    det = '{"symbol": "\u20ac"}'
    h = compute_row_hash(GENESIS_HASH, "2026-01-01T00:00:00Z", "A", "SUCCESS", 200, None, None, "ACTOR", det)
    canonical = json.dumps(
        ["FORENSIC-X-AUDIT-V1", GENESIS_HASH, "2026-01-01T00:00:00Z", "A", "SUCCESS", 200, None, None, "ACTOR", det],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    assert "\\u20ac" in canonical
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == h


def test_audit_chain_source_code_pure():
    import app.forensic.audit_chain as mod
    src = inspect.getsource(mod)
    assert "sqlite3" not in src
    assert "os." not in src and "import os" not in src
    assert "pathlib" not in src
    assert "open(" not in src


def test_audit_repository_insert_return_and_exists():
    ret = AuditRepository.insert("2026-01-01T00:00:00Z", "TEST_ACTION", "SUCCESS", 200, "ACTOR", {"foo": "bar"})
    assert ret is None
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM audit_log WHERE action = 'TEST_ACTION'").fetchone()
        assert row is not None
        assert row["prev_hash"] is not None
        assert row["row_hash"] is not None


def test_audit_chain_repository_anchor_check_rows_after():
    h1 = "1" * 64
    h2 = "2" * 64
    h3 = "3" * 64
    with get_connection() as conn:
        conn.execute("INSERT INTO audit_log (timestamp, action, outcome, http_status, actor, details, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?)",
                     ("2026-01-01T00:00:00Z", "A", "SUCCESS", 200, "U", "{}", GENESIS_HASH, h1))
        id1 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO audit_log (timestamp, action, outcome, http_status, actor, details, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?)",
                     ("2026-01-01T00:00:00Z", "B", "SUCCESS", 200, "U", "{}", h1, h2))
        conn.execute("INSERT INTO audit_log (timestamp, action, outcome, http_status, actor, details, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?)",
                     ("2026-01-01T00:00:00Z", "C", "SUCCESS", 200, "U", "{}", h2, h3))
    check = AuditChainRepository.check_anchor(h1)
    assert check == {"matched": True, "audit_id": id1, "rows_after_anchor": 2}


def test_audit_chain_repository_anchor_check_lowest_audit_id():
    same_h = "a" * 64
    with get_connection() as conn:
        conn.execute("INSERT INTO audit_log (timestamp, action, outcome, http_status, actor, details, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?)",
                     ("2026-01-01T00:00:00Z", "A", "SUCCESS", 200, "U", "{}", GENESIS_HASH, same_h))
        first_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO audit_log (timestamp, action, outcome, http_status, actor, details, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?)",
                     ("2026-01-01T00:00:00Z", "B", "SUCCESS", 200, "U", "{}", same_h, same_h))
    check = AuditChainRepository.check_anchor(same_h)
    assert check["matched"] is True
    assert check["audit_id"] == first_id


def test_api_verify_anchor_pattern_422(client):
    assert client.get("/api/audit-log/verify", params={"anchor": "invalid_anchor"}).status_code == 422
    assert client.get("/api/audit-log/verify", params={"anchor": "f" * 63}).status_code == 422
    assert client.get("/api/audit-log/verify", params={"anchor": "F" * 64}).status_code == 422


def test_rows_after_anchor_ignores_rows_without_hash(client):
    from app.services.audit_service import AuditService
    from app.db.database import get_connection
    from app.repositories.audit_chain_repository import AuditChainRepository as R
    AuditService.record(action="A", outcome="SUCCESS", http_status=200, details={})
    with get_connection() as c:
        h = c.execute("SELECT row_hash FROM audit_log ORDER BY audit_id DESC LIMIT 1").fetchone()[0]
        c.execute("INSERT INTO audit_log (timestamp, action, outcome, http_status, actor, details) VALUES ('t','FORGED','SUCCESS',200,'U','{}')")
    AuditService.record(action="B", outcome="SUCCESS", http_status=200, details={})
    res = R.check_anchor(h)
    assert res["matched"] is True and res["rows_after_anchor"] == 1

