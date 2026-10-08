import io
import struct
import pytest
import os
import random
import json
import hashlib
from app.forensic.metadata_mp4 import parse_mp4
import app.forensic.metadata_mp4 as mp4_mod

def make_box(box_type: bytes, payload: bytes, size_override=None, largesize=False):
    if size_override is not None:
        return struct.pack(">I4s", size_override, box_type) + payload
    if largesize:
        return struct.pack(">I4sQ", 1, box_type, len(payload) + 16) + payload
    return struct.pack(">I4s", len(payload) + 8, box_type) + payload

def make_ftyp(major_brand=b"mp42", minor_version=0, compatible_brands=[b"isom", b"mp42"]):
    payload = struct.pack(">4sI", major_brand, minor_version)
    for b in compatible_brands:
        payload += struct.pack(">4s", b)
    return make_box(b"ftyp", payload)

def make_mvhd_v0(ctime=0, mtime=0, timescale=1000, duration=5000):
    payload = struct.pack(">BBH IIII", 0, 0, 0, ctime, mtime, timescale, duration)
    # 96 bytes total payload standard, but 16 bytes for v0 data is enough
    payload += b"\x00" * 80 
    return make_box(b"mvhd", payload)

def make_mvhd_v1(ctime=0, mtime=0, timescale=1000, duration=5000):
    payload = struct.pack(">BBH QQIQ", 1, 0, 0, ctime, mtime, timescale, duration)
    payload += b"\x00" * 80
    return make_box(b"mvhd", payload)

def make_tkhd_v0(track_id=1, width=1920, height=1080):
    # struct tkhd v0: version(1), flags(3), ctime(4), mtime(4), track_id(4), reserved(4), duration(4), res(8), layer(2), alt(2), vol(2), res(2), matrix(36), w(4), h(4) = 84 bytes
    payload = struct.pack(">BBH IIII I HHHH", 0, 0, 0, 0, 0, track_id, 0, 0, 0, 0, 0, 0)
    payload += b"\x00" * 36
    payload += b"\x00" * 8
    payload += struct.pack(">II", width * 65536, height * 65536)
    return make_box(b"tkhd", payload)

def make_hdlr(handler_type=b"vide"):
    payload = struct.pack(">BBH I 4s", 0, 0, 0, 0, handler_type) + b"\x00" * 12 + b"Name\x00"
    return make_box(b"hdlr", payload)

def make_stsd(codec=b"avc1"):
    entry = struct.pack(">I4s", 86, codec) + b"\x00" * 78 # Dummy entry
    payload = struct.pack(">BBH I", 0, 0, 0, 1) + entry
    return make_box(b"stsd", payload)

def build_track(track_id, handler, codec, w, h):
    tkhd = make_tkhd_v0(track_id, w, h)
    hdlr = make_hdlr(handler)
    stsd = make_stsd(codec)
    stbl = make_box(b"stbl", stsd)
    minf = make_box(b"minf", stbl)
    mdia = make_box(b"mdia", hdlr + minf)
    trak = make_box(b"trak", tkhd + mdia)
    return trak

def test_mp4_normal():
    trak1 = build_track(1, b"vide", b"avc1", 1920, 1080)
    trak2 = build_track(2, b"soun", b"mp4a", 0, 0)
    mvhd = make_mvhd_v0(ctime=2082844800, timescale=1000, duration=5000) # 1970-01-01 in MP4 is 2082844800
    moov = make_box(b"moov", mvhd + trak1 + trak2)
    ftyp = make_ftyp()
    
    data = ftyp + moov
    res = parse_mp4(io.BytesIO(data), len(data))
    assert res["status"] == "OK"
    assert res["container"] == "MP4"
    assert res["parser_version"] == "1"
    
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["creation_time"]["interpreted_value"] == "1970-01-01T00:00:00Z"
    assert fields["duration"]["interpreted_value"] == 5.0
    assert fields["track1.width"]["interpreted_value"] == 1920.0
    assert fields["track2.codec"]["raw_value"] == "mp4a"

def test_mp4_moov_after_mdat():
    ftyp = make_ftyp()
    mdat = make_box(b"mdat", b"garbage123456789")
    mvhd = make_mvhd_v1(ctime=0)
    moov = make_box(b"moov", mvhd)
    data = ftyp + mdat + moov
    res = parse_mp4(io.BytesIO(data), len(data))
    assert res["status"] == "OK"
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["creation_time"]["interpreted_value"] is None
    assert "NOT_SET" in fields["creation_time"]["note"]

