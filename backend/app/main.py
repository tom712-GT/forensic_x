from fastapi import FastAPI
from app.api.cases import router as cases_router
from app.api.evidence import router as evidence_router

app = FastAPI(title="FORENSIC-X API")

# Register the cases router
app.include_router(cases_router)
# Register the evidence router
app.include_router(evidence_router)

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
