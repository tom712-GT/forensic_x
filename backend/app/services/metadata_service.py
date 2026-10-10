import os
import builtins
from datetime import datetime, timezone
from app.repositories.metadata_repository import MetadataRepository
from app.forensic.metadata_mp4 import parse_mp4
from app.forensic.metadata_avi import parse_avi

class MetadataService:
    @staticmethod
    def extract(evidence) -> dict:
        if not evidence.stored_path or not os.path.exists(evidence.stored_path):
            raise FileNotFoundError("Stored evidence file missing")
            
        fmt = (evidence.format_detection or {}).get("detected_format")
        if not fmt:
            return {"applicable": False, "reason": "FORMAT_NOT_DETECTED"}
            
        parser = None
        if fmt in ("MP4_ISO_BMFF", "MOV_QUICKTIME"):
            parser = parse_mp4
        elif fmt == "AVI":
            parser = parse_avi
        else:
            return {"applicable": False, "reason": "FORMAT_NOT_SUPPORTED"}
            
        file_size = os.path.getsize(evidence.stored_path)
        with builtins.open(evidence.stored_path, "rb") as f:
            result = parser(f, file_size)
            
        extracted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        stored_row = MetadataRepository.upsert(
            subject_type="EVIDENCE",
            subject_id=evidence.evidence_id,
            case_id=evidence.case_id,
            container=result["container"],
            parser_version=result["parser_version"],
            status=result["status"],
            result_dict=result,
            extracted_at=extracted_at
        )
        return stored_row
