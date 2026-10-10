from fastapi import FastAPI
from app.api.cases import router as cases_router
from app.api.evidence import router as evidence_router
from app.api.audit import router as audit_router

app = FastAPI(title="FORENSIC-X API")

# Register the cases router
from app.api.timeline import router as timeline_router

app.include_router(cases_router)
# Register the evidence router
app.include_router(evidence_router)
# Register the audit router
app.include_router(audit_router)
# Register timeline
app.include_router(timeline_router)

@app.get("/")
def read_root():
    """
    Root endpoint to confirm the API is running.
    """
    return {"message": "FORENSIC-X API is running"}

@app.get("/api/health")
def health_check():
    """
    Health check endpoint for monitoring service status.
    """
    return {
        "status": "ok",
        "service": "FORENSIC-X API"
    }
