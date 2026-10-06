import pytest
from app.forensic.carver import carve_artifacts
from io import BytesIO

def test_carve_jpeg_happy_path():
    data = b"junk" * 100 + b"\xff\xd8\xff" + b"image data" + b"\xff\xd9" + b"more junk"
    stream = BytesIO(data)
    
    artifacts = list(carve_artifacts(stream, max_search_bytes=1000))
    assert len(artifacts) == 1
    a = artifacts[0]
    assert a["start_offset"] == 400
    assert a["data"] == b"\xff\xd8\xff" + b"image data" + b"\xff\xd9"
    assert a["type"] == "JPEG"
    assert a["status"] == "RECOVERED"

def test_carve_jpeg_not_found():
    data = b"junk" * 100
    stream = BytesIO(data)
    
    artifacts = list(carve_artifacts(stream, max_search_bytes=1000))
    assert len(artifacts) == 0

def test_carve_jpeg_no_end_marker():
    data = b"junk" * 100 + b"\xff\xd8\xff" + b"image data without end marker"
    stream = BytesIO(data)
    
    artifacts = list(carve_artifacts(stream, max_search_bytes=1000))
    assert len(artifacts) == 1
    a = artifacts[0]
    assert a["start_offset"] == 400
    assert a["data"] == b"\xff\xd8\xff" + b"image data without end marker"
    assert a["type"] == "JPEG"
    assert a["status"] == "PARTIAL"

def test_carve_jpeg_cross_chunk_boundary():
    data = b"a" * 4095 + b"\xff" + b"\xd8\xff" + b"img" + b"\xff\xd9"
    stream = BytesIO(data)
    
    artifacts = list(carve_artifacts(stream, max_search_bytes=8192))
    assert len(artifacts) == 1
    a = artifacts[0]
    assert a["start_offset"] == 4095
    assert a["data"] == b"\xff\xd8\xff" + b"img" + b"\xff\xd9"
    assert a["type"] == "JPEG"
    assert a["status"] == "RECOVERED"

def test_carve_multiple_signatures():
    data = b"a" * 10 + b"\xff\xd8\xff" + b"A" + b"\xff\xd9" + b"b" * 10 + b"PK\x03\x04" + b"Z" * 1024
    stream = BytesIO(data)
    
    artifacts = list(carve_artifacts(stream, max_search_bytes=8192))
    assert len(artifacts) == 2
    assert artifacts[0]["type"] == "JPEG"
    assert artifacts[0]["status"] == "RECOVERED"
    assert artifacts[1]["type"] == "ZIP"
    assert artifacts[1]["status"] == "CANDIDATE"
    assert artifacts[1]["data"].startswith(b"PK\x03\x04")
