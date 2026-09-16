"""Unit tests for pyramidGen.py: the Laplacian-pyramid tile/delta generation
that turns a Tile/<CGLLevel> DEM tile into a downsampled base tile plus 4
per-quadrant delta tiles.

No Global Mapper, no real DEM data -- synthetic 257x257 int16 .bil files are
written to a pytest tmp_path in exactly the layout loadToNPArray() expects
(basepath/Tile/<level>/dem<qkey>.bil).
"""
import struct

import numpy as np
import pytest

import bingtile as bt
import pyramidGen as pg


def _write_tile(basepath, qkey, arr):
    filename = str(basepath) + "\\Tile/" + str(len(qkey)) + "/dem" + qkey + ".bil"
    import os
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb") as f:
        f.write(arr.astype(np.int16).tobytes())
    return filename


def _constant_tile(value):
    return np.full((257, 257), value, dtype=np.int16)


def test_load_to_np_array_places_tiles_in_3x3_neighborhood(tmp_path):
    qkey = "023011"
    # loadToNPArray looks for the 3x3 neighborhood of children of `qkey+'0'`
    beginningcoords = bt.QuadKeyToTileXY(qkey + '0')
    center_subqkey = bt.TileXYToQuadKey(beginningcoords[0], beginningcoords[1], beginningcoords[2])
    _write_tile(tmp_path, center_subqkey, _constant_tile(42))

    found, arr = pg.loadToNPArray(qkey, str(tmp_path))
    assert found is True
    assert arr.shape == (1024, 1024)
    assert arr.dtype == np.int16
    # the tile we wrote should show up somewhere in the middle of the 1024x1024
    # working array (upper-left quadrant offsets start at (256,256))
    assert (arr == 42).sum() >= 256 * 256


def test_load_to_np_array_not_found_when_no_tiles(tmp_path):
    found, arr = pg.loadToNPArray("023099", str(tmp_path))
    assert found is False
    assert arr.shape == (1024, 1024)
    assert (arr == 0).all()


def test_create_level_tile_and_sub_deltas_constant_field_roundtrips(tmp_path):
    """For a spatially-constant elevation field, downsampling (whether via
    Gaussian blur or plain decimation) and then pyrUp'ing back should
    reproduce the same constant almost everywhere, so the Laplacian delta
    should be ~0 in the interior of the tile (away from border effects).
    This is a real correctness property of the pyramid encoding, not just a
    shape check.
    """
    qkey = "023011"
    beginningcoords = bt.QuadKeyToTileXY(qkey + '0')
    value = 500
    # loadToNPArray actually walks a 4x4 neighborhood (xoffset/yoffset run
    # -1..2 inclusive, since `while xoffset < 3` starting at -1 yields
    # -1,0,1,2), so all 16 neighbors must be populated to avoid zero-bleed
    # from the large-sigma Gaussian blur contaminating the tile we check.
    for xo in range(-1, 3):
        for yo in range(-1, 3):
            subqkey = bt.TileXYToQuadKey(beginningcoords[0] + xo, beginningcoords[1] + yo, beginningcoords[2])
            _write_tile(tmp_path, subqkey, _constant_tile(value))

    pg.createLevelTileAndSubDeltas(qkey, str(tmp_path))

    # base (downsampled) tile for this qkey should exist and be the same
    # constant value throughout (256x256 valid region; the [257] edge row/col
    # of a zero-initialized array can differ, so only check the interior).
    base_path = str(tmp_path) + "\\Tile\\" + str(len(qkey)) + "\\dem" + qkey + ".bil"
    with open(base_path, "rb") as f:
        base = np.frombuffer(f.read(), np.int16).reshape((257, 257))
    assert np.all(base[0:256, 0:256] == value)

    # delta tiles should exist, have the saveDelta 7-byte header, and their
    # payload should be all (or almost all) zero for a constant input field.
    for i in range(4):
        delta_qkey = qkey + str(i)
        delta_path = str(tmp_path) + "\\Delta\\" + str(len(delta_qkey)) + "\\dem" + delta_qkey + ".bil"
        with open(delta_path, "rb") as f:
            raw = f.read()
        header, payload = raw[:7], raw[7:]
        multi = struct.unpack("f", header[0:4])[0]
        assert multi == pytest.approx(1.0)
        delta_arr = np.frombuffer(payload, np.int16).reshape((257, 257))
        # interior should be exactly reconstructed (constant field is a fixed
        # point of this Gaussian-blur/decimate + pyrUp pipeline away from
        # borders)
        nonzero_fraction = np.count_nonzero(delta_arr[10:-10, 10:-10]) / delta_arr[10:-10, 10:-10].size
        assert nonzero_fraction < 0.01


def test_save_and_to8bit_delta_header_format(tmp_path):
    qkey = "023011"
    nparr = np.arange(257 * 257, dtype=np.int16).reshape((257, 257)) % 1000
    pg.saveTile(str(tmp_path) + "\\Tile", qkey, nparr)

    tile_path = str(tmp_path) + "\\Tile\\" + str(len(qkey)) + "\\dem" + qkey + ".bil"
    with open(tile_path, "rb") as f:
        raw = f.read()
    assert len(raw) == 257 * 257 * 2  # raw int16 payload, no header yet

    pg.to8bit(qkey, str(tmp_path))
    with open(tile_path, "rb") as f:
        raw2 = f.read()
    # to8bit rewraps the same tile through saveDelta, adding the 7-byte
    # header (heightscale float32 + int16 offset + constant byte 16)
    assert len(raw2) == 7 + 257 * 257 * 2
    header, payload = raw2[:7], raw2[7:]
    multi = struct.unpack("f", header[0:4])[0]
    assert multi == pytest.approx(1.0)
    assert header[6] == 16
    restored = np.frombuffer(payload, np.int16).reshape((257, 257))
    assert np.array_equal(restored, nparr)


def test_save_delta_header_encodes_multiplier_and_offset():
    qkey = "0230110"
    data = np.zeros((257, 257), dtype=np.int16)
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        pg.saveDelta(d, qkey, data, multi=2.0, offsetm=10)
        path = d + "\\" + str(len(qkey)) + "\\dem" + qkey + ".bil"
        with open(path, "rb") as f:
            raw = f.read()
        multi = struct.unpack("f", raw[0:4])[0]
        offset = int.from_bytes(raw[4:6], "little", signed=True)
        assert multi == pytest.approx(2.0)
        assert offset == 5  # floor(offsetm / multi) = floor(10/2)
        assert raw[6] == 16
