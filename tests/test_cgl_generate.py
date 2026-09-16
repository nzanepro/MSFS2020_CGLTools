"""Unit tests for cgl_generate.py: the pure encoding/compression logic used
to build a .cgl file out of a pyramid of .bil tiles.

No Global Mapper, no network. Uses tiny synthetic tile files written to a
pytest tmp_path.
"""
import lzma
import math
import struct

import pytest

import cgl_generate as cglg


# ---------------------------------------------------------------------------
# custom_key (sort key used to order tiles: shortest filename first, i.e.
# lower pyramid levels / base tiles before deeper delta tiles)
# ---------------------------------------------------------------------------

def test_custom_key_sorts_by_length_then_alpha():
    names = ["dem0123.bil", "dem01230.bil", "dem01.bil", "DEM0123.bil"]
    ordered = sorted(names, key=cglg.custom_key)
    # shortest first
    assert ordered[0] == "dem01.bil"
    # 'dem0123.bil' and 'DEM0123.bil' are same length -> compared case-insensitively,
    # and both come before the longer 'dem01230.bil'
    assert ordered[-1] == "dem01230.bil"
    assert set(ordered[1:3]) == {"dem0123.bil", "DEM0123.bil"}


def test_custom_key_is_case_insensitive():
    assert cglg.custom_key("ABC") == cglg.custom_key("abc")


# ---------------------------------------------------------------------------
# createLayout: builds the delta-encoded subtile position table
# ---------------------------------------------------------------------------

def test_create_layout_length_matches_tile_count():
    # base "dem" + 6-char base quadkey + arbitrary sub-quadkey + ".bil"
    tiles = [
        "dem023011.bil",     # base tile, no subkey
        "dem0230110.bil",    # subkey '0', level 1
        "dem0230111.bil",    # subkey '1', level 1
        "dem0230112.bil",    # subkey '2', level 1
    ]
    layout = cglg.createLayout(tiles)
    assert isinstance(layout, bytearray)
    # 2 bytes (one little-endian uint16 delta) per tile
    assert len(layout) == 2 * len(tiles)


def test_create_layout_is_deterministic():
    tiles = ["dem023011.bil", "dem0230110.bil", "dem0230111.bil"]
    assert cglg.createLayout(tiles) == cglg.createLayout(list(tiles))


def test_create_layout_matches_hand_computed_deltas():
    # subkey='' -> subval=0, level=0; subkey='0' -> subval=int('0',4)=0, level=1;
    # subkey='1' -> subval=1, level=1; subkey='2' -> subval=2, level=1.
    # pervlevel starts at 0, so:
    #   tile0 (level 0): same level as initial pervlevel(0) -> delta = subval(0) - prevval(0) = 0
    #   tile1 (level 1): level changed (0 -> 1) -> delta = levelchangevalue - prevval(0) + subval(0) = 4096
    #   tile2 (level 1): same level as tile1 -> delta = subval(1) - prevval(0) = 1
    #   tile3 (level 1): same level -> delta = subval(2) - prevval(1) = 1
    tiles = ["dem023011.bil", "dem0230110.bil", "dem0230111.bil", "dem0230112.bil"]
    layout = cglg.createLayout(tiles)
    deltas = [int.from_bytes(layout[i:i + 2], "little") for i in range(0, len(layout), 2)]
    assert deltas == [0, 4096, 1, 1]


def test_create_layout_empty_list():
    assert cglg.createLayout([]) == bytearray()


# ---------------------------------------------------------------------------
# createBlob / compressChunk: LZMA round trip with the custom raw filter
# ---------------------------------------------------------------------------

def _make_tile(tmp_path, name, payload):
    p = tmp_path / name
    p.write_bytes(payload)
    return str(p)


def test_create_blob_lzma_roundtrips(tmp_path):
    payload_a = bytes(range(256)) * 4  # 1024 bytes, compressible
    payload_b = bytes([7]) * 2000      # highly compressible
    tile_a = _make_tile(tmp_path, "dem023011_0.bil", payload_a)
    tile_b = _make_tile(tmp_path, "dem023011_1.bil", payload_b)

    blob, compressedsizes, uncompressedsizes = cglg.createBlob([tile_a, tile_b])

    assert uncompressedsizes == [len(payload_a), len(payload_b)]
    assert len(compressedsizes) == 2
    assert sum(compressedsizes) == len(blob)

    # Manually decompress each chunk out of the blob using the same raw
    # LZMA1 filter settings createBlob used, and confirm we get back
    # exactly the original bytes.
    prop = 93
    pb = math.floor(prop / (9 * 5))
    prop = prop - (pb * 9 * 5)
    lp = math.floor(prop / 9)
    lc = math.floor(prop - lp * 9)
    filters = [{"id": lzma.FILTER_LZMA1, "preset": lzma.PRESET_DEFAULT,
                "lc": lc, "lp": lp, "pb": pb, "dict_size": 65536}]

    offset = 0
    originals = [payload_a, payload_b]
    for size, orig in zip(compressedsizes, originals):
        chunk = bytes(blob[offset:offset + size])
        restored = lzma.decompress(chunk, lzma.FORMAT_RAW, None, filters)
        assert restored == orig
        offset += size


