# Security & Forensic Integrity

## Evidence Integrity
Ensuring the integrity of digital evidence is the primary security concern of FORENSIC-X. Any alteration to the evidence can render it inadmissible in court.

## Original Evidence Preservation
- Original evidence files must be stored in a dedicated vault directory.
- Once written, the original files must have read-only permissions applied at the filesystem level.
- The application will only read from these files for hashing or creating working copies.

## Hashing
- **Algorithm**: SHA-256 is the initial standard.
- **Timing**: Hashing must occur immediately upon file ingestion, before any other processing.
- **Verification**: The system must provide mechanisms to re-hash and verify evidence against the originally stored hash.

## File Upload Validation
- Validate file types based on magic numbers/headers, not just extensions.
- Enforce strict size limits and timeout configurations to prevent DoS during ingestion.

## Path Traversal Protection
- All user-supplied filenames and case names must be strictly sanitized.
- The backend must ensure that file read/write operations cannot escape the designated vault or working directories (e.g., no `../` allowed in paths).

## Secrets/Configuration
- No hardcoded secrets, database credentials, or keys in the source code.
- Configuration must be managed via environment variables (e.g., `.env` files).

## API Security
- Strict input validation for all REST endpoints using Pydantic models.
- Future implementation of JWT-based authentication and authorization.

## Audit Logging
- Implement comprehensive logging for all actions affecting evidence (upload, view, hash verification, deletion).
- Logs must include timestamps, user context (future), and the exact action performed.

## Access Control Considerations (Future)
- Role-Based Access Control (RBAC) to differentiate between administrators, analysts, and read-only viewers.

## Forensic Chain-of-Custody Considerations
- The system design must support generating a verifiable chain of custody, documenting who handled the evidence, what actions were taken, and when they occurred.