def test_mp4_timestamp_out_of_range():
    mvhd = make_mvhd_v1(ctime=10000000000)
    moov = make_box(b"moov", mvhd)
    data = moov
    res = parse_mp4(io.BytesIO(data), len(data))
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["creation_time"]["interpreted_value"] is None
    assert "OUT_OF_RANGE" in fields["creation_time"]["note"]


def test_mp4_size_zero_last_box():
    ftyp = make_ftyp()
    # size=0 means extends to end of file
    moov_payload = make_mvhd_v0()
    moov = struct.pack(">I4s", 0, b"moov") + moov_payload
    data = ftyp + moov
    res = parse_mp4(io.BytesIO(data), len(data))
    assert res["status"] == "OK"

def test_mp4_largesize():
    moov = make_box(b"moov", make_mvhd_v0(), largesize=True)
    res = parse_mp4(io.BytesIO(moov), len(moov))
    assert res["status"] == "OK"

def test_mp4_box_larger_than_file():
    data = struct.pack(">I4s", 1000, b"moov") + make_mvhd_v0()
    res = parse_mp4(io.BytesIO(data), len(data))
    assert res["status"] == "PARSE_ERROR"

def test_mp4_box_size_lt_8():
    data = struct.pack(">I4s", 4, b"moov") + b"1234"
    res = parse_mp4(io.BytesIO(data), len(data))
    assert res["status"] == "PARSE_ERROR"

def test_mp4_truncated_mvhd():
    moov = struct.pack(">I4s", 12, b"moov") + struct.pack(">I4s", 16, b"mvhd") + b"123"
    res = parse_mp4(io.BytesIO(moov), len(moov))
    assert res["status"] in ("PARTIAL", "PARSE_ERROR")

def test_mp4_moov_too_large(monkeypatch):
    monkeypatch.setattr(mp4_mod, "MAX_MOOV_BYTES", 10)
    moov = make_box(b"moov", make_mvhd_v0())
    res = parse_mp4(io.BytesIO(moov), len(moov))
    assert res["status"] == "PARSE_ERROR"
    assert "MOOV_TOO_LARGE" in res["errors"][0]

def test_mp4_depth_limit(monkeypatch):
    monkeypatch.setattr(mp4_mod, "MAX_DEPTH", 2)
    trak = make_box(b"trak", make_box(b"mdia", make_box(b"minf", b"12345678")))
    moov = make_box(b"moov", trak)
    res = parse_mp4(io.BytesIO(moov), len(moov))
    assert "MAX_DEPTH exceeded" in res["errors"]
    assert res["status"] == "PARSE_ERROR"

def test_mp4_box_count_limit(monkeypatch):
    monkeypatch.setattr(mp4_mod, "MAX_BOXES", 2)
    data = make_ftyp() + make_box(b"free", b"1") + make_box(b"moov", make_mvhd_v0())
    res = parse_mp4(io.BytesIO(data), len(data))
    assert res["status"] == "PARTIAL"



def test_mp4_real_file_unchanged(tmp_path):
    fp = tmp_path / "test.mp4"
    data = make_ftyp() + make_box(b"moov", make_mvhd_v0())
    fp.write_bytes(data)
    h_before = hashlib.sha256(data).hexdigest()
    with open(fp, "rb") as f:
        parse_mp4(f, len(data))
    h_after = hashlib.sha256(fp.read_bytes()).hexdigest()
    assert h_before == h_after
    
def test_mp4_all_field_keys():
    data = make_ftyp()
    res = parse_mp4(io.BytesIO(data), len(data))
    if res["fields"]:
        f = res["fields"][0]
        assert set(f.keys()) == {"field", "raw_value", "interpreted_value", "source", "byte_offset", "note"}


def test_mp4_mvhd_v0():
    moov = make_box(b"moov", make_mvhd_v0(ctime=2082844800))
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["version"]["raw_value"] == 0

def test_mp4_mvhd_v1():
    moov = make_box(b"moov", make_mvhd_v1(ctime=2082844800))
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["version"]["raw_value"] == 1

def test_mp4_tkhd_width_height():
    trak = build_track(1, b"vide", b"avc1", 1920, 1080)
    moov = make_box(b"moov", trak)
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["track1.width"]["raw_value"] == 1920 * 65536
    assert fields["track1.width"]["interpreted_value"] == 1920.0
    assert fields["track1.height"]["raw_value"] == 1080 * 65536
    assert fields["track1.height"]["interpreted_value"] == 1080.0

