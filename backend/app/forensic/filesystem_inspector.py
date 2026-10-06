def inspect_filesystem(header_bytes: bytes) -> dict:
    """
    Analyzes the first bytes of a file to determine container and filesystem.
    This is a safe, read-only bounding check that extracts basic structural metadata.
    """
    container = "UNKNOWN"
    filesystem = "UNKNOWN"
    status = "UNKNOWN"
    structure = None
    
    length = len(header_bytes)
    
    # 1. Container Types
    if header_bytes.startswith(b"EVF\x09\x0d\x0a\xff\x00"):
        container = "E01"
        structure = {"container_signature": "EWF"}
    elif header_bytes.startswith(b"EVF2\x0d\x0a\x81\x00") or header_bytes.startswith(b"EVF2\x09\x0d\x0a\xff\x00"):
        container = "EX01"
        structure = {"container_signature": "EWF2"}
    else:
        # 2. Filesystem Types
        if length >= 11 and header_bytes[3:11] == b"NTFS    ":
            container = "RAW"
            filesystem = "NTFS"
            if length >= 80:
                bps = int.from_bytes(header_bytes[11:13], byteorder='little')
                spc = header_bytes[13]
                mft_lcn = int.from_bytes(header_bytes[48:56], byteorder='little')
                if bps in (512, 1024, 2048, 4096) and spc > 0:
                    structure = {
                        "bytes_per_sector": bps,
                        "sectors_per_cluster": spc,
                        "mft_logical_cluster_number": mft_lcn
                    }
        elif length >= 11 and header_bytes[3:11] == b"EXFAT   ":
            container = "RAW"
            filesystem = "exFAT"
        elif length >= 90 and header_bytes[82:90] == b"FAT32   ":
            container = "RAW"
            filesystem = "FAT32"
            if length >= 90:
                bps = int.from_bytes(header_bytes[11:13], byteorder='little')
                spc = header_bytes[13]
                rsvd = int.from_bytes(header_bytes[14:16], byteorder='little')
                fc = header_bytes[16]
                fsz = int.from_bytes(header_bytes[36:40], byteorder='little')
                if bps in (512, 1024, 2048, 4096) and spc > 0 and fc in (1, 2):
                    structure = {
                        "bytes_per_sector": bps,
                        "sectors_per_cluster": spc,
                        "reserved_sectors": rsvd,
                        "fat_count": fc,
                        "fat_size_32": fsz
                    }
        elif length >= 62 and header_bytes[54:62] == b"FAT16   ":
            container = "RAW"
            filesystem = "FAT16"
            if length >= 62:
                bps = int.from_bytes(header_bytes[11:13], byteorder='little')
                spc = header_bytes[13]
                rsvd = int.from_bytes(header_bytes[14:16], byteorder='little')
                fc = header_bytes[16]
                fsz = int.from_bytes(header_bytes[22:24], byteorder='little')
                if bps in (512, 1024, 2048, 4096) and spc > 0 and fc in (1, 2):
                    structure = {
                        "bytes_per_sector": bps,
                        "sectors_per_cluster": spc,
                        "reserved_sectors": rsvd,
                        "fat_count": fc,
                        "fat_size_16": fsz
                    }
        elif length >= 32774 and header_bytes[32769:32774] == b"CD001":
            container = "RAW"
            filesystem = "ISO 9660"
            if length >= 32898:
                vol_type = header_bytes[32768]
                lbs = int.from_bytes(header_bytes[32896:32898], byteorder='little')
                vol_id = header_bytes[32808:32840].decode('ascii', errors='ignore').strip()
                structure = {
                    "volume_descriptor_type": vol_type,
                    "logical_block_size": lbs,
                    "volume_identifier": vol_id
                }
        elif length >= 520 and header_bytes[512:520] == b"EFI PART":
            container = "RAW"
            filesystem = "GPT"
            if length >= 600:
                rev = int.from_bytes(header_bytes[520:524], byteorder='little')
                hsz = int.from_bytes(header_bytes[524:528], byteorder='little')
                clba = int.from_bytes(header_bytes[536:544], byteorder='little')
                blba = int.from_bytes(header_bytes[544:552], byteorder='little')
                fulba = int.from_bytes(header_bytes[552:560], byteorder='little')
                lulba = int.from_bytes(header_bytes[560:568], byteorder='little')
                pcnt = int.from_bytes(header_bytes[592:596], byteorder='little')
                psz = int.from_bytes(header_bytes[596:600], byteorder='little')
                
                if 92 <= hsz <= 512 and pcnt <= 128 and psz >= 128:
                    structure = {
                        "gpt_header_presence": True,
                        "revision": rev,
                        "header_size": hsz,
                        "current_lba": clba,
                        "backup_lba": blba,
                        "first_usable_lba": fulba,
                        "last_usable_lba": lulba,
                        "partition_entry_count": pcnt,
                        "partition_entry_size": psz
                    }
        elif length >= 512 and header_bytes[510:512] == b"\x55\xaa":
            container = "RAW"
            filesystem = "MBR"
            valid_entries = 0
            parts = []
            for i in range(4):
                off = 446 + (i * 16)
                if off + 16 <= length:
                    entry = header_bytes[off:off+16]
                    ptype = entry[4]
                    if ptype != 0x00:
                        ssec = int.from_bytes(entry[8:12], byteorder='little')
                        scnt = int.from_bytes(entry[12:16], byteorder='little')
                        if scnt > 0:
                            valid_entries += 1
                            parts.append({
                                "partition_type": ptype,
                                "start_sector": ssec,
                                "sector_count": scnt
                            })
            structure = {
                "partition_table_presence": True,
                "partition_entry_count": valid_entries,
                "partitions": parts
            }

    if container != "UNKNOWN" or filesystem != "UNKNOWN":
        status = "IDENTIFIED"
            
    res = {
        "container_type": container,
        "filesystem_type": filesystem,
        "status": status
    }
    if structure is not None:
        res["structure"] = structure
    return res
