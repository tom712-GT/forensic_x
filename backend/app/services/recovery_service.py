import os
import stat
from pathlib import Path
from app.models.evidence import Evidence
from app.models.recovery import RecoveredArtifact
from app.repositories.recovery_repository import RecoveryRepository
from app.forensic.carver import carve_jpeg

RECOVERED_STORAGE_ROOT = Path(__file__).resolve().parents[3] / "data" / "recovered"

class RecoveryService:
    @staticmethod
    def recover_artifacts(evidence: Evidence) -> list[RecoveredArtifact]:
        if not evidence.stored_path or not os.path.exists(evidence.stored_path):
            raise FileNotFoundError("Stored evidence file missing")
            
        recovered_dir = RECOVERED_STORAGE_ROOT / evidence.case_id / evidence.evidence_id
        recovered_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        with open(evidence.stored_path, "rb") as f:
            start_offset, data = carve_jpeg(f)
            if data:
                artifact = RecoveredArtifact(
                    evidence_id=evidence.evidence_id,
                    case_id=evidence.case_id,
                    source_offset=start_offset,
                    recovered_size=len(data),
                    detected_type="JPEG",
                    output_path=""
                )
                output_file = recovered_dir / f"{artifact.artifact_id}.jpeg"
                artifact.output_path = str(output_file)
                
                with open(output_file, "wb") as out_f:
                    out_f.write(data)
                
                # Make the recovered artifact read-only for safety
                os.chmod(output_file, stat.S_IREAD)
                
                RecoveryRepository.insert(artifact)
                results.append(artifact)
                
        return results
