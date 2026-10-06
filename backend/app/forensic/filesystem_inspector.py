def inspect_filesystem(header_bytes: bytes) -> dict:
    """
    Analyzes the first bytes of a file to determine container and filesystem.
    This is a safe, read-only bounding check.
    """
    container = "UNKNOWN"
    filesystem = "UNKNOWN"
    
    # E01 Check (EnCase)
    if header_bytes.startswith(b"EVF\x09\x0d\x0a\xff\x00"):
        container = "E01"
    else:
        # Check filesystems to imply RAW container
        if len(header_bytes) >= 11 and header_bytes[3:11] == b"NTFS    ":
            container = "RAW"
            filesystem = "NTFS"
        elif len(header_bytes) >= 1082 and header_bytes[1080:1082] == b"\x53\xef":
            container = "RAW"
            filesystem = "EXT4"
        elif len(header_bytes) >= 11 and header_bytes[3:11] in (b"MSDOS5.0", b"mkdosfs\x00"):
            container = "RAW"
            filesystem = "FAT32"
            
    return {
        "container_type": container,
        "filesystem_type": filesystem
    }
