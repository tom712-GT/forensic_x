import os
import stat
import hashlib
import sqlite3
from pathlib import Path
from app.models.evidence import Evidence
from app.models.recovery import RecoveredArtifact
from app.repositories.recovery_repository import RecoveryRepository
from app.forensic.carver import carve_artifacts

RECOVERED_STORAGE_ROOT = Path(__file__).resolve().parents[3] / "data" / "recovered"

class RecoveryService:
    @staticmethod
    def recover_artifacts(evidence: Evidence) -> list[RecoveredArtifact]:
        if not evidence.stored_path or not os.path.exists(evidence.stored_path):
            raise FileNotFoundError("Stored evidence file missing")
            
        recovered_dir = RECOVERED_STORAGE_ROOT / evidence.case_id / evidence.evidence_id
        recovered_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        # Basic deterministic deduplication using offset and type during this scan.
        seen_artifacts = set()
        
        with open(evidence.stored_path, "rb") as f:
            for art_dict in carve_artifacts(f):
                offset = art_dict["start_offset"]
                art_type = art_dict["type"]
                data = art_dict["data"]
                status = art_dict["status"]
                
                dedup_key = f"{offset}:{art_type}"
                if dedup_key in seen_artifacts:
                    continue
                seen_artifacts.add(dedup_key)
                
                artifact_hash = hashlib.sha256(data).hexdigest()
                
                artifact = RecoveredArtifact(
                    evidence_id=evidence.evidence_id,
                    case_id=evidence.case_id,
                    source_offset=offset,
                    recovered_size=len(data),
                    detected_type=art_type,
                    output_path="",
                    artifact_hash=artifact_hash,
                    status=status
                )
                
                if status == "CANDIDATE":
                    extension = "bin"
                else:
                    extension = art_type.lower()
                    
                output_file = recovered_dir / f"{artifact.artifact_id}.{extension}"
                artifact.output_path = str(output_file)
                
                with open(output_file, "wb") as out_f:
                    out_f.write(data)
                
                # Make the recovered artifact read-only for safety
                os.chmod(output_file, stat.S_IREAD)
                
                try:
                    RecoveryRepository.insert(artifact)
                    results.append(artifact)
                except sqlite3.IntegrityError:
                    # Duplicate artifact. Clean up physical file and ignore.
                    if output_file.exists():
                        os.chmod(output_file, stat.S_IWRITE)
                        output_file.unlink()
                except Exception as e:
                    # Other DB error. Clean up and raise.
                    if output_file.exists():
                        os.chmod(output_file, stat.S_IWRITE)
                        output_file.unlink()
                    raise e
                
        return results
