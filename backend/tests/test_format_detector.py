from app.forensic.format_detector import detect_format

def test_empty():
    res = detect_format(b"", "clip.mp4")
    assert res["detected_format"] == "UNKNOWN"

def test_trunc_ftyp():
    res = detect_format(b"\x00\x00\x00\x1cftyp", "clip.mp4")
    assert res["detected_format"] == "UNKNOWN"

def test_ewf_e01():
    res = detect_format(b"EVF\x09\x0d\x0a\xff\x00" + b"\x00"*10, "image.e01")
    assert res["detected_format"] == "EWF_E01"
    assert res["confidence"] == "HIGH"
    assert res["extension_consistent"] is True

def test_ewf_ex01():
    res = detect_format(b"EVF2\x0d\x0a\x81\x00" + b"\x00"*10, "image.ex01")
    assert res["detected_format"] == "EWF_EX01"
    assert res["confidence"] == "HIGH"
    assert res["extension_consistent"] is True

def test_mov():
    res = detect_format(b"\x00\x00\x00\x1cftypqt  " + b"\x00"*10, "video.mov")
    assert res["detected_format"] == "MOV_QUICKTIME"
    assert res["confidence"] == "HIGH"
    assert res["extension_consistent"] is True

def test_mp4():
    res = detect_format(b"\x00\x00\x00\x1cftypisom" + b"\x00"*10, "video.MP4")
    assert res["detected_format"] == "MP4_ISO_BMFF"
    assert res["confidence"] == "HIGH"
    assert res["extension_consistent"] is True

def test_avi():
    res = detect_format(b"RIFF\x00\x00\x00\x00AVI " + b"\x00"*10, "video.avi")
    assert res["detected_format"] == "AVI"
    assert res["confidence"] == "HIGH"
    assert res["extension_consistent"] is True

def test_mkv():
    res = detect_format(b"\x1a\x45\xdf\xa3" + b"\x00"*10, "video.mkv")
    assert res["detected_format"] == "MATROSKA_WEBM"
    assert res["confidence"] == "HIGH"
    assert res["extension_consistent"] is True

def test_flv():
    res = detect_format(b"FLV\x01" + b"\x00"*10, "video.flv")
    assert res["detected_format"] == "FLV"
    assert res["confidence"] == "HIGH"

def test_asf():
    sig = bytes.fromhex("3026B2758E66CF11A6D900AA0062CE6C")
    res = detect_format(sig + b"\x00"*10, "video.wmv")
    assert res["detected_format"] == "ASF_WMV"
    assert res["confidence"] == "HIGH"

def test_mpeg_ps():
    res = detect_format(bytes.fromhex("000001BA") + b"\x00"*10, "video.mpg")
    assert res["detected_format"] == "MPEG_PS"
    assert res["confidence"] == "HIGH"

def test_mpeg_ts():
    packet = b"\x47" + b"\x00"*187
    res = detect_format(packet * 3, "video.ts")
    assert res["detected_format"] == "MPEG_TS"
    assert res["confidence"] == "HIGH"

def test_zip():
    res = detect_format(b"PK\x03\x04" + b"\x00"*10, "archive.zip")
    assert res["detected_format"] == "ZIP"
    assert res["confidence"] == "HIGH"

def test_ntfs():
    sig = b"\x00"*3 + b"NTFS    " + b"\x00"*10
    res = detect_format(sig, "disk.img")
    assert res["detected_format"] == "NTFS_VOLUME"
    assert res["confidence"] == "HIGH"

def test_exfat():
    sig = b"\x00"*3 + b"EXFAT   " + b"\x00"*10
    res = detect_format(sig, "disk.img")
    assert res["detected_format"] == "EXFAT_VOLUME"
    assert res["confidence"] == "HIGH"

def test_fat32():
    sig = b"\x00"*82 + b"FAT32   " + b"\x00"*10
    res = detect_format(sig, "disk.img")
    assert res["detected_format"] == "FAT32_VOLUME"
    assert res["confidence"] == "HIGH"

def test_fat16():
    sig = b"\x00"*54 + b"FAT16   " + b"\x00"*10
    res = detect_format(sig, "disk.img")
    assert res["detected_format"] == "FAT12_16_VOLUME"
    assert res["confidence"] == "HIGH"

def test_gpt():
    sig = b"\x00"*512 + b"EFI PART" + b"\x00"*10
    res = detect_format(sig, "disk.img")
    assert res["detected_format"] == "GPT_DISK_IMAGE"
    assert res["confidence"] == "HIGH"

def test_mbr():
    sig = b"\x00"*510 + b"\x55\xaa"
    res = detect_format(sig, "disk.img")
    assert res["detected_format"] == "MBR_DISK_IMAGE"
    assert res["confidence"] == "LOW"

def test_h264():
    res = detect_format(bytes.fromhex("0000000109"), "stream.264")
    assert res["detected_format"] == "H264_ANNEXB_STREAM"
    assert res["confidence"] == "LOW"

def test_h265():
    res = detect_format(bytes.fromhex("00000140"), "stream.hevc")
    assert res["detected_format"] == "H265_ANNEXB_STREAM"
    assert res["confidence"] == "LOW"

def test_ntfs_over_mbr():
    # Both NTFS and MBR signatures
    sig = b"\x00"*3 + b"NTFS    " + b"\x00"*499 + b"\x55\xaa"
    res = detect_format(sig, "disk.img")
    assert res["detected_format"] == "NTFS_VOLUME"

def test_avi_extension_mismatch():
    res = detect_format(b"RIFF\x00\x00\x00\x00AVI " + b"\x00"*10, "clip.mp4")
    assert res["detected_format"] == "AVI"
    assert res["extension_consistent"] is False

def test_bad_names():
    sig = b"\x00\x00\x00\x1cftypisom" + b"\x00"*10
    for name in ["../../evil.mp4", "noextension", "", "a.b.c"]:
        res = detect_format(sig, name)
        assert res["detected_format"] == "MP4_ISO_BMFF"

def test_extension_check_is_case_insensitive():
    res1 = detect_format(b"\x00\x00\x00\x1cftypisom" + b"\x00"*10, "clip.MP4")
    assert res1["detected_format"] == "MP4_ISO_BMFF"
    assert res1["extension_consistent"] is True

    res2 = detect_format(b"RIFF\x00\x00\x00\x00AVI " + b"\x00"*10, "clip.MP4")
    assert res2["detected_format"] == "AVI"
    assert res2["extension_consistent"] is False
