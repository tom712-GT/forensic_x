import io
import struct
import pytest
import os
import random
import json
import hashlib
from app.forensic.metadata_avi import parse_avi
import app.forensic.metadata_avi as avi_mod

def make_chunk(fourcc: bytes, payload: bytes):
    # chunks padded to even size
    pad = b"\x00" if len(payload) % 2 != 0 else b""
    return struct.pack("<4sI", fourcc, len(payload)) + payload + pad

def make_list(list_type: bytes, payload: bytes):
    return make_chunk(b"LIST", struct.pack("<4s", list_type) + payload)

def make_avih(microsec=33333, frames=100, streams=1, w=1920, h=1080):
    # avih is 56 bytes
    payload = struct.pack("<IIIIIIIIIIIIII",
        microsec, 0, 0, 0, frames, 0, streams, 0, w, h, 0, 0, 0, 0)
    return make_chunk(b"avih", payload)

def make_strh(fccType=b"vids", fccHandler=b"cvid"):
    # strh is 56 bytes
    payload = struct.pack("<4s4sIIIIIIIIIIII",
        fccType, fccHandler, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    return make_chunk(b"strh", payload)

def make_strf_video(w=1920, h=1080, bit_count=24, compression=b"cvid"):
    # strf for video is BITMAPINFOHEADER (40 bytes)
    payload = struct.pack("<IiiHH4sIIIIII",
        40, w, h, 1, bit_count, compression, 0, 0, 0, 0, 0, 0)
    return make_chunk(b"strf", payload)

def test_avi_normal():
    avih = make_avih()
    strh = make_strh()
    strf = make_strf_video()
    strl = make_list(b"strl", strh + strf)
    hdrl = make_list(b"hdrl", avih + strl)
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    
    res = parse_avi(io.BytesIO(riff), len(riff))
    assert res["status"] == "OK"
    assert res["container"] == "AVI"
    assert res["parser_version"] == "1"
    
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["frames_per_second"]["interpreted_value"] == 30.00030000300003
    assert fields["width"]["raw_value"] == 1920
    assert fields["stream0.stream_type"]["raw_value"] == "vids"
    assert fields["stream0.compression"]["interpreted_value"] is None

def test_avi_microsec_zero():
    avih = make_avih(microsec=0)
    hdrl = make_list(b"hdrl", avih)
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    res = parse_avi(io.BytesIO(riff), len(riff))
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["frames_per_second"]["interpreted_value"] is None

def test_avi_not_riff():
    res = parse_avi(io.BytesIO(b"NOT_RIFF12345678"), 16)
    assert res["status"] == "PARSE_ERROR"

def test_avi_not_avi():
    riff = make_chunk(b"RIFF", b"WAVE" + b"1234")
    res = parse_avi(io.BytesIO(riff), len(riff))
    assert res["status"] == "PARSE_ERROR"

def test_avi_truncated_avih():
    avih = struct.pack("<4sI", b"avih", 56) + b"123"
    hdrl = make_list(b"hdrl", avih)
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    res = parse_avi(io.BytesIO(riff), len(riff))
    assert res["status"] == "PARSE_ERROR"

def test_avi_chunk_larger_than_file():
    hdrl = struct.pack("<4sI4s", b"LIST", 1000, b"hdrl") + b"123"
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    res = parse_avi(io.BytesIO(riff), len(riff))
    assert res["status"] == "PARSE_ERROR"

def test_avi_odd_size_chunk_padding():
    strh = make_chunk(b"strh", b"123") # size 3, packed with 1 byte pad
    strl = make_list(b"strl", strh)
    hdrl = make_list(b"hdrl", make_avih() + strl)
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    assert len(riff) % 2 == 0
    res = parse_avi(io.BytesIO(riff), len(riff))
    assert res["status"] in ("OK", "PARTIAL")

def test_avi_hdrl_larger_than_cap(monkeypatch):
    monkeypatch.setattr(avi_mod, "MAX_HDRL_BYTES", 10)
    avih = make_avih()
    hdrl = make_list(b"hdrl", avih)
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    res = parse_avi(io.BytesIO(riff), len(riff))
    assert res["status"] == "PARSE_ERROR"
    assert any("MAX_HDRL_BYTES" in e for e in res["errors"])

def test_avi_two_streams():
    avih = make_avih(streams=2)
    strl1 = make_list(b"strl", make_strh(b"vids") + make_strf_video())
    strl2 = make_list(b"strl", make_strh(b"auds"))
    hdrl = make_list(b"hdrl", avih + strl1 + strl2)
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    res = parse_avi(io.BytesIO(riff), len(riff))
    assert res["status"] == "OK"
    fields = {f["field"]: f for f in res["fields"]}
    assert "stream0.stream_type" in fields
    assert "stream1.stream_type" in fields

def test_avi_stream_count_limit(monkeypatch):
    monkeypatch.setattr(avi_mod, "MAX_STREAMS", 1)
    strl1 = make_list(b"strl", make_strh(b"vids"))
    strl2 = make_list(b"strl", make_strh(b"auds"))
    hdrl = make_list(b"hdrl", make_avih() + strl1 + strl2)
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    res = parse_avi(io.BytesIO(riff), len(riff))
    assert res["status"] == "PARTIAL"



def test_avi_real_file_unchanged(tmp_path):
    fp = tmp_path / "test.avi"
    riff = make_chunk(b"RIFF", b"AVI " + make_list(b"hdrl", make_avih()))
    fp.write_bytes(riff)
    h_before = hashlib.sha256(riff).hexdigest()
    with open(fp, "rb") as f:
        parse_avi(f, len(riff))
    h_after = hashlib.sha256(fp.read_bytes()).hexdigest()
    assert h_before == h_after

def test_avi_strf_exact_values():
    avih = make_avih()
    strh = make_strh()
    strf = make_strf_video(w=1920, h=1080, bit_count=24, compression=b"cvid")
    strl = make_list(b"strl", strh + strf)
    hdrl = make_list(b"hdrl", avih + strl)
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    res = parse_avi(io.BytesIO(riff), len(riff))
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["stream0.width"]["raw_value"] == 1920
    assert fields["stream0.height"]["raw_value"] == 1080
    assert fields["stream0.bit_count"]["raw_value"] == 24
    assert fields["stream0.compression"]["raw_value"] == "cvid"

@pytest.mark.parametrize("garbage", [
    b"", b"\x00"*64, b"\xff"*64, b"ftyp", b"RIFF", b"RIFF\x00\x00\x00\x00AVI ", b"\x01\x02\x03\x04\x05\x06\x07\x08", random.Random(1234).randbytes(64)
])
def test_avi_garbage_inputs(garbage):
    res = parse_avi(io.BytesIO(garbage), len(garbage))
    assert res["status"] in ("OK", "PARTIAL", "PARSE_ERROR")
    allowed = {"read error", "file too small", "struct error", "not AVI", "MAX_CHUNKS exceeded", "invalid size bounds", "MAX_HDRL_BYTES exceeded", "MAX_STREAMS exceeded", "MAX_DEPTH exceeded", "NO_METADATA_FOUND", "internal parse error"}



    for err in res["errors"]:
        assert err in allowed
    for f in res["fields"]:
        for k, v in f.items():
            if isinstance(v, str):
                assert "\\" not in v and ":/" not in v and "Traceback" not in v and "Error(" not in v
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        assert "\\" not in item and ":/" not in item and "Traceback" not in item and "Error(" not in item
    assert isinstance(json.dumps(res), str)
    for f in res["fields"]:
        for k, v in f.items():
            if isinstance(v, str):
                assert "\\" not in v and ":/" not in v and "Traceback" not in v and "Error(" not in v
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        assert "\\" not in item and ":/" not in item and "Traceback" not in item and "Error(" not in item
    assert isinstance(json.dumps(res), str)
    for f in res["fields"]:
        for k, v in f.items():
            if isinstance(v, str):
                assert "\\" not in v and ":/" not in v and "Traceback" not in v and "Error(" not in v
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        assert "\\" not in item and ":/" not in item and "Traceback" not in item and "Error(" not in item
    assert isinstance(json.dumps(res), str)

def test_avi_f1_json():
    avih = make_avih()
    strl = make_list(b"strl", make_strh() + make_strf_video())
    riff = make_chunk(b"RIFF", b"AVI " + make_list(b"hdrl", avih + strl))
    res = parse_avi(io.BytesIO(riff), len(riff))
    json.dumps(res)
    
def test_avi_f2_recursion():
    data = b""
    for _ in range(2000):
        data = make_list(b"hdrl", data)
    riff1 = make_chunk(b"RIFF", b"AVI " + data)
    res1 = parse_avi(io.BytesIO(riff1), len(riff1))
    assert res1["status"] in ("PARTIAL", "PARSE_ERROR")
    assert "MAX_DEPTH exceeded" in res1["errors"]

    data2 = b""
    for _ in range(2000):
        data2 = make_list(b"strl", data2)
    riff2 = make_chunk(b"RIFF", b"AVI " + make_list(b"hdrl", data2))
    res2 = parse_avi(io.BytesIO(riff2), len(riff2))
    assert "MAX_DEPTH exceeded" in res2["errors"]

def test_avi_f5_audio_strf():
    strl = make_list(b"strl", make_strh(fccType=b"auds") + make_strf_video())
    riff = make_chunk(b"RIFF", b"AVI " + make_list(b"hdrl", make_avih() + strl))
    res = parse_avi(io.BytesIO(riff), len(riff))
    fields = {f["field"]: f for f in res["fields"]}
    assert "stream0.width" not in fields
    assert "stream0.compression" not in fields

def test_avi_r3_status_rules():
    res_empty = parse_avi(io.BytesIO(b""), 0)
    assert res_empty["status"] == "PARSE_ERROR"
    res_5b = parse_avi(io.BytesIO(b"12345"), 5)
    assert res_5b["status"] == "PARSE_ERROR"

def test_avi_r6_current_stype_reset():
    # video strl (strh + strf)
    strh_vids = make_chunk(b"strh", b"vids" + b"1234" + b"\x00"*48)
    strf_vids = make_chunk(b"strf", struct.pack("<IiiHH4s", 40, 1920, 1080, 1, 24, b"H264") + b"\x00"*20)
    strl1 = make_list(b"strl", strh_vids + strf_vids)
    
    # second strl (only strf)
    strf_orphan = make_chunk(b"strf", struct.pack("<IiiHH4s", 40, 1280, 720, 1, 24, b"H264") + b"\x00"*20)
    strl2 = make_list(b"strl", strf_orphan)
    
    hdrl = make_list(b"hdrl", make_chunk(b"avih", b"\x00"*56) + strl1 + strl2)
    riff = make_chunk(b"RIFF", b"AVI " + hdrl)
    
    res = parse_avi(io.BytesIO(riff), len(riff))
    fields = [f["field"] for f in res["fields"]]
    assert "stream0.width" in fields
    assert "stream1.width" not in fields
