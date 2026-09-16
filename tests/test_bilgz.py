"""Unit tests for bilgz.py, a small wrapper this branch adds around gzip for
reading gzip-compressed .bil files.

Note bilgz.open() hardcodes mode='rb' -- it can only ever be used for
reading, regardless of what a caller might expect from a generic "open"
helper (no write mode is reachable through this wrapper).
"""
import gzip

import pytest

import bilgz


def test_open_reads_back_gzip_compressed_bytes(tmp_path):
    original = b"some fake .bil elevation payload" * 100
    gz_path = tmp_path / "dem023011.bil.gz"
    with gzip.open(gz_path, "wb") as f:
        f.write(original)

    with bilgz.open(str(gz_path)) as f:
        restored = f.read()

    assert restored == original


def test_open_is_read_only_regardless_of_intent(tmp_path):
    # bilgz.open hardcodes mode='rb'; there is no way to request a write
    # mode through this wrapper, so writing through the returned handle
    # must fail.
    gz_path = tmp_path / "dem023011.bil.gz"
    with gzip.open(gz_path, "wb") as f:
        f.write(b"seed")

    with bilgz.open(str(gz_path)) as f:
        with pytest.raises(OSError):
            f.write(b"more data")
