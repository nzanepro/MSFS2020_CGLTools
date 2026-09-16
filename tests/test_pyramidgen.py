"""Unit tests for pyramidGen.py: the Laplacian-pyramid tile/delta generation
that turns a Tile/<CGLLevel> DEM tile into a downsampled base tile plus 4
per-quadrant delta tiles.

No Global Mapper, no real DEM data -- synthetic 257x257 int16 .bil files are
written to a pytest tmp_path in exactly the layout loadToNPArray() expects
on this branch (basepath/Tile/<level>/dem_<qkey>.bil -- note the "dem_"
prefix, different from main/plain/try3's "dem<qkey>.bil").

IMPORTANT: this branch's rewrite of createLevelTileAndSubDeltas /
saveDelta has THREE severe, independently-reproduced bugs (see the tests
below):
  1. saveDelta() no longer creates its own parent directory (main/plain/
     try3's saveDelta calls os.makedirs(..., exist_ok=True) first). If the
     Delta/<level> directory doesn't already exist, every call raises
     FileNotFoundError. In the real pipeline this is only masked because
     GenDEMCGL.py's __main__ block happens to pre-create Tile/Delta
     directories for every level up front.
  2. The call that writes the downsampled base tile (`saveTile(...)`) is
     commented out, so no Tile/<level>/dem_<qkey>.bil file is ever produced.
     Since the NEXT (lower) pyramid level's loadToNPArray() depends on
     finding exactly that file, this breaks pyramid generation below the
     very first level processed -- the whole pyramid below the top is
     silently empty.
  3. All four delta-quadrant files (delta0..delta3) are written to the
     SAME path, `Delta/<level>/dem_<qkey>.bil` (the intended per-quadrant
     suffix, computed into a throwaway variable `x`, is never used in the
     actual filename). Each write clobbers the previous one, so only
     delta3's data survives on disk; delta0/1/2 are silently lost.
"""
import struct
from pathlib import Path

import numpy as np
import pytest

import bingtile as bt
import pyramidGen as pg


def _write_tile(basepath: Path, qkey, arr):
    filename = basepath / "Tile" / str(len(qkey)) / f"dem_{qkey}.bil"
    filename.parent.mkdir(parents=True, exist_ok=True)
    filename.write_bytes(arr.astype(np.int16).tobytes())
    return filename


def _constant_tile(value):
    return np.full((257, 257), value, dtype=np.int16)


def test_load_to_np_array_places_tiles_in_neighborhood(tmp_path):
    qkey = "023011"
    beginningcoords = bt.QuadKeyToTileXY(qkey + '0')
    center_subqkey = bt.TileXYToQuadKey(beginningcoords[0], beginningcoords[1], beginningcoords[2])
    _write_tile(tmp_path, center_subqkey, _constant_tile(42))

    found, arr = pg.loadToNPArray(qkey, tmp_path)
    assert found is True
    assert arr.shape == (1024, 1024)
    assert (arr == 42).sum() >= 256 * 256


def test_load_to_np_array_not_found_when_no_tiles(tmp_path):
    found, arr = pg.loadToNPArray("023099", tmp_path)
    assert found is False
    assert (arr == 0).all()


def _populate_full_neighborhood(tmp_path, qkey, value):
    beginningcoords = bt.QuadKeyToTileXY(qkey + '0')
    for xo in range(-1, 3):
        for yo in range(-1, 3):
            subqkey = bt.TileXYToQuadKey(beginningcoords[0] + xo, beginningcoords[1] + yo, beginningcoords[2])
            _write_tile(tmp_path, subqkey, _constant_tile(value))


def test_create_level_tile_and_sub_deltas_crashes_without_precreated_delta_dir(tmp_path):
    """BUG (1): saveDelta() no longer creates its parent directory (unlike
    main/plain/try3's saveDelta, which calls os.makedirs(exist_ok=True)),
    so calling createLevelTileAndSubDeltas with a fresh basepath -- with no
    other code having pre-created Delta/<level> -- crashes outright.
    """
    qkey = "023011"
    _populate_full_neighborhood(tmp_path, qkey, 500)
    with pytest.raises(FileNotFoundError):
        pg.createLevelTileAndSubDeltas(qkey, tmp_path)


