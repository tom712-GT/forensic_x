import pytest
from app.forensic.filesystem_inspector import inspect_filesystem

def test_inspect_e01():
    header = b"EVF\x09\x0d\x0a\xff\x00" + b"\x00" * 65000
    res = inspect_filesystem(header)
    assert res["container_type"] == "E01"
    assert res["filesystem_type"] == "UNKNOWN"
    assert res["status"] == "IDENTIFIED"

def test_inspect_ex01():
    header = b"EVF2\x0d\x0a\x81\x00" + b"\x00" * 65000
    res = inspect_filesystem(header)
    assert res["container_type"] == "EX01"
    assert res["filesystem_type"] == "UNKNOWN"
    assert res["status"] == "IDENTIFIED"

def test_inspect_ntfs():
    header = b"\x00\x00\x00NTFS    " + b"\x00" * 65000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "NTFS"
    assert res["status"] == "IDENTIFIED"

def test_inspect_exfat():
    header = b"\x00\x00\x00EXFAT   " + b"\x00" * 65000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "exFAT"

def test_inspect_fat32():
    header = b"\x00" * 82 + b"FAT32   " + b"\x00" * 65000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "FAT32"

def test_inspect_fat16():
    header = b"\x00" * 54 + b"FAT16   " + b"\x00" * 65000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "FAT16"

def test_inspect_iso9660():
    header = b"\x00" * 32769 + b"CD001" + b"\x00" * 33000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "ISO 9660"

def test_inspect_gpt():
    header = b"\x00" * 512 + b"EFI PART" + b"\x00" * 65000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "GPT"

def test_inspect_mbr():
    header = b"\x00" * 510 + b"\x55\xaa" + b"\x00" * 65000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "MBR"

def test_inspect_unknown():
    header = b"RandomBytes" * 100
    res = inspect_filesystem(header)
    assert res["container_type"] == "UNKNOWN"
    assert res["filesystem_type"] == "UNKNOWN"
    assert res["status"] == "UNKNOWN"

def test_inspect_truncated():
    header = b"\x00\x00\x00NT"
    res = inspect_filesystem(header)
    assert res["container_type"] == "UNKNOWN"
    assert res["filesystem_type"] == "UNKNOWN"
    assert res["status"] == "UNKNOWN"

def test_inspect_mbr_structure():
    # Valid MBR with one partition
    header = bytearray(b"\x00" * 65536)
    header[510:512] = b"\x55\xaa"
    # Partition 1 at 446
    header[446 + 4] = 0x07 # NTFS
    header[446 + 8 : 446 + 12] = (2048).to_bytes(4, 'little') # start sector
    header[446 + 12 : 446 + 16] = (102400).to_bytes(4, 'little') # sector count
    
    res = inspect_filesystem(bytes(header))
    assert res["filesystem_type"] == "MBR"
    assert "structure" in res
    assert res["structure"]["partition_table_presence"] is True
    assert res["structure"]["partition_entry_count"] == 1
    assert len(res["structure"]["partitions"]) == 1
    assert res["structure"]["partitions"][0]["partition_type"] == 0x07
    assert res["structure"]["partitions"][0]["start_sector"] == 2048
    assert res["structure"]["partitions"][0]["sector_count"] == 102400

def test_inspect_gpt_structure():
    header = bytearray(b"\x00" * 65536)
    header[512:520] = b"EFI PART"
    header[520:524] = (0x00010000).to_bytes(4, 'little') # Revision
    header[524:528] = (92).to_bytes(4, 'little') # Header size
    header[536:544] = (1).to_bytes(8, 'little') # Current LBA
    header[544:552] = (2).to_bytes(8, 'little') # Backup LBA
    header[552:560] = (34).to_bytes(8, 'little') # First usable
    header[560:568] = (1000).to_bytes(8, 'little') # Last usable
    header[592:596] = (128).to_bytes(4, 'little') # Part entries count
    header[596:600] = (128).to_bytes(4, 'little') # Part entry size
    
    res = inspect_filesystem(bytes(header))
    assert res["filesystem_type"] == "GPT"
    assert "structure" in res
    s = res["structure"]
    assert s["revision"] == 65536
    assert s["header_size"] == 92
    assert s["current_lba"] == 1
    assert s["backup_lba"] == 2
    assert s["first_usable_lba"] == 34
    assert s["last_usable_lba"] == 1000
    assert s["partition_entry_count"] == 128
    assert s["partition_entry_size"] == 128

def test_inspect_fat32_structure():
    header = bytearray(b"\x00" * 65536)
    header[82:90] = b"FAT32   "
    header[11:13] = (512).to_bytes(2, 'little') # bytes_per_sector
    header[13] = 8 # sectors_per_cluster
    header[14:16] = (32).to_bytes(2, 'little') # reserved_sectors
    header[16] = 2 # fat_count
    header[36:40] = (1000).to_bytes(4, 'little') # fat_size_32
    
    res = inspect_filesystem(bytes(header))
    assert res["filesystem_type"] == "FAT32"
    assert "structure" in res
    s = res["structure"]
    assert s["bytes_per_sector"] == 512
    assert s["sectors_per_cluster"] == 8
    assert s["reserved_sectors"] == 32
    assert s["fat_count"] == 2
    assert s["fat_size_32"] == 1000

def test_inspect_ntfs_structure():
    header = bytearray(b"\x00" * 65536)
    header[3:11] = b"NTFS    "
    header[11:13] = (512).to_bytes(2, 'little') # bps
    header[13] = 8 # spc
    header[48:56] = (4).to_bytes(8, 'little') # mft_lcn
    
    res = inspect_filesystem(bytes(header))
    assert res["filesystem_type"] == "NTFS"
    assert "structure" in res
    s = res["structure"]
    assert s["bytes_per_sector"] == 512
    assert s["sectors_per_cluster"] == 8
    assert s["mft_logical_cluster_number"] == 4

def test_inspect_iso9660_structure():
    header = bytearray(b"\x00" * 65536)
    header[32769:32774] = b"CD001"
    header[32768] = 1 # Type
    header[32896:32898] = (2048).to_bytes(2, 'little') # Logical block size
    header[32808:32840] = b"MY_VOLUME".ljust(32, b" ")
    
    res = inspect_filesystem(bytes(header))
    assert res["filesystem_type"] == "ISO 9660"
    assert "structure" in res
    s = res["structure"]
    assert s["volume_descriptor_type"] == 1
    assert s["logical_block_size"] == 2048
    assert s["volume_identifier"] == "MY_VOLUME"

def test_inspect_e01_structure():
    header = b"EVF\x09\x0d\x0a\xff\x00" + b"\x00" * 65000
    res = inspect_filesystem(header)
    assert res["container_type"] == "E01"
    assert "structure" in res
    assert res["structure"]["container_signature"] == "EWF"

def test_inspect_malformed_structure():
    # FAT32 with invalid bytes_per_sector (e.g. 513) should not return structure
    header = bytearray(b"\x00" * 65536)
    header[82:90] = b"FAT32   "
    header[11:13] = (513).to_bytes(2, 'little')
    header[13] = 8
    header[14:16] = (32).to_bytes(2, 'little')
    header[16] = 2
    header[36:40] = (1000).to_bytes(4, 'little')
    
    res = inspect_filesystem(bytes(header))
    assert res["filesystem_type"] == "FAT32"
    assert "structure" not in res