def test_mp4_two_tracks_names():
    trak1 = build_track(0, b"vide", b"avc1", 1920, 1080)
    trak2 = build_track(1, b"soun", b"mp4a", 0, 0)
    moov = make_box(b"moov", trak1 + trak2)
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    assert "track0.track_id" in fields
    assert "track1.track_id" in fields

def test_mp4_stsd_codec_avc1():
    trak = build_track(1, b"vide", b"avc1", 1920, 1080)
    moov = make_box(b"moov", trak)
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["track1.codec"]["raw_value"] == "avc1"

@pytest.mark.parametrize("garbage", [
    b"", b"\x00"*64, b"\xff"*64, b"ftyp", b"RIFF", b"moov\x00\x00\x00\x00", b"\x01\x02\x03\x04\x05\x06\x07\x08", random.Random(1234).randbytes(64)
])
def test_mp4_garbage_inputs(garbage):
    res = parse_mp4(io.BytesIO(garbage), len(garbage))
    assert res["status"] in ("OK", "PARTIAL", "PARSE_ERROR")
    allowed = {"MAX_DEPTH exceeded", "MAX_BOXES exceeded", "read error", "struct error", "struct error ext", "size 0 not at top level", "invalid size bounds", "MOOV_TOO_LARGE", "UNSUPPORTED_VERSION", "BOX_TOO_SMALL", "NO_METADATA_FOUND", "internal parse error", "file too small"}



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

def test_mp4_f1_json():
    trak1 = build_track(1, b"vide", b"avc1", 1920, 1080)
    moov = make_box(b"moov", make_mvhd_v0() + trak1)
    res = parse_mp4(io.BytesIO(make_ftyp() + moov), len(make_ftyp() + moov))
    assert res["status"] == "OK"
    json.dumps(res)
    assert parse_mp4(io.BytesIO(make_ftyp(major_brand=b"\x00\x01\x02\x03")), len(make_ftyp(major_brand=b"\x00\x01\x02\x03")))["fields"][0]["raw_value"] == "hex:00010203"

def test_mp4_f3_bounds_mvhd():
    moov = make_box(b"moov", struct.pack(">I4s", 16, b"mvhd") + b"12345678")
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    assert "creation_time" not in fields
    assert "BOX_TOO_SMALL" in res["errors"]
    

def test_mp4_f3_bounds_tkhd():
    fake_tkhd = struct.pack(">I4s", 16, b"tkhd") + b"12345678"
    fake_width_height = struct.pack(">I4s", 16, b"fake") + struct.pack(">II", 1920*65536, 1080*65536)
    moov = make_box(b"moov", make_box(b"trak", fake_tkhd + fake_width_height))
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    for k in fields:
        assert not k.endswith(".width") and not k.endswith(".height")
    assert "BOX_TOO_SMALL" in res["errors"]

def test_mp4_hdlr_too_small():
    moov = make_box(b"moov", make_box(b"trak", make_box(b"mdia", 
        struct.pack(">I4s", 10, b"hdlr") + b"12"
    )))
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    for k in fields:
        assert not k.endswith("handler_type")
    assert "BOX_TOO_SMALL" in res["errors"]

def test_mp4_stsd_too_small():
    moov = make_box(b"moov", make_box(b"trak", make_box(b"mdia", 
        make_box(b"minf", make_box(b"stbl", struct.pack(">I4s", 12, b"stsd") + b"1234")))
    ))
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    for k in fields:
        assert not k.endswith("codec") and not k.endswith("entry_count")
    assert "BOX_TOO_SMALL" in res["errors"]

def test_mp4_mvhd_too_small_does_not_read_neighbour():
    fake_mvhd = struct.pack(">I4s", 12, b"mvhd") + struct.pack(">BBH", 0, 0, 0)
    fake_neighbour = struct.pack(">I4s", 24, b"fake") + struct.pack(">IIII", 12345, 12345, 1000, 5000)
    moov = make_box(b"moov", fake_mvhd + fake_neighbour)
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    assert "creation_time" not in fields
    assert "timescale" not in fields
    assert "duration" not in fields

def test_mp4_tkhd_version_2():
    moov = make_box(b"moov", make_box(b"trak", struct.pack(">I4s", 96, b"tkhd") + struct.pack(">BBH", 2, 0, 0) + b"\x00"*84))
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    for k in fields:
        assert not k.endswith(".width") and not k.endswith(".height")
    assert "UNSUPPORTED_VERSION" in res["errors"]

