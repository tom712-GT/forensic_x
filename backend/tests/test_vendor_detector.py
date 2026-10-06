import pytest
from app.forensic.vendor_detector import detect_vendor

@pytest.mark.parametrize("header, filename", [
    (b"IMKH" + b"\x00"*10, "clip.mp4"),
    (b"DHAV" + b"\x00"*10, "clip.mp4"),
    (b"\x00"*100 + b"HIKVISION" + b"\x00"*10, "clip.mp4"),
    (b"randombytes", "x.dav"),
    (b"IMKH" + b"\x00"*96 + b"HIKVISION", "clip.mp4"),
    (b"DHAV" + b"\x00"*10, "x.dav"),
    (b"DHAV" + b"\x00"*96 + b"HIKVISION", "clip.mp4"),
    (b"IMKH" + b"\x00"*10, "x.dav"),
    (b"\x00\x00\x00\x1cftypisom", "hikvision_clip.mp4"),
    (b"\x00\x00\x00\x00IMKH", "clip.mp4"),
    (b"", "")
])
def test_every_result_has_unverified_note(header, filename):
    res = detect_vendor(header, filename)
    assert "Confidence is capped at MEDIUM because some rules are UNVERIFIED_PUBLIC_KNOWLEDGE." in res["notes"]

def test_imkh_magic():
    # b"IMKH"+padding -> HIKVISION, MEDIUM
    res = detect_vendor(b"IMKH" + b"\x00"*10, "clip.mp4")
    assert res["vendor"] == "HIKVISION"
    assert res["confidence"] == "MEDIUM"
    assert res["conflict"] is False
    assert any("unverified" in n.lower() for n in res["notes"])
    assert not any("more than one vendor" in n for n in res["notes"])

def test_dhav_magic():
    # b"DHAV"+padding -> DAHUA, MEDIUM
    res = detect_vendor(b"DHAV" + b"\x00"*10, "clip.mp4")
    assert res["vendor"] == "DAHUA"
    assert res["confidence"] == "MEDIUM"
    assert res["conflict"] is False
    assert any("unverified" in n.lower() for n in res["notes"])

def test_dahua_extension():
    # random bytes with filename "x.dav" -> DAHUA, LOW
    res = detect_vendor(b"randombytes", "x.dav")
    assert res["vendor"] == "DAHUA"
    assert res["confidence"] == "LOW"
    assert any("unverified" in n.lower() for n in res["notes"])

def test_dahua_extension_case_insensitive():
    # random bytes with filename "X.DAV" -> DAHUA, LOW (case-insensitive)
    res = detect_vendor(b"randombytes", "X.DAV")
    assert res["vendor"] == "DAHUA"
    assert res["confidence"] == "LOW"
    assert any("unverified" in n.lower() for n in res["notes"])

def test_hikvision_string():
    # b"HIKVISION" at offset 100 -> HIKVISION, LOW
    res = detect_vendor(b"\x00"*100 + b"HIKVISION" + b"\x00"*10, "clip.mp4")
    assert res["vendor"] == "HIKVISION"
    assert res["confidence"] == "LOW"

def test_hikvision_string_lowercase():
    # b"hikvision" (lowercase) at offset 100 -> UNKNOWN
    res = detect_vendor(b"\x00"*100 + b"hikvision" + b"\x00"*10, "clip.mp4")
    assert res["vendor"] == "UNKNOWN"

def test_imkh_and_string():
    # IMKH magic + HIKVISION string -> HIKVISION, still MEDIUM (cap)
    res = detect_vendor(b"IMKH" + b"\x00"*96 + b"HIKVISION", "clip.mp4")
    assert res["vendor"] == "HIKVISION"
    assert res["confidence"] == "MEDIUM"

def test_dhav_and_extension():
    # DHAV magic + filename "x.dav" -> DAHUA, MEDIUM
    res = detect_vendor(b"DHAV" + b"\x00"*10, "x.dav")
    assert res["vendor"] == "DAHUA"
    assert res["confidence"] == "MEDIUM"

