import pytest
from app.forensic.filesystem_inspector import inspect_filesystem

def test_inspect_e01():
    header = b"EVF\x09\x0d\x0a\xff\x00" + b"\x00" * 8000
    res = inspect_filesystem(header)
    assert res["container_type"] == "E01"
    assert res["filesystem_type"] == "UNKNOWN"

def test_inspect_ntfs():
    header = b"\x00\x00\x00NTFS    " + b"\x00" * 8000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "NTFS"

def test_inspect_fat32_msdos():
    header = b"\x00\x00\x00MSDOS5.0" + b"\x00" * 8000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "FAT32"

def test_inspect_fat32_mkdosfs():
    header = b"\x00\x00\x00mkdosfs\x00" + b"\x00" * 8000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "FAT32"

def test_inspect_ext4():
    header = b"\x00" * 1080 + b"\x53\xef" + b"\x00" * 7000
    res = inspect_filesystem(header)
    assert res["container_type"] == "RAW"
    assert res["filesystem_type"] == "EXT4"

def test_inspect_unknown():
    header = b"RandomBytes" * 100
    res = inspect_filesystem(header)
    assert res["container_type"] == "UNKNOWN"
    assert res["filesystem_type"] == "UNKNOWN"

def test_inspect_truncated():
    header = b"\x00\x00\x00NT"
    res = inspect_filesystem(header)
    assert res["container_type"] == "UNKNOWN"
    assert res["filesystem_type"] == "UNKNOWN"
