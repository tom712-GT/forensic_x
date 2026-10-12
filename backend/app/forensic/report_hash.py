import hashlib
import json
from typing import Any, Dict


def canonical_json(report: Dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_report_hash(report: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(report).encode("utf-8")).hexdigest()
