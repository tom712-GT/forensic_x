import io, json, random, struct, sys, time
sys.path.insert(0, r"D:\FORENSIC-X\backend")
from app.forensic.metadata_mp4 import parse_mp4
from app.forensic.metadata_avi import parse_avi

class WriteAttempt(BaseException):
    pass

class RO(io.BytesIO):
    def __init__(self, b):
        super().__init__(b)
        self.total = 0
    def write(self, *a):
        raise WriteAttempt()
    def writelines(self, *a):
        raise WriteAttempt()
    def truncate(self, *a):
        raise WriteAttempt()
    def read(self, n=-1):
        d = super().read(n)
        self.total += len(d)
        return d

BAD = ["\\", ":/", "Traceback", "Error("]
KEYS = {"field", "raw_value", "interpreted_value", "source", "byte_offset", "note"}
NOTE = "Value stored in the container; not proof of when the recorded event happened."
TESTS = []

def test(fn):
    TESTS.append(fn)
    return fn

def strs(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, (list, tuple)):
        for i in v:
            yield from strs(i)

def common(r):
    assert isinstance(r, dict), "result is not a dict"
    assert r["status"] in ("OK", "PARTIAL", "PARSE_ERROR"), r["status"]
    json.dumps(r)
    for x in r["fields"]:
        assert set(x) == KEYS, x
        assert isinstance(x["byte_offset"], int) and x["byte_offset"] >= 0, x
        for k in ("raw_value", "interpreted_value", "note", "source"):
            for s in strs(x[k]):
                assert not any(b in s for b in BAD), (x["field"], s)
    for e in r["errors"]:
        assert isinstance(e, str) and len(e) < 60 and not any(b in e for b in BAD), e
    assert r["fields"] or r["status"] == "PARSE_ERROR", "no fields but status " + r["status"]
    if r["status"] == "OK":
        assert not r["errors"], r["errors"]

def go(fn, b):
    f = RO(bytes(b))
    r = fn(f, len(b))
    common(r)
    return r, f

def fld(r, n):
    return next((x for x in r["fields"] if x["field"] == n), None)

def suf(r, s):
    return [x for x in r["fields"] if x["field"].endswith(s)]

# ---------- MP4 builders ----------
def box(t, p):
    return struct.pack(">I4s", 8 + len(p), t) + p
def ftyp():
    return box(b"ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2")
def mvhd0(c=2082844800 + 3600, m=2082844800 + 7200, ts=1000, d=5000):
    return box(b"mvhd", struct.pack(">B3xIIII", 0, c, m, ts, d) + b"\0" * 80)
def mvhd1(c=2082844800 + 3600, m=2082844800 + 7200, ts=1000, d=5000):
    return box(b"mvhd", struct.pack(">B3xQQIQ", 1, c, m, ts, d) + b"\0" * 68)
def tkhd0(tid, w, h):
    p = bytearray(84)
    p[12:16] = struct.pack(">I", tid)
    p[76:84] = struct.pack(">II", w << 16, h << 16)
    return box(b"tkhd", bytes(p))
def tkhd1(tid, w, h):
    p = bytearray(96)
    p[0] = 1
    p[20:24] = struct.pack(">I", tid)
    p[88:96] = struct.pack(">II", w << 16, h << 16)
    return box(b"tkhd", bytes(p))
def hdlr(t=b"vide"):
    return box(b"hdlr", b"\0" * 8 + t + b"\0" * 12)
def stsd(c=b"avc1"):
    return box(b"stsd", struct.pack(">B3xI", 0, 1) + struct.pack(">I4s", 86, c) + b"\0" * 78)
def trak(tid=1, w=1920, h=1080, codec=b"avc1", ver=0, handler=b"vide"):
    tk = tkhd0(tid, w, h) if ver == 0 else tkhd1(tid, w, h)
    return box(b"trak", tk + box(b"mdia", hdlr(handler) + box(b"minf", box(b"stbl", stsd(codec)))))
def moov(*parts):
    return box(b"moov", b"".join(parts))

