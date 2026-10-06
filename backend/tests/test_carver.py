import pytest
from app.forensic.carver import carve_jpeg
from io import BytesIO

def test_carve_jpeg_happy_path():
    data = b"junk" * 100 + b"\xff\xd8\xff" + b"image data" + b"\xff\xd9" + b"more junk"
    stream = BytesIO(data)
    
    offset, recovered = carve_jpeg(stream, max_search_bytes=1000)
    assert offset == 400
    assert recovered == b"\xff\xd8\xff" + b"image data" + b"\xff\xd9"

def test_carve_jpeg_not_found():
    data = b"junk" * 100
    stream = BytesIO(data)
    
    offset, recovered = carve_jpeg(stream, max_search_bytes=1000)
    assert offset is None
    assert recovered is None

def test_carve_jpeg_no_end_marker():
    data = b"junk" * 100 + b"\xff\xd8\xff" + b"image data without end marker"
    stream = BytesIO(data)
    
    offset, recovered = carve_jpeg(stream, max_search_bytes=1000)
    assert offset == 400
    assert recovered == b"\xff\xd8\xff" + b"image data without end marker"

def test_carve_jpeg_cross_chunk_boundary():
    data = b"a" * 4095 + b"\xff" + b"\xd8\xff" + b"img" + b"\xff\xd9"
    stream = BytesIO(data)
    
    offset, recovered = carve_jpeg(stream, max_search_bytes=8192)
    assert offset == 4095
    assert recovered == b"\xff\xd8\xff" + b"img" + b"\xff\xd9"