def test_mp4_mvhd_version_2():
    moov = make_box(b"moov", struct.pack(">I4s", 32, b"mvhd") + struct.pack(">BBH", 2, 0, 0) + b"\x00"*20)
    res = parse_mp4(io.BytesIO(moov), len(moov))
    fields = {f["field"]: f for f in res["fields"]}
    assert "creation_time" not in fields
    assert "UNSUPPORTED_VERSION" in res["errors"]















def test_mp4_f4_timestamp():
    res1 = parse_mp4(io.BytesIO(make_box(b"moov", make_mvhd_v1(ctime=2082844800 - 86400))), len(make_box(b"moov", make_mvhd_v1(ctime=2082844800 - 86400))))
    assert res1["fields"][1]["interpreted_value"] == "1969-12-31T00:00:00Z"
    res2 = parse_mp4(io.BytesIO(make_box(b"moov", make_mvhd_v0(ctime=1))), len(make_box(b"moov", make_mvhd_v0(ctime=1))))
    assert res2["fields"][1]["interpreted_value"] == "1904-01-01T00:00:01Z"
    res3 = parse_mp4(io.BytesIO(make_box(b"moov", make_mvhd_v1(ctime=2**63))), len(make_box(b"moov", make_mvhd_v1(ctime=2**63))))
    assert res3["fields"][1]["interpreted_value"] is None
    assert "OUT_OF_RANGE" in res3["fields"][1]["note"]

def test_mp4_f6_status():
    res1 = parse_mp4(io.BytesIO(b"\x00"*64), 64)
    assert res1["status"] == "PARSE_ERROR"
    res2 = parse_mp4(io.BytesIO(make_ftyp() + struct.pack(">I4s", 0xFFFFFFFF, b"moov")), 100)
    assert res2["status"] == "PARTIAL"

def test_mp4_r1_minor_version():
    moov = make_box(b"moov", make_mvhd_v0())
    res = parse_mp4(io.BytesIO(make_ftyp(minor_version=123) + moov), len(make_ftyp(minor_version=123) + moov))
    fields = {f["field"]: f for f in res["fields"]}
    assert fields["minor_version"]["raw_value"] == 123

def test_mp4_r2_timescale_zero():
    moov_v0 = make_box(b"moov", make_mvhd_v0(timescale=0, duration=5000))
    res0 = parse_mp4(io.BytesIO(make_ftyp() + moov_v0), len(make_ftyp() + moov_v0))
    moov_v1 = make_box(b"moov", make_mvhd_v1(timescale=0, duration=5000))
    res1 = parse_mp4(io.BytesIO(make_ftyp() + moov_v1), len(make_ftyp() + moov_v1))
    
    fields0 = {f["field"]: f for f in res0["fields"]}
    assert fields0["duration"]["interpreted_value"] is None
    assert fields0["duration"]["note"] == "timescale is zero"
    
    fields1 = {f["field"]: f for f in res1["fields"]}
    assert fields1["duration"]["interpreted_value"] is None
    assert fields1["duration"]["note"] == "timescale is zero"

def test_mp4_r3_status_rules():
    res_empty = parse_mp4(io.BytesIO(b""), 0)
    assert res_empty["status"] == "PARSE_ERROR"
    res_5b = parse_mp4(io.BytesIO(b"12345"), 5)
    assert res_5b["status"] == "PARSE_ERROR"
    # valid ftyp, truncated moov
    res_trunc = parse_mp4(io.BytesIO(make_ftyp() + b"\x00\x00\x00\x10moo"), 32)
    assert res_trunc["status"] == "PARTIAL"
    assert len(res_trunc["fields"]) > 0


def test_mp4_r4_catch_all_2(monkeypatch):
    import struct
    def mock_unpack(fmt, data):
        if b"mvhd" in data:
            raise RuntimeError("simulated crash")
        return struct._original_unpack(fmt, data)
    struct._original_unpack = struct.unpack
    monkeypatch.setattr(struct, "unpack", mock_unpack)
    
    res = parse_mp4(io.BytesIO(make_ftyp() + make_box(b"moov", struct.pack(">I4s", 20, b"mvhd") + b"123456789012")), len(make_ftyp() + make_box(b"moov", struct.pack(">I4s", 20, b"mvhd") + b"123456789012")))
    assert isinstance(res, dict)
    assert "internal parse error" in res["errors"]
    assert res["status"] == "PARTIAL"
    fields = [f["field"] for f in res["fields"]]
    assert "major_brand" in fields