# ---------- MP4 tests ----------
@test
def mp4_normal_v0_two_tracks():
    d = ftyp() + moov(mvhd0(), trak(1, 1920, 1080), trak(2, 0, 0, b"mp4a", handler=b"soun"))
    r, f = go(parse_mp4, d)
    assert r["status"] == "OK", (r["status"], r["errors"])
    c = fld(r, "creation_time")
    assert c and c["interpreted_value"] == "1970-01-01T01:00:00Z" and c["note"] == NOTE, c
    assert fld(r, "duration")["interpreted_value"] == 5.0
    assert fld(r, "timescale")["raw_value"] == 1000
    assert fld(r, "major_brand")["raw_value"] == "isom"
    assert fld(r, "minor_version") and fld(r, "minor_version")["raw_value"] == 512
    assert any(x["raw_value"] == 1920 << 16 and x["interpreted_value"] == 1920.0 for x in suf(r, ".width"))
    assert any(x["raw_value"] == 1080 << 16 and x["interpreted_value"] == 1080.0 for x in suf(r, ".height"))
    assert {x["raw_value"] for x in suf(r, ".codec")} >= {"avc1", "mp4a"}
    assert {x["raw_value"] for x in suf(r, ".handler_type")} >= {"vide", "soun"}
    names = [x["field"] for x in r["fields"]]
    assert len(names) == len(set(names)), "duplicate field names"

@test
def mp4_normal_v1():
    d = ftyp() + moov(mvhd1(), trak(1, 1280, 720, ver=1))
    r, f = go(parse_mp4, d)
    assert r["status"] == "OK", (r["status"], r["errors"])
    assert fld(r, "creation_time")["interpreted_value"] == "1970-01-01T01:00:00Z"
    assert fld(r, "version")["raw_value"] == 1
    assert any(x["raw_value"] == 1280 << 16 for x in suf(r, ".width"))

@test
def mp4_timestamps():
    cases = [
        (0, None, "NOT_SET"),
        (2082844800 - 86400, "1969-12-31T00:00:00Z", NOTE),
        (1, "1904-01-01T00:00:01Z", NOTE),
        (2 ** 63, None, "OUT_OF_RANGE"),
    ]
    for raw, exp, note in cases:
        r, f = go(parse_mp4, ftyp() + moov(mvhd1(c=raw)))
        c = fld(r, "creation_time")
        assert c, raw
        assert c["interpreted_value"] == exp, (raw, c["interpreted_value"])
        assert c["note"] is not None and c["note"].startswith(note), (raw, c["note"])
        assert c["raw_value"] == raw

@test
def mp4_timescale_zero():
    for mk in (mvhd0, mvhd1):
        r, f = go(parse_mp4, ftyp() + moov(mk(ts=0)))
        d = fld(r, "duration")
        assert d and d["interpreted_value"] is None and d["note"] == "timescale is zero", d

@test
def mp4_moov_at_end_bounded_read():
    d = ftyp() + box(b"mdat", b"\0" * 20000000) + moov(mvhd0())
    r, f = go(parse_mp4, d)
    assert fld(r, "creation_time"), r["errors"]
    assert f.total < 200000, "read too much: %d" % f.total

@test
def mp4_small_boxes_do_not_read_neighbour():
    neighbour = box(b"free", struct.pack(">IIII", 5, 6, 7, 8) * 4)
    r, f = go(parse_mp4, ftyp() + moov(box(b"mvhd", b"\0" * 12), neighbour))
    assert not fld(r, "creation_time") and not fld(r, "timescale") and not fld(r, "duration")
    assert "BOX_TOO_SMALL" in r["errors"], r["errors"]
    r, f = go(parse_mp4, ftyp() + moov(box(b"trak", box(b"tkhd", b"\0" * 8) + box(b"free", b"\0" * 100))))
    assert not suf(r, ".width") and not suf(r, ".height")
    assert "BOX_TOO_SMALL" in r["errors"], r["errors"]
    r, f = go(parse_mp4, ftyp() + moov(trak(), box(b"trak", box(b"mdia", box(b"hdlr", b"\0" * 6) + box(b"free", b"\0" * 40)))))
    assert "BOX_TOO_SMALL" in r["errors"], r["errors"]

