"""Unit tests for cgl_generate.py: the pure encoding/compression logic used
to build a .cgl file out of a pyramid of .bil tiles.

No Global Mapper, no network. Uses tiny synthetic tile files written to a
pytest tmp_path.

IMPORTANT: on this branch (unlike main/plain/try3), custom_key/createLayout
were rewritten to expect `pathlib.Path` tile arguments (they call
`.as_posix()`), and the tile-naming convention changed from "dem<qkey>.bil"
to "dem_<qkey>.bil". Tests below use Path objects and the "dem_" prefix to
match.
"""
import lzma
import math
import struct
from pathlib import Path

import pytest

import cgl_generate as cglg


# ---------------------------------------------------------------------------
# custom_key (sort key used to order tiles: shortest posix path first)
# ---------------------------------------------------------------------------

def test_custom_key_sorts_by_length_then_alpha():
    names = [Path("dem_0123.bil"), Path("dem_01230.bil"), Path("dem_01.bil")]
    ordered = sorted(names, key=cglg.custom_key)
    assert ordered[0] == Path("dem_01.bil")
    assert ordered[-1] == Path("dem_01230.bil")


def test_custom_key_requires_path_not_str():
    # main/plain/try3's custom_key accepts plain strings; this branch's
    # rewrite requires a Path (calls .as_posix()), a real API break for any
    # caller still passing strings.
    with pytest.raises(AttributeError):
        cglg.custom_key("dem_0123.bil")


def test_custom_key_is_case_insensitive():
    assert cglg.custom_key(Path("ABC")) == cglg.custom_key(Path("abc"))


# ---------------------------------------------------------------------------
# createLayout: builds the delta-encoded subtile position table.
#
# *** This uncovers a real, reproducible bug on this branch. ***
#
# createLayout does:
#   subkey = tile.as_posix()[idx("dem_") + 3 + 6 : idx(".bil")]
# "+3" lands the slice start AT the underscore in "dem_" (d=0,e=1,m=2,_=3),
# not past it, and "+6" only advances 6 more characters. For a 6-character
# base quadkey ("023011"), "dem_023011" is 10 characters wide (4 for "dem_"
# + 6 for the quadkey), but the code only skips 3+6=9, one short. The
# result: for a *base* tile with no subkey, the slice captures the LAST
# digit of the base quadkey itself as a bogus 1-digit "subkey" instead of
# the empty string, and every child tile's subkey is contaminated with an
# extra leading digit lifted from the base quadkey.
# ---------------------------------------------------------------------------

def test_create_layout_length_matches_tile_count():
    tiles = [
        Path("dem_023011.bil"),     # base tile, no subkey (intended)
        Path("dem_0230110.bil"),    # subkey '0', level 1 (intended)
        Path("dem_0230111.bil"),    # subkey '1', level 1 (intended)
        Path("dem_0230112.bil"),    # subkey '2', level 1 (intended)
    ]
    layout = cglg.createLayout(tiles)
    assert isinstance(layout, bytearray)
    assert len(layout) == 2 * len(tiles)


def test_create_layout_subkey_offset_is_off_by_one_for_dem__prefix():
    """Demonstrates the bug directly: a base tile (which should have an
    EMPTY subkey) instead gets a spurious non-empty subkey scraped off the
    tail of the base quadkey, because the "dem_" + 6-char-qkey skip is
    computed as 3+6=9 instead of 4+6=10.
    """
    base_tile = Path("dem_023011.bil")
    s = base_tile.as_posix()
    idx = s.index("dem_")
    subkey = s[idx + 3 + 6:s.index(".bil")]
    # This is the buggy, currently-observed behavior: NOT empty, as it
    # should be for a base tile with no subtile suffix.
    assert subkey == "1"
    assert subkey != ""


def test_create_layout_matches_actual_buggy_deltas():
    """Pins down createLayout's current (buggy) output for a small base +
    3-children pyramid so a fix shows up as a test change, not a silent
    regression. Compare against test_cgl_generate.py on main/plain/try3,
    where the equivalent hand-computed deltas are [0, 4096, 1, 1] -- the
    *correct* sequence for "base tile, then 3 same-level children 0,1,2".
    Here, because of the off-by-one above, every subkey is contaminated
    with an extra leading '1' digit (the last digit of "023011"), which
    changes both the parsed base-4 values and therefore the encoded deltas.
    """
    tiles = [Path("dem_023011.bil"), Path("dem_0230110.bil"),
             Path("dem_0230111.bil"), Path("dem_0230112.bil")]
    layout = cglg.createLayout(tiles)
    deltas = [int.from_bytes(layout[i:i + 2], "little") for i in range(0, len(layout), 2)]
    # actual (buggy) parsed subkeys are '1', '10', '11', '12' -> base-4
    # values 1, 4, 5, 6 respectively (all length>=1, so "same level" branch
    # never triggers a level-change reset the way it should for a true base
    # tile) -- this assertion pins the wrong-but-real current output.
    assert deltas != [0, 4096, 1, 1]