def test_conflict_dhav_hikvision():
    # DHAV magic + "HIKVISION" string -> UNKNOWN, conflict true, both indicators listed
    res = detect_vendor(b"DHAV" + b"\x00"*96 + b"HIKVISION", "clip.mp4")
    assert res["vendor"] == "UNKNOWN"
    assert res["conflict"] is True
    assert len(res["indicators"]) == 2
    assert any("unverified" in n.lower() for n in res["notes"])
    assert any("Indicators point to more than one vendor. Vendor is left UNKNOWN and all indicators are listed for manual review." in n for n in res["notes"])

def test_conflict_imkh_dahua():
    # IMKH magic + filename "x.dav" -> UNKNOWN, conflict true, both indicators listed
    res = detect_vendor(b"IMKH" + b"\x00"*10, "x.dav")
    assert res["vendor"] == "UNKNOWN"
    assert res["conflict"] is True
    assert len(res["indicators"]) == 2
    assert any("Indicators point to more than one vendor. Vendor is left UNKNOWN and all indicators are listed for manual review." in n for n in res["notes"])

def test_no_indicators():
    # valid MP4 header with filename "hikvision_clip.mp4" -> UNKNOWN, no indicators
    res = detect_vendor(b"\x00\x00\x00\x1cftypisom", "hikvision_clip.mp4")
    assert res["vendor"] == "UNKNOWN"
    assert len(res["indicators"]) == 0
    assert any("No vendor indicators found" in n for n in res["notes"])

def test_imkh_wrong_offset():
    # IMKH at offset 4 (not 0) -> UNKNOWN
    res = detect_vendor(b"\x00\x00\x00\x00IMKH", "clip.mp4")
    assert res["vendor"] == "UNKNOWN"
    
@pytest.mark.parametrize("header, filename, expected_vendor, expected_confidence", [
    (b"x"*50, "../../x.dav", "DAHUA", "LOW"),
    (b"x"*50, "", "UNKNOWN", "NONE"),
    (b"x"*50, "noextension", "UNKNOWN", "NONE"),
    (b"x"*50, "a.b.c", "UNKNOWN", "NONE"),
    (b"x"*50, "dir.dav/readme", "UNKNOWN", "NONE"),
    (b"IMK", "", "UNKNOWN", "NONE"),
    (b"", "x.dav", "DAHUA", "LOW"),
    (b"", "", "UNKNOWN", "NONE")
])
def test_edge_cases(header, filename, expected_vendor, expected_confidence):
    res = detect_vendor(header, filename)
    assert res["vendor"] == expected_vendor
    assert res["confidence"] == expected_confidence

def test_raise_to_medium():
    # raise-to-MEDIUM branch: call detect_vendor with a small TEST-ONLY rules list 
    # containing two LOW rules of different types for the same vendor -> result MEDIUM; 
    # and with only one LOW rule -> stays LOW
    
    test_rules = [
        {
            "vendor": "TESTVEN",
            "type": "STRING",
            "value": b"FOO",
            "strength": "LOW",
            "description": "String",
            "rule_status": "VERIFIED"
        },
        {
            "vendor": "TESTVEN",
            "type": "EXTENSION",
            "value": ".foo",
            "strength": "LOW",
            "description": "Extension",
            "rule_status": "VERIFIED"
        }
    ]
    
    # Both matches -> MEDIUM
    res1 = detect_vendor(b"FOO", "a.foo", rules=test_rules)
    assert res1["vendor"] == "TESTVEN"
    assert res1["confidence"] == "MEDIUM"
    
    # One match -> LOW
    res2 = detect_vendor(b"FOO", "a.bar", rules=test_rules)
    assert res2["vendor"] == "TESTVEN"
    assert res2["confidence"] == "LOW"
