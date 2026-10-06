# Test Plan

## Unit Testing
- **Backend**: Use `pytest` to test isolated Python functions, specifically hashing algorithms, metadata extraction logic, and database crud operations.
- **Frontend**: Use `Vitest` and React Testing Library to test UI components, state changes, and evidence rendering logic.

## Integration Testing
- Verify the interaction between the FastAPI backend and the SQLite database.
- Ensure that the Forensic Processing Layer correctly interacts with the filesystem and backend logic.

## API Testing
- Use `pytest` with FastAPI's `TestClient` to validate REST API contracts, status codes, and JSON responses.
- Test endpoint input validation (Pydantic models).

## Evidence Ingestion Testing
- Test uploading large video files to ensure memory limits and timeouts are handled gracefully.
- Verify that uploaded files are correctly written to the vault with the correct read-only permissions.
- Test concurrent uploads.

## Hash Verification Testing
- **Crucial**: Verify that the SHA-256 hash calculated by the system matches externally verified hashes (e.g., using OS command line tools).
- Test the system's response to tampered files (hash mismatch detection).

## Recovery Testing
- Simulate disk full errors during ingestion.
- Simulate database lock scenarios (SQLite concurrency limits) and verify graceful error handling.

## Negative/Error Testing
- Attempt path traversal attacks during file upload and download.
- Upload invalid file formats (e.g., text files renamed as `.mp4`).
- Test API endpoints with missing required fields or malformed JSON.

## Future AI/CV Testing
- Establish accuracy and performance benchmarks for future models (e.g., precision/recall for object detection).
- Test GPU memory management during heavy inference.

## Ground-Truth Testing
- Maintain a repository of known video samples with verified metadata, lengths, and hashes.
- Automatically run the ingestion pipeline against these samples and assert the output matches the ground truth exactly.
