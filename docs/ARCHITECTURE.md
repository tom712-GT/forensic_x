# Architecture Overview

## System Overview
FORENSIC-X uses a 3-tier software architecture focusing on separation of concerns, scalability, and strict evidence preservation.
- **Frontend**: React + Vite
- **Backend**: Python + FastAPI
- **Database**: SQLite (Initial)

## Frontend/Backend/Database Responsibilities
- **Frontend (React + Vite)**: Provides the user interface for case management, video playback, and forensic analysis. Responsible for state management and presenting data fetched from the API.
- **Backend (FastAPI)**: Serves as the core REST API. Orchestrates evidence ingestion, initiates forensic processing, interacts with the database, and serves working copies to the frontend.
- **Database (SQLite)**: Relational storage for case details, evidence metadata, hashes, and audit logs.

## Forensic Processing Layer
A modular Python-based layer invoked by the backend. It handles:
- Cryptographic hashing.
- Video metadata extraction (e.g., via FFmpeg bindings).
- Future AI/CV inference pipelines.

## Evidence Flow
1. User uploads evidence via the Frontend.
2. Backend receives the file and immediately saves it to a designated read-only vault.
3. Backend triggers the Forensic Processing Layer to compute the SHA-256 hash.
4. Hash and metadata are stored in the database.
5. A forensic working copy (or proxy format for web playback) is generated if needed.
6. Frontend serves playback and analysis from the working copy, never the original.

## Data Flow
Client (Browser) <-> REST API (FastAPI) <-> SQLite Database & File System Vault.

## Initial Directory Structure
```
FORENSIC-X/
├── backend/       # FastAPI application and Python modules
├── frontend/      # React/Vite application
├── docs/          # Project documentation
└── vault/         # Secure, read-only storage for original evidence (To be configured)
```

## Major Future Modules
- **AI/Computer Vision Pipeline**: Asynchronous workers for heavy CV tasks (object detection, enhancement).
- **Proprietary Filesystem Parser**: Modules for decoding raw DVR disk images.
- **Reporting Engine**: Module for generating PDF/HTML forensic reports.

## Important Architectural Rules
- **The original evidence must NEVER be modified.** All processing, playback, and analysis must happen on a forensic working copy or via a read-only representation.
