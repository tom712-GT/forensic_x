# FORENSIC-X Backend

## Purpose
This is the backend service for the FORENSIC-X platform, a digital forensics application for CCTV/DVR/NVR evidence analysis. It acts as the core REST API layer that will manage evidence ingestion, orchestrate processing tasks, and serve data to the frontend.

## FastAPI Usage
The backend is built using Python and FastAPI. FastAPI was chosen for its high performance, modern Python type hints, automatic interactive documentation (Swagger UI), and robust asynchronous support which is ideal for I/O bound forensic tasks.

## Implemented Endpoints
Currently, the minimal backend skeleton implements the following endpoints:
- `GET /` : Returns a simple JSON message confirming the API is running.
- `GET /api/health` : Returns the basic health status of the FORENSIC-X API service.

## Incremental Development
This directory currently contains a minimal skeleton. Database integration (SQLite), robust forensic modules (like file hashing and evidence parsing), and authentication mechanisms will be added incrementally as the project progresses.
