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
