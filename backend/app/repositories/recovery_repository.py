from app.models.recovery import RecoveredArtifact
from app.db.database import get_connection

class RecoveryRepository:
    @staticmethod
    def insert(artifact: RecoveredArtifact) -> RecoveredArtifact:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO recovered_artifacts (
                    artifact_id, evidence_id, case_id, source_offset,
                    recovered_size, detected_type, recovery_timestamp,
                    output_path, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.evidence_id,
                    artifact.case_id,
                    artifact.source_offset,
                    artifact.recovered_size,
                    artifact.detected_type,
                    artifact.recovery_timestamp.isoformat(),
                    artifact.output_path,
                    artifact.status
                )
            )
        return artifact
