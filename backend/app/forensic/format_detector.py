import os

def is_ewf_ext(ext):
    if not ext:
        return False
    if ext == ".e01":
        return True
    if len(ext) == 4 and ext.startswith(".e") and ext[2:].isdigit():
        return True
    return False

def detect_format(header: bytes, filename: str) -> dict:
    """
    A signature match means "looks like this format", not "valid or complete".
    Vendor detection is a later step; synthetic tests do not prove real-world files.
    """
    ext = None
    if filename:
        try:
            _, e = os.path.splitext(filename)
            if e:
                ext = e.lower()
        except:
            pass

    def make_result(fmt: str, cat: str, conf: str, expected_exts: set, sig: str, check_ewf=False):
        ext_consistent = None
        if ext is not None:
            ext_consistent = (ext in expected_exts) or (check_ewf and is_ewf_ext(ext))
        return {
            "detected_format": fmt,
            "category": cat,
            "confidence": conf,
            "matched_signature": sig,
            "extension_hint": ext,
            "extension_consistent": ext_consistent
        }

    hl = len(header)

    # 1. EWF_E01
    if hl >= 8 and header[:8] == b"EVF\x09\x0d\x0a\xff\x00":
        return make_result("EWF_E01", "FORENSIC_IMAGE", "HIGH", {".e01"}, 'b"EVF\\x09\\x0d\\x0a\\xff\\x00" at offset 0', check_ewf=True)

    # 2. EWF_EX01
    if hl >= 8 and header[:8] == b"EVF2\x0d\x0a\x81\x00":
        return make_result("EWF_EX01", "FORENSIC_IMAGE", "HIGH", {".ex01"}, 'b"EVF2\\x0d\\x0a\\x81\\x00" at offset 0')

    # 3. MOV_QUICKTIME & 4. MP4_ISO_BMFF
    if hl >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand == b"qt  ":
            return make_result("MOV_QUICKTIME", "VIDEO_CONTAINER", "HIGH", {".mov"}, "'ftyp' at offset 4, brand 'qt  '")
        else:
            return make_result("MP4_ISO_BMFF", "VIDEO_CONTAINER", "HIGH", {".mp4", ".m4v", ".3gp", ".mov"}, f"'ftyp' at offset 4, brand '{brand.decode('ascii', 'replace')}'")

    # 5. AVI
    if hl >= 12 and header[:4] == b"RIFF" and header[8:12] == b"AVI ":
        return make_result("AVI", "VIDEO_CONTAINER", "HIGH", {".avi"}, 'b"RIFF" at 0 and b"AVI " at 8')

    # 6. MATROSKA_WEBM
    if hl >= 4 and header[:4] == b"\x1a\x45\xdf\xa3":
        return make_result("MATROSKA_WEBM", "VIDEO_CONTAINER", "HIGH", {".mkv", ".webm"}, "bytes 1A 45 DF A3 at 0")

    # 7. FLV
    if hl >= 4 and header[:4] == b"FLV\x01":
        return make_result("FLV", "VIDEO_CONTAINER", "HIGH", {".flv"}, 'b"FLV\\x01" at 0')

    # 8. ASF_WMV
    asf_sig = bytes.fromhex("3026B2758E66CF11A6D900AA0062CE6C")
    if hl >= 16 and header[:16] == asf_sig:
        return make_result("ASF_WMV", "VIDEO_CONTAINER", "HIGH", {".wmv", ".asf"}, "ASF signature at 0")

    # 9. MPEG_PS
    if hl >= 4 and header[:4] == bytes.fromhex("000001BA"):
        return make_result("MPEG_PS", "VIDEO_CONTAINER", "HIGH", {".mpg", ".mpeg", ".vob", ".ps"}, "00 00 01 BA at 0")

    # 10. MPEG_TS
    if hl >= 377 and header[0] == 0x47 and header[188] == 0x47 and header[376] == 0x47:
        return make_result("MPEG_TS", "VIDEO_CONTAINER", "HIGH", {".ts", ".mts", ".m2ts"}, "byte 0x47 at offsets 0, 188 and 376")

    # 11. ZIP
    if hl >= 4 and header[:4] == b"PK\x03\x04":
        return make_result("ZIP", "ARCHIVE", "HIGH", {".zip"}, 'b"PK\\x03\\x04" at 0')

    disk_exts = {".img", ".dd", ".raw", ".bin"}

    # 12. NTFS_VOLUME
    if hl >= 11 and header[3:11] == b"NTFS    ":
        return make_result("NTFS_VOLUME", "DISK_IMAGE", "HIGH", disk_exts, 'b"NTFS    " at offset 3')

    # 13. EXFAT_VOLUME
    if hl >= 11 and header[3:11] == b"EXFAT   ":
        return make_result("EXFAT_VOLUME", "DISK_IMAGE", "HIGH", disk_exts, 'b"EXFAT   " at offset 3')

    # 14. FAT32_VOLUME
    if hl >= 90 and header[82:90] == b"FAT32   ":
        return make_result("FAT32_VOLUME", "DISK_IMAGE", "HIGH", disk_exts, 'b"FAT32   " at offset 82')

    # 15. FAT12_16_VOLUME
    if hl >= 62 and (header[54:62] == b"FAT12   " or header[54:62] == b"FAT16   "):
        sig_str = header[54:62].decode('ascii').strip()
        return make_result("FAT12_16_VOLUME", "DISK_IMAGE", "HIGH", disk_exts, f'b"{sig_str}   " at offset 54')

    # 16. GPT_DISK_IMAGE
    if hl >= 520 and header[512:520] == b"EFI PART":
        return make_result("GPT_DISK_IMAGE", "DISK_IMAGE", "HIGH", disk_exts, 'b"EFI PART" at offset 512')

    # 17. MBR_DISK_IMAGE
    if hl >= 512 and header[510:512] == b"\x55\xaa":
        return make_result("MBR_DISK_IMAGE", "DISK_IMAGE", "LOW", disk_exts, "bytes 55 AA at offsets 510-511")

    # Annex B start codes
    def check_annexb(header, hl):
        start = 0
        if hl >= 4 and header[:4] == bytes.fromhex("00000001"):
            start = 4
        elif hl >= 3 and header[:3] == bytes.fromhex("000001"):
            start = 3
            
        if start > 0 and hl > start:
            nal_byte = header[start]
            if (nal_byte & 0x80) == 0:
                nal_type_h264 = nal_byte & 0x1F
                nal_type_h265 = (nal_byte >> 1) & 0x3F
                if nal_type_h264 in (7, 9):
                    return "H264"
                if nal_type_h265 in (32, 33, 34, 35):
                    return "H265"
        return None

    annexb = check_annexb(header, hl)
    if annexb == "H264":
        return make_result("H264_ANNEXB_STREAM", "RAW_VIDEO_STREAM", "LOW", {".h264", ".264", ".bin", ".dvr"}, "H264 NAL header")
    elif annexb == "H265":
        return make_result("H265_ANNEXB_STREAM", "RAW_VIDEO_STREAM", "LOW", {".h265", ".265", ".hevc", ".bin"}, "H265 NAL header")

    # 20. UNKNOWN
    return {
        "detected_format": "UNKNOWN",
        "category": "UNKNOWN",
        "confidence": "NONE",
        "matched_signature": None,
        "extension_hint": ext,
        "extension_consistent": None
    }
