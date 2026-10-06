# Architectural Decisions Record

## Python + FastAPI
**Decision**: Use Python with FastAPI for the backend.
**Reason**: Python is the industry standard for data processing, forensics, and AI/Computer Vision. FastAPI provides excellent performance, modern async support, and automatic OpenAPI documentation, making API development rapid and robust.

## React + Vite
**Decision**: Use React with Vite for the frontend.
**Reason**: React provides a robust component-based architecture necessary for building complex forensic analysis interfaces (e.g., timelines, multi-viewers). Vite offers a significantly faster development experience and optimized build process compared to older bundlers.

## SQLite Initially
**Decision**: Use SQLite as the initial database.
**Reason**: It requires zero configuration, stores data in a single file, and is highly portable. This is ideal for an MVP and aligns with the concept of isolated, portable case files. It can be migrated to PostgreSQL later if multi-user concurrent scale demands it.

## SHA-256 Initially
**Decision**: Use SHA-256 for cryptographic hashing of evidence.
**Reason**: SHA-256 is the current industry standard for forensic hashing, offering strong collision resistance acceptable in legal contexts, replacing older vulnerable standards like MD5 or SHA-1.

## Software-Only Architecture
**Decision**: Build the platform as a software-only solution.
**Reason**: Lowers the barrier to entry, allows for rapid deployment on standard hardware, and positions the platform for future cloud or on-premise scalable deployments, avoiding hardware lock-in.

## Modular Forensic Processing
**Decision**: Decouple forensic processing tasks from the core web API.
**Reason**: Forensic tasks (like video decoding or future AI inference) can be long-running and resource-intensive. A modular approach allows these to run asynchronously and scales independently from the web server.

## Original Evidence Preservation
**Decision**: Original evidence must never be modified; work only on copies.
**Reason**: This is a non-negotiable requirement for digital forensics to ensure the legal admissibility of the evidence. 

## Incremental Feature Development
**Decision**: Start with basic ingestion, hashing, and playback before implementing AI/CV.
**Reason**: Validates the core architecture, data flow, and integrity mechanisms before introducing complex, computationally expensive features.