def test_create_level_tile_and_sub_deltas_does_not_write_the_base_tile(tmp_path):
    """BUG (2): saveTile(...) is commented out in createLevelTileAndSubDeltas,
    so the downsampled Tile/<level>/dem_<qkey>.bil this level is supposed
    to produce for the NEXT (lower-detail) pyramid level to consume is
    never written. On main/plain/try3 the equivalent function always
    writes this file when `found` is True. (Delta dir pre-created here to
    work around bug (1) above and isolate this one.)
    """
    qkey = "023011"
    _populate_full_neighborhood(tmp_path, qkey, 500)
    (tmp_path / "Delta" / str(len(qkey))).mkdir(parents=True, exist_ok=True)

    pg.createLevelTileAndSubDeltas(qkey, tmp_path)

    tile_path = tmp_path / "Tile" / str(len(qkey)) / f"dem_{qkey}.bil"
    assert not tile_path.exists()


def test_create_level_tile_and_sub_deltas_delta_quadrants_clobber_each_other(tmp_path):
    """BUG (3): delta0/delta1/delta2/delta3 are all written to the same path
    `Delta/<level>/dem_<qkey>.bil` (the per-quadrant suffix computed into
    variable `x` is never used in the actual filename), so only the last
    write (delta3) survives. On main/plain/try3, four distinct files
    dem<qkey>0.bil .. dem<qkey>3.bil are produced. Here we can only find
    one leftover Delta file for this qkey's whole level directory. (Delta
    dir pre-created here to work around bug (1) above and isolate this one.)
    """
    qkey = "023011"
    _populate_full_neighborhood(tmp_path, qkey, 500)
    (tmp_path / "Delta" / str(len(qkey))).mkdir(parents=True, exist_ok=True)

    pg.createLevelTileAndSubDeltas(qkey, tmp_path)

    delta_dir = tmp_path / "Delta" / str(len(qkey))
    assert delta_dir.is_dir()
    delta_files = list(delta_dir.glob("*.bil"))
    # intended behavior (matching main/plain/try3) would be 4 distinct files
    assert len(delta_files) == 1
    assert delta_files[0].name == f"dem_{qkey}.bil"

    # and its content is delta3's (the last of the four writes), not a
    # combination of all four quadrants
    raw = delta_files[0].read_bytes()
    header, payload = raw[:7], raw[7:]
    delta_arr = np.frombuffer(payload, np.int16).reshape((257, 257))
    # constant input field -> delta should be ~0 regardless of which
    # quadrant survived, so this doesn't by itself prove *which* quadrant
    # won, but confirms only one wrote through successfully.
    assert delta_arr.shape == (257, 257)


def test_save_tile_writes_raw_payload_and_hdr_sidecar(tmp_path):
    qkey = "023011"
    nparr = np.arange(257 * 257, dtype=np.int16).reshape((257, 257)) % 1000
    tile_path = tmp_path / "Tile" / str(len(qkey)) / f"dem_{qkey}.bil"
    tile_path.parent.mkdir(parents=True, exist_ok=True)

    pg.saveTile(tile_path, qkey, nparr)

    assert tile_path.exists()
    raw = tile_path.read_bytes()
    assert len(raw) == 257 * 257 * 2
    restored = np.frombuffer(raw, np.int16).reshape((257, 257))
    assert np.array_equal(restored, nparr)
    # saveTile also writes a BIL header sidecar
    hdr_path = tile_path.with_suffix(".hdr")
    assert hdr_path.exists()
    assert "NROWS          257" in hdr_path.read_text()


def test_save_delta_header_encodes_multiplier_and_offset(tmp_path):
    data = np.zeros((257, 257), dtype=np.int16)
    path = tmp_path / "dem_0230110.bil"
    pg.saveDelta(path, data, multi=2.0, offsetm=10)

    raw = path.read_bytes()
    multi = struct.unpack("f", raw[0:4])[0]
    offset = int.from_bytes(raw[4:6], "little", signed=True)
    assert multi == pytest.approx(2.0)
    assert offset == 5  # floor(offsetm / multi) = floor(10/2)
    assert raw[6] == 16


def test_to8bit_rewraps_existing_tile_with_delta_header(tmp_path):
    qkey = "023011"
    nparr = np.arange(257 * 257, dtype=np.int16).reshape((257, 257)) % 500
    tile_path = tmp_path / "Tile" / str(len(qkey)) / f"dem_{qkey}.bil"
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    tile_path.write_bytes(nparr.tobytes())

    pg.to8bit(qkey, tmp_path)

    raw = tile_path.read_bytes()
    assert len(raw) == 7 + 257 * 257 * 2
    header, payload = raw[:7], raw[7:]
    assert header[6] == 16
    restored = np.frombuffer(payload, np.int16).reshape((257, 257))
    assert np.array_equal(restored, nparr)