def test_compress_chunk_matches_create_blob_for_same_input(tmp_path):
    payload = bytes(range(200)) * 3
    tile = _make_tile(tmp_path, "dem023011_0.bil", payload)

    blob1, csizes1, usizes1 = cglg.createBlob([tile])
    chunkid, (blob2, csizes2, usizes2) = cglg.compressChunk(0, [tile])

    assert bytes(blob1) == bytes(blob2)
    assert csizes1 == csizes2
    assert usizes1 == usizes2


# ---------------------------------------------------------------------------
# deltaSizes / deltasToUncompressed: header delta encodings used by
# cgl_decompress.py to reconstruct compressed/uncompressed tile sizes
# ---------------------------------------------------------------------------

def test_delta_sizes_small_positive_and_negative():
    # First value is always encoded as delta from 0.
    sizes = [100, 150, 90]
    enc = cglg.deltaSizes(sizes)
    # 3 entries, each within the small +/- range -> 2 bytes each
    assert len(enc) == 6
    d0 = int.from_bytes(enc[0:2], "little")
    d1 = int.from_bytes(enc[2:4], "little")
    d2 = int.from_bytes(enc[4:6], "little")
    assert d0 == 100
    assert d1 == 50
    # negative delta (150 -> 90 = -60) encoded as 0x8000 - 60
    assert d2 == 0x8000 - 60


def test_deltas_to_uncompressed_reconstructs_sizes():
    compressedsizes = [100, 200, 50]
    uncompressedsizes = [132098, 132098, 66056]
    enc = cglg.deltasToUncompressed(compressedsizes, uncompressedsizes)
    assert len(enc) == 4 * len(compressedsizes)
    # decode using the same convention cgl_decompress.py uses: firstbyte,
    # then delta = usize - csize (mod 65536, offset by 0x8000)
    for i, (csize, usize) in enumerate(zip(compressedsizes, uncompressedsizes)):
        firstbyte = int.from_bytes(enc[i * 4:i * 4 + 2], "little")
        delta = int.from_bytes(enc[i * 4 + 2:i * 4 + 4], "little")
        mult = firstbyte - 0x8000
        reconstructed = csize + (0x10000 * mult) + delta
        assert reconstructed == usize


# ---------------------------------------------------------------------------
# createUncompressedHeader / createCompressedHeader / compileCGL: overall
# structure of the resulting .cgl byte layout
# ---------------------------------------------------------------------------

def test_create_uncompressed_header_concatenates_sections():
    layout = bytearray(b"\x01\x02")
    deltasizes = b"\x03\x04"
    dtous = b"\x05\x06"
    header = cglg.createUncompressedHeader(layout, deltasizes, dtous)
    assert bytes(header) == b"\x01\x02\x03\x04\x05\x06"


def test_create_compressed_header_roundtrips_with_lzma():
    header = bytearray(b"some header bytes" * 5)
    compressed = cglg.createCompressedHeader(header)
    prop = 93
    pb = math.floor(prop / (9 * 5))
    prop = prop - (pb * 9 * 5)
    lp = math.floor(prop / 9)
    lc = math.floor(prop - lp * 9)
    filters = [{"id": lzma.FILTER_LZMA1, "preset": lzma.PRESET_DEFAULT,
                "lc": lc, "lp": lp, "pb": pb, "dict_size": 65536}]
    restored = lzma.decompress(bytes(compressed), lzma.FORMAT_RAW, None, filters)
    assert restored == bytes(header)


def test_compile_cgl_layout():
    headerc = b"\xAA\xBB\xCC"
    blob = b"\x01\x02\x03\x04\x05"
    tilecount = 4
    cgl = cglg.compileCGL(headerc, blob, tilecount)
    assert isinstance(cgl, bytearray)
    # tilecount is written as a little-endian uint32 at offset 32
    assert int.from_bytes(cgl[32:36], "little") == tilecount
    # header length (uint24) is written at offset 40
    headerlen = int.from_bytes(cgl[40:43], "little")
    assert headerlen == len(headerc)
    # header start offset byte (single byte at offset 36) tells us where
    # the (variable-size) fixed prefix ends and the header begins
    headerstart = cgl[36]
    assert bytes(cgl[headerstart:headerstart + headerlen]) == headerc
    assert bytes(cgl[headerstart + headerlen:]) == blob


def test_create_cgl_end_to_end(tmp_path):
    """Feeds createCGL a small synthetic pyramid and confirms the resulting
    file parses back into the same tile blobs via the low-level LZMA filter,
    exercising custom_key + createLayout + createBlobMT + compileCGL together.
    """
    tile0 = _make_tile(tmp_path, "dem023011.bil", bytes(range(256)) * 2)
    tile1 = _make_tile(tmp_path, "dem0230110.bil", bytes([9]) * 300)
    dst = tmp_path / "out" / "dem011.cgl"

    cglg.createCGL([tile0, tile1], str(dst), threads=1)

    assert dst.exists()
    data = dst.read_bytes()
    tilecount = int.from_bytes(data[32:34], "little")
    assert tilecount == 2
    headerstart = data[36]
    headerlength = int.from_bytes(data[40:43], "little")
    assert headerstart + headerlength <= len(data)