@test
def mp4_unsupported_versions():
    r, f = go(parse_mp4, ftyp() + moov(box(b"mvhd", bytes([2]) + b"\0" * 99)))
    assert "UNSUPPORTED_VERSION" in r["errors"], r["errors"]
    assert not fld(r, "creation_time")
    p = bytearray(96)
    p[0] = 2
    r, f = go(parse_mp4, ftyp() + moov(box(b"trak", box(b"tkhd", bytes(p)))))
    assert "UNSUPPORTED_VERSION" in r["errors"], r["errors"]
    assert not suf(r, ".width")

@test
def mp4_bad_sizes_and_status():
    r, f = go(parse_mp4, struct.pack(">I4s", 5000, b"moov") + b"\0" * 50)
    assert r["status"] != "OK"
    r, f = go(parse_mp4, struct.pack(">I4s", 4, b"free") + b"\0" * 50)
    assert r["status"] != "OK"
    for b in (b"", b"12345", b"\0" * 64):
        r, f = go(parse_mp4, b)
        assert r["status"] == "PARSE_ERROR", (b[:5], r["status"])
    r, f = go(parse_mp4, ftyp() + b"\0\0\0\x10moo")
    assert r["status"] == "PARTIAL" and fld(r, "major_brand"), (r["status"], r["errors"])

@test
def mp4_largesize_and_size_zero():
    inner = mvhd0()
    big = struct.pack(">I4sQ", 1, b"moov", 16 + len(inner)) + inner
    r, f = go(parse_mp4, ftyp() + big)
    assert fld(r, "creation_time"), r["errors"]
    r, f = go(parse_mp4, ftyp() + struct.pack(">I4s", 0, b"moov") + inner)
    assert fld(r, "creation_time"), r["errors"]

@test
def mp4_deep_nesting_does_not_crash():
    data = b"\0" * 8
    for _ in range(3000):
        data = box(b"trak", data)
    r, f = go(parse_mp4, ftyp() + moov(data))
    assert isinstance(r, dict)

@test
def mp4_fuzz():
    base = ftyp() + moov(mvhd0(), trak(1))
    rng = random.Random(1234)
    t0 = time.time()
    for i in range(400):
        b = bytearray(base)
        for _ in range(rng.randint(1, 6)):
            b[rng.randrange(len(b))] = rng.randrange(256)
        if rng.random() < 0.4:
            b = b[:rng.randrange(len(b))]
        go(parse_mp4, b)
    assert time.time() - t0 < 30, "too slow"

# ---------- AVI builders ----------
def chunk(i, p):
    return struct.pack("<4sI", i, len(p)) + p + (b"\0" if len(p) % 2 else b"")
def lst(t, p):
    return chunk(b"LIST", t + p)
def avih(us=40000):
    return chunk(b"avih", struct.pack("<14I", us, 0, 0, 0, 250, 0, 1, 0, 640, 480, 0, 0, 0, 0))
def strh(t=b"vids", h=b"H264"):
    return chunk(b"strh", t + h + b"\0" * 48)
def strf(w=1920, h=1080, bc=24, comp=b"H264"):
    return chunk(b"strf", struct.pack("<IiiHH4s5I", 40, w, h, 1, bc, comp, 0, 0, 0, 0, 0))
def strl(*p):
    return lst(b"strl", b"".join(p))
def avi(parts, extra=b""):
    return chunk(b"RIFF", b"AVI " + lst(b"hdrl", b"".join(parts)) + extra)

def fps(r):
    return next((x for x in r["fields"] if "frames_per_second" in x["field"] or "microsec" in x["field"]), None)

