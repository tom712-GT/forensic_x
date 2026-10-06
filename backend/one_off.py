import sys
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run():
    # Create case
    case_id = client.post("/api/cases", json={"case_name": "Test"}).json()["case_id"]
    
    print("--- 1. MP4-header file ---")
    ev1 = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "video.mp4", "evidence_type": "BIN", "file_size": 1024}).json()["evidence_id"]
    client.post(f"/api/evidence/{ev1}/file", files={"file": ("video.mp4", b"\x00\x00\x00\x1cftypisom" + b"\x00"*1012)})
    print(json.dumps(client.post(f"/api/evidence/{ev1}/detect-format").json(), indent=2))
    
    print("\n--- 2. AVI bytes as 'clip.mp4' ---")
    ev2 = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "clip.mp4", "evidence_type": "BIN", "file_size": 1024}).json()["evidence_id"]
    client.post(f"/api/evidence/{ev2}/file", files={"file": ("clip.mp4", b"RIFF\x00\x00\x00\x00AVI " + b"\x00"*1012)})
    print(json.dumps(client.post(f"/api/evidence/{ev2}/detect-format").json(), indent=2))
    
    print("\n--- 3. b'abc' ---")
    ev3 = client.post(f"/api/cases/{case_id}/evidence", json={"original_filename": "clip.mp4", "evidence_type": "BIN", "file_size": 3}).json()["evidence_id"]
    client.post(f"/api/evidence/{ev3}/file", files={"file": ("clip.mp4", b"abc")})
    print(json.dumps(client.post(f"/api/evidence/{ev3}/detect-format").json(), indent=2))

if __name__ == "__main__":
    run()
