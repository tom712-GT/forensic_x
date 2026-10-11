import uuid
import datetime
import json
import sqlite3
from typing import Optional
from fastapi import HTTPException
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.calibration_repository import CalibrationRepository
from app.services.timeline_service import TimelineService
from app.forensic.timeline_builder import parse_to_datetime, format_timestamp
from app.forensic.clock_calibration import (
    compute_offset, apply_offset, within_plausible_years,
    MAX_OFFSET_SECONDS, MAX_UNCERTAINTY_SECONDS
)
from app.schemas.calibration import CalibrationCreate

DISCLAIMER = ("Calibration is a user-supplied estimate. Corrected times are ranges derived from one reference "
              "and assume a constant clock offset. They are not proof of when the real event happened.")

import logging

logger = logging.getLogger(__name__)

class CalibrationService:
    @staticmethod
    def set_calibration(evidence_id: str, data: CalibrationCreate):
        from app.api.evidence import _raise_audit
        
        ev = EvidenceRepository.get_by_id(evidence_id)
        if not ev:
            _raise_audit("CALIBRATION_SET", "NOT_FOUND", 404, "UNKNOWN_EVIDENCE", evidence_id=evidence_id, detail_msg="Evidence not found")
        case_id = ev.case_id

        device_dt, d_flag = parse_to_datetime(data.device_time)
        if not device_dt:
            _raise_audit("CALIBRATION_SET", "REJECTED", 400, "INVALID_DEVICE_TIME", evidence_id=evidence_id, case_id=case_id, detail_msg="Invalid device_time")
        reference_dt, r_flag = parse_to_datetime(data.reference_time)
        if not reference_dt:
            _raise_audit("CALIBRATION_SET", "REJECTED", 400, "INVALID_REFERENCE_TIME", evidence_id=evidence_id, case_id=case_id, detail_msg="Invalid reference_time")

        if not within_plausible_years(device_dt, 1990, 2100) or not within_plausible_years(reference_dt, 1990, 2100):
            _raise_audit("CALIBRATION_SET", "REJECTED", 400, "TIME_OUT_OF_RANGE", evidence_id=evidence_id, case_id=case_id, detail_msg="Time out of plausible range")

        offset_seconds = compute_offset(device_dt, reference_dt)
        if abs(offset_seconds) > MAX_OFFSET_SECONDS:
            _raise_audit("CALIBRATION_SET", "REJECTED", 400, "OFFSET_TOO_LARGE", evidence_id=evidence_id, case_id=case_id, detail_msg="Offset too large")

        flags = []
        if d_flag == "TIMEZONE_ASSUMED_UTC" or r_flag == "TIMEZONE_ASSUMED_UTC":
            flags.append("TIMEZONE_ASSUMED_UTC")

        note = data.note.strip() if data.note else None
        if note == "":
            note = None

        entered_at = format_timestamp(datetime.datetime.now(datetime.timezone.utc))
        entered_by = "UNAUTHENTICATED"
        reference_id = str(uuid.uuid4())

        try:
            CalibrationRepository.insert_and_supersede(
                reference_id=reference_id,
                evidence_id=evidence_id,
                case_id=case_id,
                device_time=format_timestamp(device_dt),
                reference_time=format_timestamp(reference_dt),
                offset_seconds=offset_seconds,
                uncertainty_seconds=data.uncertainty_seconds,
                note=note,
                flags=flags,
                entered_at=entered_at,
                entered_by=entered_by
            )
        except sqlite3.IntegrityError:
            _raise_audit("CALIBRATION_SET", "REJECTED", 409, "CONFLICT", evidence_id=evidence_id, case_id=case_id, detail_msg="Calibration conflict, retry")
        except Exception as e:
            logger.exception("Error saving calibration")
            _raise_audit("CALIBRATION_SET", "ERROR", 500, "INTERNAL_ERROR", evidence_id=evidence_id, case_id=case_id, detail_msg="Internal error while saving calibration")

        record = {
            "reference_id": reference_id,
            "evidence_id": evidence_id,
            "case_id": case_id,
            "device_time": format_timestamp(device_dt),
            "reference_time": format_timestamp(reference_dt),
            "offset_seconds": offset_seconds,
            "uncertainty_seconds": data.uncertainty_seconds,
            "note": note,
            "flags": flags,
            "entered_at": entered_at,
            "entered_by": entered_by,
            "superseded_at": None,
            "status": "ACTIVE"
        }
        
        from app.api.evidence import _audit
        _audit("CALIBRATION_SET", "SUCCESS", 201, case_id=case_id, evidence_id=evidence_id, details={
            "reference_id": reference_id,
            "offset_seconds": offset_seconds,
            "uncertainty_seconds": data.uncertainty_seconds
        })

        return record

    @staticmethod
    def get_calibration(evidence_id: str):
        ev = EvidenceRepository.get_by_id(evidence_id)
        if not ev:
            raise HTTPException(status_code=404, detail="Evidence not found")

        rows = CalibrationRepository.get_history(evidence_id)
        
        history = []
        active = None
        for r in rows:
            r["flags"] = json.loads(r["flags"])
            r["status"] = "ACTIVE" if r["superseded_at"] is None else "SUPERSEDED"
            history.append(r)
            if r["status"] == "ACTIVE":
                active = r

        return {
            "evidence_id": evidence_id,
            "disclaimer": DISCLAIMER,
            "active": active,
            "history": history
        }

    @staticmethod
    def get_calibrated_times(case_id: str, evidence_id: Optional[str] = None):
        from app.repositories.case_repository import CaseRepository
        if not CaseRepository.get_by_id(case_id):
            raise HTTPException(status_code=404, detail="Case not found")

        tl = TimelineService.get_timeline(
            case_id,
            kinds=["CONTAINER_CREATION_TIME", "CONTAINER_MODIFICATION_TIME"],
            time_source="CONTAINER_CLAIM",
            evidence_id=evidence_id,
            start=None,
            end=None,
            limit=1000000,
            offset=0
        )
        
        active_refs = CalibrationRepository.get_active_for_case(case_id)
        calibrations_by_evidence = {r["evidence_id"]: r for r in active_refs}

        items = []
        by_status = {}
        
        for e in tl["events"]:
            eid = e["evidence_id"]
            ref = calibrations_by_evidence.get(eid)
            orig_ts = e["timestamp"]
            
            orig_dt, _ = parse_to_datetime(orig_ts)
            if orig_dt is None:
                continue
            
            calibration = None
            corrected = None
            
            if not ref:
                status = "NOT_CALIBRATED"
                eff_dt = orig_dt
            else:
                calibration = {
                    "reference_id": ref["reference_id"],
                    "offset_seconds": ref["offset_seconds"],
                    "uncertainty_seconds": ref["uncertainty_seconds"]
                }
                try:
                    nominal_dt, earliest_dt, latest_dt = apply_offset(
                        orig_dt,
                        ref["offset_seconds"],
                        ref["uncertainty_seconds"]
                    )
                    
                    if (within_plausible_years(nominal_dt, 1000, 9999) and 
                        within_plausible_years(earliest_dt, 1000, 9999) and 
                        within_plausible_years(latest_dt, 1000, 9999)):
                        
                        corrected = {
                            "nominal": format_timestamp(nominal_dt),
                            "earliest": format_timestamp(earliest_dt),
                            "latest": format_timestamp(latest_dt)
                        }
                        status = "CALIBRATED"
                        eff_dt = nominal_dt
                    else:
                        status = "OUT_OF_RANGE"
                        eff_dt = orig_dt
                        
                except OverflowError:
                    status = "OUT_OF_RANGE"
                    eff_dt = orig_dt
            
            by_status[status] = by_status.get(status, 0) + 1
            
            items.append({
                "event_id": e["event_id"],
                "evidence_id": eid,
                "kind": e["kind"],
                "original_timestamp": orig_ts,
                "flags": e["flags"],
                "correction_status": status,
                "calibration": calibration,
                "corrected": corrected,
                "effective_timestamp": format_timestamp(eff_dt),
                "eff_dt": eff_dt
            })

        items.sort(key=lambda x: (x["eff_dt"], x["kind"], x["event_id"]))
        
        for i in items:
            del i["eff_dt"]

        return {
            "case_id": case_id,
            "disclaimer": DISCLAIMER,
            "items": items,
            "summary": {
                "item_count": len(items),
                "by_status": by_status,
                "truncated": tl["summary"]["truncated"]
            }
        }
