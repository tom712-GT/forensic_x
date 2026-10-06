def inspect_filesystem(header_bytes: bytes) -> dict:
    """
    Analyzes the first bytes of a file to determine container and filesystem.
    This is a safe, read-only bounding check.
    """
    container = "UNKNOWN"
    filesystem = "UNKNOWN"
    status = "UNKNOWN"
    
    length = len(header_bytes)
    
    # 1. Container Types
    if header_bytes.startswith(b"EVF\x09\x0d\x0a\xff\x00"):
        container = "E01"
    elif header_bytes.startswith(b"EVF2\x0d\x0a\x81\x00") or header_bytes.startswith(b"EVF2\x09\x0d\x0a\xff\x00"):
        container = "EX01"
    else:
        # 2. Filesystem Types (assuming RAW container if identified)
        if length >= 11 and header_bytes[3:11] == b"NTFS    ":
            container = "RAW"
            filesystem = "NTFS"
        elif length >= 11 and header_bytes[3:11] == b"EXFAT   ":
            container = "RAW"
            filesystem = "exFAT"
        elif length >= 90 and header_bytes[82:90] == b"FAT32   ":
            container = "RAW"
            filesystem = "FAT32"
        elif length >= 62 and header_bytes[54:62] == b"FAT16   ":
            container = "RAW"
            filesystem = "FAT16"
        elif length >= 32774 and header_bytes[32769:32774] == b"CD001":
            container = "RAW"
            filesystem = "ISO 9660"
        elif length >= 520 and header_bytes[512:520] == b"EFI PART":
            container = "RAW"
            filesystem = "GPT"
        elif length >= 512 and header_bytes[510:512] == b"\x55\xaa":
            container = "RAW"
            filesystem = "MBR"

    if container != "UNKNOWN" or filesystem != "UNKNOWN":
        status = "IDENTIFIED"
            
    return {
        "container_type": container,
        "filesystem_type": filesystem,
        "status": status
    }