# ---------- AVI tests ----------
@test
def avi_normal_and_movi_not_read():
    d = avi([avih(), strl(strh(), strf())], lst(b"movi", b"\0" * 20000000))
    r, f = go(parse_avi, d)
    assert r["status"] == "OK", (r["status"], r["errors"])
    x = fps(r)
    assert x and x["raw_value"] == 40000 and x["interpreted_value"] == 25.0, x
    assert any(y["raw_value"] == 1920 for y in suf(r, ".width"))
    assert any(y["raw_value"] == 1080 for y in suf(r, ".height"))
    assert any(y["raw_value"] == 24 for y in suf(r, ".bit_count"))
    assert any(y["raw_value"] == "H264" for y in suf(r, ".compression"))
    assert any(y["raw_value"] == "vids" for y in suf(r, ".stream_type"))
    assert f.total < 200000, "read too much: %d" % f.total

@test
def avi_microsec_zero():
    r, f = go(parse_avi, avi([avih(0), strl(strh(), strf())]))
    x = fps(r)
    assert x and x["raw_value"] == 0 and x["interpreted_value"] is None, x

@test
def avi_audio_strf_not_parsed_as_video():
    r, f = go(parse_avi, avi([avih(), strl(strh(b"auds", b"\0\0\0\0"), strf())]))
    assert not any(y["raw_value"] == 1920 for y in suf(r, ".width"))
    assert not suf(r, ".compression")

@test
def avi_orphan_strf_inherits_nothing():
    r, f = go(parse_avi, avi([avih(), strl(strh(), strf()), strl(strf(1280, 720))]))
    assert any(y["raw_value"] == 1920 for y in suf(r, ".width"))
    assert not any(y["raw_value"] == 1280 for y in r["fields"]), "second stream inherited type"

@test
def avi_odd_chunk_padding():
    r, f = go(parse_avi, avi([chunk(b"JUNK", b"abc"), avih(), strl(strh(), strf())]))
    assert fps(r) is not None, r["errors"]

@test
def avi_bad_input_status():
    for b in (b"X" * 64, chunk(b"RIFF", b"WAVE" + b"\0" * 20), b"", b"12345"):
        r, f = go(parse_avi, b)
        assert r["status"] == "PARSE_ERROR", (b[:6], r["status"])
    d = avi([avih(), strl(strh(), strf())])
    go(parse_avi, d[: len(d) // 2])

@test
def avi_deep_nesting_hdrl():
    data = b""
    for _ in range(2000):
        data = lst(b"hdrl", data)
    r, f = go(parse_avi, chunk(b"RIFF", b"AVI " + data))
    assert "MAX_DEPTH exceeded" in r["errors"], r["errors"]

@test
def avi_deep_nesting_strl():
    data = b""
    for _ in range(2000):
        data = lst(b"strl", data)
    r, f = go(parse_avi, chunk(b"RIFF", b"AVI " + lst(b"hdrl", data)))
    assert "MAX_DEPTH exceeded" in r["errors"], r["errors"]

@test
def avi_hdrl_cap_is_1mb():
    r, f = go(parse_avi, avi([chunk(b"JUNK", b"\0" * (1024 * 1024 + 16))]))
    assert "MAX_HDRL_BYTES exceeded" in r["errors"], r["errors"]

@test
def avi_stream_limit():
    r, f = go(parse_avi, avi([avih()] + [strl(strh(), strf()) for _ in range(17)]))
    assert "MAX_STREAMS exceeded" in r["errors"], r["errors"]

@test
def avi_fuzz():
    base = avi([avih(), strl(strh(), strf())], lst(b"movi", b"\0" * 200))
    rng = random.Random(1234)
    t0 = time.time()
    for i in range(400):
        b = bytearray(base)
        for _ in range(rng.randint(1, 6)):
            b[rng.randrange(len(b))] = rng.randrange(256)
        if rng.random() < 0.4:
            b = b[:rng.randrange(len(b))]
        go(parse_avi, b)
    assert time.time() - t0 < 30, "too slow"

passed = failed = 0
for fn in TESTS:
    try:
        fn()
        passed += 1
        print("PASS", fn.__name__)
    except (Exception, WriteAttempt) as e:
        failed += 1
        print("FAIL", fn.__name__, "->", type(e).__name__, str(e)[:300])
print("ACCEPTANCE: %d passed, %d failed, %d total" % (passed, failed, len(TESTS)))
sys.exit(1 if failed else 0)
