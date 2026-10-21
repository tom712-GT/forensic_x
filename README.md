# FORENSIC-X — Multi-Vendor DVR/NVR Forensic Analysis Tool

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB.svg)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4+-646CFF.svg)](https://vitejs.dev/)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.20-363636.svg)](https://soliditylang.org/)

**Smart India Hackathon 2026**  
**Problem Statement ID:** SIH26150  
**Title:** Development of a Multi-Vendor DVR/NVR Forensic Analysis Tool for Standardized Acquisition, Recovery, and Analysis of Surveillance Evidence  
**Theme:** Blockchain & Cybersecurity  

---

## 1. Project Objective & Core Forensic Principles

Surveillance video evidence extracted from DVRs/NVRs often comes in proprietary, corrupted, or non-standardized formats with unreliable device clocks. **FORENSIC-X** is an end-to-end digital forensic suite providing:

1. **Strict Evidence Preservation**: Original evidence files are stored in a dedicated vault with OS-level and application-level read-only locks (`S_IREAD`). The system **NEVER** modifies original evidence. All video playback, carving, and analysis occur strictly on derived working copies.
2. **Immediate Cryptographic Hashing**: Ingested evidence is fingerprinted with chunked SHA-256 baselines that are immutable and guarded against overwrite.
3. **Multi-Vendor Stream Handling**: Standardized container parsing for MP4/MOV and AVI, with extensible signature detection for Dahua, Hikvision, and CP Plus CCTV formats.
4. **Timeline & Clock Calibration**: Reconstructs unified timelines while explicitly labeling timestamp provenance (`TOOL_CLOCK`, `USER_DECLARED`, `CONTAINER_CLAIM`). Mathematical calibration applies reference clock offsets with confidence intervals without overwriting original claims.
5. **Gap & Cross-Camera Analysis**: Algorithmic gap detection classifies lost recording periods as `CERTAIN` or `UNCERTAIN`. Cross-camera correlation detects concurrent recording windows across multiple angles.
6. **Immutable Audit & Blockchain Chain-of-Custody**: In-database SQLite triggers enforce append-only audit logging cryptographically chained via SHA-256 genesis hashes, backed by an Ethereum/Solidity `EvidenceRegistry` smart contract.

---

## 2. Project Architecture

```
FORENSIC-X/
├── backend/                  # FastAPI REST API & Forensic Engine
│   ├── app/
│   │   ├── main.py           # Application entrypoint & CORS middleware
│   │   ├── config.py         # Pydantic environment configuration (Zero hardcoded secrets)
│   │   ├── database.py       # Core database connection facade
│   │   ├── api/ (routers/)   # REST API route controllers
│   │   ├── models/           # Domain data models (Case, Evidence, Recovery)
│   │   ├── schemas/          # Pydantic request/response validation schemas
│   │   ├── repositories/     # SQLite database access layer
│   │   ├── services/         # Business logic (Evidence, Timeline, Calibration, Gaps, Report)
│   │   ├── forensic/         # Forensic algorithms (Carver, MP4/AVI parsers, Audit chain, Vendor parsers)
│   │   ├── video/            # Video proxy generation & streaming helpers
│   │   ├── ai/               # Surveillance AI & event detection interface
│   │   ├── blockchain/       # Web3 / EVM smart contract client
│   │   └── utils/            # Hashing and file utilities
│   └── tests/                # 35 test suites (570 unit & acceptance tests)
├── frontend/                 # React 18 + Vite Forensic Investigation Web App
│   ├── src/
│   │   ├── pages/            # 6-tab Investigation Workspace (Evidence, Timeline, Time, Gaps, Correlation, Report) + Audit Panel
│   │   ├── components/       # Loading, ErrorBanner, Disclaimer components
│   │   ├── lib/              # API client with automatic baseUrl resolution & formatters
│   │   └── styles.css        # Dark-mode cybersecurity dashboard styling
│   └── vite.config.js        # Vite build & Vitest test runner configuration
├── blockchain/               # Hardhat EVM Blockchain Environment
│   ├── contracts/            # EvidenceRegistry.sol smart contract
│   ├── scripts/              # Contract deployment scripts
│   └── hardhat.config.cjs    # Hardhat local network configuration
├── dataset/                  # Test datasets & surveillance benchmarks
│   ├── UCF_Crimes/           # UCF-Crime real-world surveillance video benchmark
│   └── sample_videos/        # Non-sensitive benchmark video streams
├── evidence/                 # Forensic Evidence Vault
│   ├── original/             # Immutable, read-only original evidence storage
│   ├── working/              # Derived video proxies and analysis copies
│   ├── recovered/            # Carved artifacts and extracted images/documents
│   └── exports/              # Court-admissible exported evidence packages
├── reports/                  # Generated forensic reports
│   ├── generated/            # Cryptographically hashed JSON/PDF case summaries
│   └── templates/            # Forensic reporting templates
├── scripts/                  # Automation & diagnostic utility scripts
│   ├── import_ucf_crime.py   # UCF-Crime surveillance dataset batch importer
│   └── verify_environment.py # System environment diagnostics
├── docs/                     # Architectural documentation, PRD, and test plans
├── .env.example              # Central configuration template
└── README.md
```

---

## 3. Security & Integrity Guarantees

- **No Hardcoded Secrets**: All passwords, JWT keys, ports, and RPC URLs are read dynamically from environment variables.
- **Path Traversal Immunization**: Files are saved strictly using server-generated UUIDs (`RAW_STORAGE_ROOT / case_id / evidence_id`). Original filenames provided by users are never used in local filesystem paths.
- **Resource Exhaustion Defense**: File uploads are capped (default 100MB), streamed in 1MB chunks, and aborted immediately if limits are exceeded.
- **Database Append-Only Triggers**: SQLite aborts any `UPDATE` or `DELETE` executed against the `audit_log` table.
- **Fail-Closed Sandbox**: Test environments validate path boundaries to prevent test writes from ever touching production evidence vaults.

---

## 4. Setup and Installation

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** & `npm`

### Step 1: Clone and Configure Environment
```powershell
cd D:\FORENSIC-X
Copy-Item .env.example .env
```

### Step 2: Backend Setup
```powershell
# Create and activate virtual environment (if not already created)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install fastapi uvicorn pydantic python-multipart pytest httpx
```

### Step 3: Frontend Setup
```powershell
cd D:\FORENSIC-X\frontend
npm install
```

---

## 5. How to Run the Application

To run the complete platform, open **two PowerShell terminals**:

### Terminal 1: Start Backend API
```powershell
cd D:\FORENSIC-X
.\scripts\start_backend.ps1
```
*Or manually via:*
```powershell
$env:PYTHONPATH = "D:\FORENSIC-X\backend"
.\venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Endpoint: `http://127.0.0.1:8000`
- Interactive Swagger Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/api/health`

### Terminal 2: Start Frontend Web App
```powershell
cd D:\FORENSIC-X
.\scripts\start_frontend.ps1
```
*Or manually via:*
```powershell
cd D:\FORENSIC-X\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
- Open in your browser: `http://localhost:5173`

---

## 6. How to Run Automated Tests

### Backend Test Suite (570 Tests)
```powershell
cd D:\FORENSIC-X\backend
$env:PYTHONPATH = "D:\FORENSIC-X\backend"
..\venv\Scripts\pytest.exe -v
```

### Frontend Test Suite (39 Tests)
```powershell
cd D:\FORENSIC-X\frontend
npm test
```

### Run System Environment Diagnostics
```powershell
cd D:\FORENSIC-X
.\venv\Scripts\python.exe scripts\verify_environment.py
```

---

## 7. Running the Optional Local Blockchain Network

To test decentralized evidence anchoring:
```powershell
cd D:\FORENSIC-X\blockchain
npm install
npm run node              # Starts local Hardhat EVM node on http://127.0.0.1:8545
npm run deploy:local      # Compiles and deploys EvidenceRegistry.sol
```

---

## 8. UCF-Crime Surveillance Video Dataset Integration

### Overview
The **UCF-Crime** dataset is an open-access, large-scale surveillance video benchmark containing 128 hours of real-world CCTV footage across 13 anomalous activity categories (such as Abuse, Arrest, Arson, Assault, Burglary, Robbery, Shooting, Stealing) and normal surveillance controls. 

In **FORENSIC-X**, UCF-Crime is utilized exclusively for **video analysis, timeline synchronization, and surveillance anomaly-detection research**.

> [!IMPORTANT]
> **Forensic Scope Disclaimer:**
> **UCF-Crime is a surveillance video dataset used for video-analysis and anomaly-detection research. It does not represent proprietary DVR/NVR disk images, filesystem structures, deleted-file recovery, or physical-device acquisition evidence. These forensic acquisition capabilities must be evaluated separately using suitable device images or other authorized test evidence.**

### Dataset Directory Setup
The dataset root is expected at:
```
D:\FORENSIC-X\dataset\UCF_Crimes\
```
The importer also dynamically detects custom paths configured via `--dataset-dir` or the `UCF_CRIME_DATASET_DIR` environment variable, as well as root-level `UCF_Crimes/` or `UFC_Crimes/` folders.

### Storage Architecture & Zero-Byte Database Policy
- **No Video Blobs in Database**: Video files remain in their original filesystem directory. PostgreSQL stores only metadata, relative disk paths, SHA-256 hashes, ground-truth labels, and relational mappings (`Case -> Evidence -> Camera -> Video -> VideoMetadata`).
- **Read-Only Preservation**: Original dataset files are never renamed, moved, modified, re-encoded, or deleted.
- **Incremental & Chunked**: File hashing reads files in 64 KB chunks to prevent loading entire video streams into application memory.
- **Storage Constraints**: Batch ingestion respects the ~40 GB development storage limits and checks drive free space before executing.

### Category & Train/Test Split Separation
- **Dynamic Category Detection**: Surveillance categories are detected dynamically from directory structures (`Abuse`, `Arrest`, `Burglary`, etc.) and mapped to synthetic dataset camera channels (`CAM-UCF-<Category>`).
- **Official Split Integrity**: Preserves official assignments from `Anomaly_Detection_splits/Anomaly_Train.txt` (1,610 videos) and `Anomaly_Test.txt` (290 videos) with **0% cross-contamination**. Unlisted videos are marked as `UNKNOWN`.
- **Ground Truth vs. AI Predictions**: Dataset labels are explicitly stored as `GROUND_TRUTH_DATASET_LABEL` in `VideoMetadata.creation_metadata` to keep ground truth clearly distinguished from automated AI model predictions.

### Command-Line Interface (CLI) Usage

The importer script is accessible via both `scripts/import_ucf_crime.py` and `backend/scripts/import_ucf_crime.py`:

```powershell
cd D:\FORENSIC-X

# 1. Preview scanned files without modifying database (Dry Run)
.\venv\Scripts\python.exe scripts/import_ucf_crime.py --dry-run --batch-size 10

# 2. Import a small configurable batch (default: 10 videos)
.\venv\Scripts\python.exe scripts/import_ucf_crime.py --batch-size 10

# 3. Import from a custom dataset root
.\venv\Scripts\python.exe scripts/import_ucf_crime.py --dataset-dir "dataset/UCF_Crimes" --batch-size 10

# 4. Filter by category or official split
.\venv\Scripts\python.exe scripts/import_ucf_crime.py --batch-size 5 --split TRAIN --category Abuse
.\venv\Scripts\python.exe scripts/import_ucf_crime.py --batch-size 5 --split TEST --category Arrest

# 5. Display current dataset ingestion metrics
.\venv\Scripts\python.exe scripts/import_ucf_crime.py --status

# 6. Cryptographically verify database SHA-256 hashes against stored disk files
.\venv\Scripts\python.exe scripts/import_ucf_crime.py --verify
```

### Duplicate Prevention & Interrupted Import Resilience
- **Idempotent**: Every file's SHA-256 hash and relative path are checked against existing PostgreSQL `videos` records. Duplicate videos are skipped without error or duplicate insertion.
- **Transaction Safety**: Commits occur after each video record; if a batch is interrupted, already-imported videos remain committed and rerunning the script safely resumes where it left off.

### REST API Endpoints
When the backend server is running (`scripts/start_backend.ps1`):
- `POST /api/dataset/import`: Triggers batch ingestion with `{ "batch_size": 10, "split": "TRAIN" }`.
- `GET /api/dataset/status`: Retrieves real-time video counts, category distributions, and train/test splits.
- `GET /api/dataset/videos`: Lists ingested dataset videos with pagination.
- `GET /api/dataset/verify`: Performs live SHA-256 baseline verification against disk files.
#   f o r e n s i c _ x  
 