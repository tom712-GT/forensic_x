import json
import datetime
from typing import List, Dict, Any, Optional, Tuple
from app.repositories.timeline_repository import TimelineRepository
from app.forensic.timeline_builder import parse_timestamp, parse_to_datetime, format_timestamp, build_event_id, sort_key

TIMELINE_MAX_ROWS = 10000

DISCLAIMER = (
    "Timestamps are not corrected. TOOL_CLOCK = this tool's clock; USER_DECLARED = typed by a person; "
    "CONTAINER_CLAIM = value stored inside the file. None is proof of when the real event happened."
)

class TimelineService:
    @staticmethod
    def get_timeline(
        case_id: str,
        kinds: Optional[List[str]],
        time_source: Optional[str],
        evidence_id: Optional[str],
        start: Optional[str],
        end: Optional[str],
        limit: int,
        offset: int
    ) -> dict:
        
        # 1. Fetch data
        evidence_rows = TimelineRepository.get_evidence(case_id, TIMELINE_MAX_ROWS)
        metadata_rows = TimelineRepository.get_metadata(case_id, TIMELINE_MAX_ROWS)
        artifact_rows = TimelineRepository.get_artifacts(case_id, TIMELINE_MAX_ROWS)
        
        truncated = (
            len(evidence_rows) > TIMELINE_MAX_ROWS or
            len(metadata_rows) > TIMELINE_MAX_ROWS or
            len(artifact_rows) > TIMELINE_MAX_ROWS
        )
        
        if len(evidence_rows) > TIMELINE_MAX_ROWS: evidence_rows = evidence_rows[:TIMELINE_MAX_ROWS]
        if len(metadata_rows) > TIMELINE_MAX_ROWS: metadata_rows = metadata_rows[:TIMELINE_MAX_ROWS]
        if len(artifact_rows) > TIMELINE_MAX_ROWS: artifact_rows = artifact_rows[:TIMELINE_MAX_ROWS]

        events = []
        undated = []

        def add_event(
            kind: str,
            ts_source: str,
            ev_id: str,
            raw_val: Any,
            source_def: dict,
            detail: dict,
            source_key: str,
            ingested_at: Optional[str] = None
        ):
            if ts_source != "CONTAINER_CLAIM":
                if raw_val is None or (isinstance(raw_val, str) and not raw_val.strip()):
                    return
            
            ts_parsed_dt, result_flag_or_reason = parse_to_datetime(raw_val) if isinstance(raw_val, str) else (None, "UNPARSEABLE_TIMESTAMP")
            
            # Container claims have special rules:
            if ts_source == "CONTAINER_CLAIM":
                interp = detail.get("interpreted_value") # We pass this in somehow
                note = detail.get("note")
                
                # We need to parse interp
                if isinstance(interp, str):
                    ts_parsed_dt, result_flag_or_reason = parse_to_datetime(interp)
                elif interp is None:
                    ts_parsed_dt = None
                    note_str = str(note) if note is not None else ""
                    if note_str.startswith("NOT_SET"):
                        result_flag_or_reason = "NOT_SET"
                    elif note_str.startswith("OUT_OF_RANGE"):
                        result_flag_or_reason = "OUT_OF_RANGE"
                    else:
                        result_flag_or_reason = "UNPARSEABLE_TIMESTAMP"
                else:
                    ts_parsed_dt = None
                    result_flag_or_reason = "UNPARSEABLE_TIMESTAMP"

            if ts_parsed_dt is None:
                # Add to undated
                u_id = build_event_id(kind, ev_id, source_key)
                
                rv_trunc = raw_val
                if isinstance(raw_val, str) and len(raw_val) > 200:
                    rv_trunc = raw_val[:200]
                    
                undated.append({
                    "event_id": u_id,
                    "kind": kind,
                    "time_source": ts_source,
                    "evidence_id": ev_id,
                    "source": source_def,
                    "raw_value": rv_trunc,
                    "reason": result_flag_or_reason,
                    "detail": {"note": detail.get("note")} if ts_source == "CONTAINER_CLAIM" else (
                        detail if ts_source == "TOOL_CLOCK" and kind == "ARTIFACT_RECOVERED" else {}
                    )
                })
                return
                
            # It's dated
            flags = []
            if result_flag_or_reason:  # TIMEZONE_ASSUMED_UTC
                flags.append(result_flag_or_reason)
                
            # OUT_OF_PLAUSIBLE_RANGE
            if ts_parsed_dt.year < 1990 or ts_parsed_dt.year > 2100:
                flags.append("OUT_OF_PLAUSIBLE_RANGE")
                
            # AFTER_INGEST
            if ts_source in ("USER_DECLARED", "CONTAINER_CLAIM") and ingested_at:
                ing_parsed_dt, _ = parse_to_datetime(ingested_at)
                if ing_parsed_dt and ts_parsed_dt > ing_parsed_dt:
                    flags.append("AFTER_INGEST")
                    
            flags.sort()
            
            e_id = build_event_id(kind, ev_id, source_key)
            
            rv_trunc = raw_val
            if isinstance(raw_val, str) and len(raw_val) > 200:
                rv_trunc = raw_val[:200]
                
            events.append({
                "event_id": e_id,
                "timestamp": format_timestamp(ts_parsed_dt),
                "dt": ts_parsed_dt,
                "kind": kind,
                "time_source": ts_source,
                "evidence_id": ev_id,
                "source": source_def,
                "raw_value": rv_trunc,
                "flags": flags,
                "detail": {"note": detail.get("note")} if ts_source == "CONTAINER_CLAIM" else (
                    detail if ts_source == "TOOL_CLOCK" and kind == "ARTIFACT_RECOVERED" else {}
                )
            })

        for row in evidence_rows:
            ev_id = row["evidence_id"]
            ing = row["ingested_at"]
            
            def add_evidence_event(kind, time_source, raw, field_name, source_key=None):
                if not isinstance(raw, str): return
                add_event(kind, time_source, ev_id, raw, 
                         {"table": "evidence", "field": field_name, "origin": None, "byte_offset": None}, 
                         {}, source_key or field_name, ing)
                         
            add_evidence_event("EVIDENCE_REGISTERED", "TOOL_CLOCK", row["registered_at"], "registered_at")
            add_evidence_event("EVIDENCE_INGESTED", "TOOL_CLOCK", row["ingested_at"], "ingested_at")
            add_evidence_event("EVIDENCE_HASHED", "TOOL_CLOCK", row["hashed_at"], "hashed_at")
            add_evidence_event("ACQUISITION_DECLARED", "USER_DECLARED", row["acquisition_time"], "acquisition_time")
            
            try:
                if isinstance(row["format_detection"], str) and row["format_detection"].strip():
                    fd = json.loads(row["format_detection"])
                    if isinstance(fd, dict) and "detected_at" in fd and isinstance(fd["detected_at"], str):
                        add_evidence_event("FORMAT_DETECTED", "TOOL_CLOCK", fd["detected_at"], "format_detection.detected_at")
            except Exception:
                pass
                
            try:
                if isinstance(row["vendor_detection"], str) and row["vendor_detection"].strip():
                    vd = json.loads(row["vendor_detection"])
                    if isinstance(vd, dict) and "detected_at" in vd and isinstance(vd["detected_at"], str):
                        add_evidence_event("VENDOR_DETECTED", "TOOL_CLOCK", vd["detected_at"], "vendor_detection.detected_at")
            except Exception:
                pass

        # Meta
        # metadata_extractions table has subject_id as evidence_id, result_dict, extracted_at
        ingest_map = {r["evidence_id"]: r["ingested_at"] for r in evidence_rows}
        
        for row in metadata_rows:
            ev_id = row["evidence_id"]
            ing = ingest_map.get(ev_id)
            
            if isinstance(row["extracted_at"], str) and row["extracted_at"].strip():
                add_event("METADATA_EXTRACTED", "TOOL_CLOCK", ev_id, row["extracted_at"],
                         {"table": "metadata_extractions", "field": "extracted_at", "origin": None, "byte_offset": None},
                         {}, "extracted_at", ing)
                         
            try:
                res_str = row["result_dict"]
                if isinstance(res_str, str) and res_str.strip():
                    res = json.loads(res_str)
                    if isinstance(res, dict) and "fields" in res and isinstance(res["fields"], list):
                        for idx, field in enumerate(res["fields"]):
                            if isinstance(field, dict) and field.get("field") in ("creation_time", "modification_time"):
                                fname = field["field"]
                                kind = "CONTAINER_CREATION_TIME" if fname == "creation_time" else "CONTAINER_MODIFICATION_TIME"
                                add_event(kind, "CONTAINER_CLAIM", ev_id, field.get("raw_value"),
                                         {"table": "metadata_extractions", "field": fname, 
                                          "origin": field.get("source"), "byte_offset": field.get("byte_offset")},
                                         {"note": field.get("note"), "interpreted_value": field.get("interpreted_value")},
                                         f"{fname}#{idx}", ing)
            except Exception:
                pass

        # Artifacts
        for row in artifact_rows:
            ev_id = row["evidence_id"]
            if isinstance(row["recovery_timestamp"], str) and row["recovery_timestamp"].strip():
                add_event("ARTIFACT_RECOVERED", "TOOL_CLOCK", ev_id, row["recovery_timestamp"],
                         {"table": "recovered_artifacts", "field": "recovery_timestamp", "origin": None, "byte_offset": None},
                         {"artifact_id": row["artifact_id"], "detected_type": row["detected_type"],
                          "status": row["status"], "source_offset": row["source_offset"]},
                         row["artifact_id"], None)

        # Filters
        if kinds is not None:
            events = [e for e in events if e["kind"] in kinds]
            undated = [u for u in undated if u["kind"] in kinds]
            
        if time_source is not None:
            events = [e for e in events if e["time_source"] == time_source]
            undated = [u for u in undated if u["time_source"] == time_source]
            
        if evidence_id is not None:
            events = [e for e in events if e["evidence_id"] == evidence_id]
            undated = [u for u in undated if u["evidence_id"] == evidence_id]
            
        if start is not None:
            events = [e for e in events if e["dt"] >= start]
            
        if end is not None:
            events = [e for e in events if e["dt"] <= end]

        # Sorting
        events.sort(key=sort_key)
        undated.sort(key=lambda x: (x["kind"], x["evidence_id"], x["event_id"]))  # deterministic sort for undated just in case

        # Summary
        by_kind = {}
        for e in events: by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
        by_source = {}
        for e in events: by_source[e["time_source"]] = by_source.get(e["time_source"], 0) + 1
        
        earliest = events[0]["timestamp"] if events else None
        latest = max(events, key=lambda e: e["dt"])["timestamp"] if events else None

        summary = {
            "event_count": len(events),
            "undated_count": len(undated),
            "earliest": earliest,
            "latest": latest,
            "by_kind": by_kind,
            "by_source": by_source,
            "truncated": truncated
        }

        # Page
        total = len(events)
        events_page = [{k: v for k, v in e.items() if k != "dt"} for e in events[offset:offset+limit]]

        return {
            "case_id": case_id,
            "disclaimer": DISCLAIMER,
            "events": events_page,
            "undated": undated,
            "summary": summary,
            "page": {
                "limit": limit,
                "offset": offset,
                "total": total
            }
        }