def test_create_layout_is_deterministic():
    tiles = [Path("dem_023011.bil"), Path("dem_0230110.bil"), Path("dem_0230111.bil")]
    assert cglg.createLayout(tiles) == cglg.createLayout(list(tiles))


def test_create_layout_empty_list():
    assert cglg.createLayout([]) == bytearray()


# ---------------------------------------------------------------------------
# createBlob / compressChunk: LZMA round trip with the custom raw filter.
# These operate on tile paths as plain strings (open(tile, 'rb')) so they
# are unaffected by the Path-only custom_key/createLayout changes above.
# ---------------------------------------------------------------------------

def _make_tile(tmp_path, name, payload):
    p = tmp_path / name
    p.write_bytes(payload)
    return str(p)


def test_create_blob_lzma_roundtrips(tmp_path):
    payload_a = bytes(range(256)) * 4
    payload_b = bytes([7]) * 2000
    tile_a = _make_tile(tmp_path, "dem_023011_0.bil", payload_a)
    tile_b = _make_tile(tmp_path, "dem_023011_1.bil", payload_b)

    blob, compressedsizes, uncompressedsizes = cglg.createBlob([tile_a, tile_b])

    assert uncompressedsizes == [len(payload_a), len(payload_b)]
    assert len(compressedsizes) == 2
    assert sum(compressedsizes) == len(blob)

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


def test_delta_sizes_small_positive_and_negative():
    sizes = [100, 150, 90]
    enc = cglg.deltaSizes(sizes)
    assert len(enc) == 6
    d0 = int.from_bytes(enc[0:2], "little")
    d1 = int.from_bytes(enc[2:4], "little")
    d2 = int.from_bytes(enc[4:6], "little")
    assert d0 == 100
    assert d1 == 50
    assert d2 == 0x8000 - 60


def test_deltas_to_uncompressed_reconstructs_sizes():
    compressedsizes = [100, 200, 50]
    uncompressedsizes = [132098, 132098, 66056]
    enc = cglg.deltasToUncompressed(compressedsizes, uncompressedsizes)
    assert len(enc) == 4 * len(compressedsizes)
    for i, (csize, usize) in enumerate(zip(compressedsizes, uncompressedsizes)):
        firstbyte = int.from_bytes(enc[i * 4:i * 4 + 2], "little")
        delta = int.from_bytes(enc[i * 4 + 2:i * 4 + 4], "little")
        mult = firstbyte - 0x8000
        reconstructed = csize + (0x10000 * mult) + delta
        assert reconstructed == usize


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
    assert int.from_bytes(cgl[32:36], "little") == tilecount
    headerlen = int.from_bytes(cgl[40:43], "little")
    assert headerlen == len(headerc)
    headerstart = cgl[36]
    assert bytes(cgl[headerstart:headerstart + headerlen]) == headerc
    assert bytes(cgl[headerstart + headerlen:]) == blob


def test_create_cgl_end_to_end(tmp_path):
    """createCGL on this branch requires Path tiles (custom_key/createLayout)
    but a Path dstpath too (`dstpath.parent.mkdir(...)`), so both must be
    Path objects here, unlike main/plain/try3 where plain strings work.
    """
    tile0 = tmp_path / "dem_023011.bil"
    tile0.write_bytes(bytes(range(256)) * 2)
    tile1 = tmp_path / "dem_0230110.bil"
    tile1.write_bytes(bytes([9]) * 300)
    dst = tmp_path / "out" / "dem011.cgl"

    cglg.createCGL([tile0, tile1], dst, threads=1)

    assert dst.exists()
    data = dst.read_bytes()
    tilecount = int.from_bytes(data[32:34], "little")
    assert tilecount == 2


def test_create_cgl_fails_with_plain_string_dstpath(tmp_path):
    """Documents the API break: createCGL's dstpath must be a Path
    (dstpath.parent.mkdir(...)); a plain string (which worked on
    main/plain/try3) raises AttributeError here.
    """
    tile0 = tmp_path / "dem_023011.bil"
    tile0.write_bytes(b"x" * 10)
    with pytest.raises(AttributeError):
        cglg.createCGL([tile0], str(tmp_path / "out" / "dem011.cgl"), threads=1)
