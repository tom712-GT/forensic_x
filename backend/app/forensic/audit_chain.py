import hashlib
import json
from typing import Any, Dict, Iterable, Optional

GENESIS_HASH = "0" * 64


def compute_row_hash(
    prev_hash: Optional[str],
    timestamp: str,
    action: str,
    outcome: str,
    http_status: int,
    case_id: Optional[str],
    evidence_id: Optional[str],
    actor: str,
    details: str,
) -> str:
    canonical = json.dumps(
        [
            "FORENSIC-X-AUDIT-V1",
            prev_hash,
            timestamp,
            action,
            outcome,
            http_status,
            case_id,
            evidence_id,
            actor,
            details,
        ],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_chain(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    chain_started = False
    expected_prev = GENESIS_HASH
    first_break = None
    anchor = None
    total_count = 0
    pre_chain_count = 0
    chained_count = 0
    verified_count = 0

    for row in rows:
        total_count += 1
        audit_id = row["audit_id"]
        prev_hash = row["prev_hash"]
        row_hash = row["row_hash"]

        if prev_hash is None and row_hash is None:
            if chain_started and first_break is None:
                first_break = {"audit_id": audit_id, "reason": "MISSING_HASH"}
            elif not chain_started:
                pre_chain_count += 1
            continue

        chained_count += 1
        if row_hash is not None:
            anchor = {"audit_id": audit_id, "row_hash": row_hash}
        was_started = chain_started
        chain_started = True

        if first_break is not None:
            continue

        if prev_hash is None or row_hash is None:
            first_break = {"audit_id": audit_id, "reason": "MISSING_HASH"}
        elif prev_hash != expected_prev:
            reason = "GENESIS_MISMATCH" if not was_started else "PREV_HASH_MISMATCH"
            first_break = {"audit_id": audit_id, "reason": reason}
        elif (
            compute_row_hash(
                prev_hash,
                row["timestamp"],
                row["action"],
                row["outcome"],
                row["http_status"],
                row["case_id"],
                row["evidence_id"],
                row["actor"],
                row["details"],
            )
            != row_hash
        ):
            first_break = {"audit_id": audit_id, "reason": "ROW_HASH_MISMATCH"}
        else:
            verified_count += 1
            expected_prev = row_hash

    return {
        "total_count": total_count,
        "pre_chain_count": pre_chain_count,
        "chained_count": chained_count,
        "verified_count": verified_count,
        "first_break": first_break,
        "anchor": anchor,
    }
