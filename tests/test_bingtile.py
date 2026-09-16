"""Unit tests for bingtile.py: the Bing Maps Tile System coordinate math
(https://docs.microsoft.com/en-us/bingmaps/articles/bing-maps-tile-system)
that everything else (GMTiles script generation, CGL layout, pyramid
generation) is built on top of.

No Global Mapper, no network, no real DEM files required.
"""
import math

import pytest

import bingtile as bt


# ---------------------------------------------------------------------------
# Clip / MapSize
# ---------------------------------------------------------------------------

def test_clip_within_range():
    assert bt.Clip(5, 0, 10) == 5


def test_clip_below_min():
    assert bt.Clip(-5, 0, 10) == 0


def test_clip_above_max():
    assert bt.Clip(15, 0, 10) == 10


@pytest.mark.parametrize("level,expected", [(1, 512), (2, 1024), (6, 16384), (12, 1048576)])
def test_map_size(level, expected):
    assert bt.MapSize(level) == expected


# ---------------------------------------------------------------------------
# LatLongToPixelXY / PixelXYToLatLong
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [1, 2, 3, 6, 10, 15])
def test_origin_maps_to_map_center(level):
    # At (0,0) sinLatitude=0 -> y=0.5, and longitude=0 -> x=0.5, so
    # the pixel coordinate must land exactly on the middle of the map,
    # independent of the implementation, by construction of the projection.
    px, py = bt.LatLongToPixelXY(0.0, 0.0, level)
    half = bt.MapSize(level) // 2
    assert px == half
    assert py == half


@pytest.mark.parametrize("lat,lon,level", [
    (60.1699, 24.9384, 10),   # Helsinki
    (51.5074, -0.1278, 12),   # London
    (-33.8688, 151.2093, 8),  # Sydney
    (0.0, 0.0, 5),
    (45.0, -179.9, 9),
    (-45.0, 179.9, 9),
])
def test_latlong_pixelxy_roundtrip(lat, lon, level):
    px, py = bt.LatLongToPixelXY(lat, lon, level)
    rlat, rlon = bt.PixelXYToLatLong(px, py, level)
    # one pixel worth of slop at this level of detail
    mapsize = bt.MapSize(level)
    lat_eps = 180.0 / mapsize * 4
    lon_eps = 360.0 / mapsize * 4
    assert abs(rlat - lat) < lat_eps
    assert abs(rlon - lon) < lon_eps


def test_latitude_clips_to_valid_mercator_range():
    # Web Mercator cannot represent the poles; the function must clip
    # rather than raising or returning nonsense/NaN.
    px, py = bt.LatLongToPixelXY(89.9, 0.0, 4)
    px_max, py_max = bt.LatLongToPixelXY(bt.MaxLatitude, 0.0, 4)
    assert (px, py) == (px_max, py_max)

    px, py = bt.LatLongToPixelXY(-89.9, 0.0, 4)
    px_min, py_min = bt.LatLongToPixelXY(bt.MinLatitude, 0.0, 4)
    assert (px, py) == (px_min, py_min)


def test_longitude_clips_at_antimeridian():
    px, _ = bt.LatLongToPixelXY(0.0, 200.0, 4)
    px_max, _ = bt.LatLongToPixelXY(0.0, bt.MaxLongitude, 4)
    assert px == px_max


# ---------------------------------------------------------------------------
# PixelXY <-> TileXY
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("px,py,expected", [
    (0, 0, (0, 0)),
    (255, 255, (0, 0)),
    (256, 256, (1, 1)),
    (256 * 5 + 10, 256 * 3 + 200, (5, 3)),
])
def test_pixelxy_to_tilexy(px, py, expected):
    assert bt.PixelXYToTileXY(px, py) == expected


def test_tilexy_pixelxy_roundtrip_upperleft():
    for tx, ty in [(0, 0), (1, 0), (0, 1), (7, 13), (100, 200)]:
        px, py = bt.TileXYToPixelXY(tx, ty)
        assert bt.PixelXYToTileXY(px, py) == (tx, ty)


# ---------------------------------------------------------------------------
# TileXY <-> QuadKey
# ---------------------------------------------------------------------------

def test_quadkey_known_values_level1():
    # Level-1 quadrants per the Bing tile system spec: (0,0)->'0', (1,0)->'1',
    # (0,1)->'2', (1,1)->'3'
    assert bt.TileXYToQuadKey(0, 0, 1) == '0'
    assert bt.TileXYToQuadKey(1, 0, 1) == '1'
    assert bt.TileXYToQuadKey(0, 1, 1) == '2'
    assert bt.TileXYToQuadKey(1, 1, 1) == '3'


@pytest.mark.parametrize("tx,ty,level", [
    (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1),
    (0, 0, 6), (23, 11, 6), (63, 63, 6),
    (0, 0, 12), (2047, 1234, 12),
    (5, 9, 4),
])
def test_tilexy_quadkey_roundtrip(tx, ty, level):
    qk = bt.TileXYToQuadKey(tx, ty, level)
    assert len(qk) == level
    rtx, rty, rlevel = bt.QuadKeyToTileXY(qk)
    assert (rtx, rty, rlevel) == (tx, ty, level)


def test_quadkey_digits_are_0_to_3_only():
    for tx in range(0, 16):
        for ty in range(0, 16):
            qk = bt.TileXYToQuadKey(tx, ty, 4)
            assert set(qk) <= {'0', '1', '2', '3'}


# ---------------------------------------------------------------------------
# QuadKeyIncrement / ListSubQKeys
# ---------------------------------------------------------------------------

def test_quadkey_increment_simple():
    assert bt.QuadKeyIncrement('0') == '1'
    assert bt.QuadKeyIncrement('1') == '2'
    assert bt.QuadKeyIncrement('2') == '3'


def test_quadkey_increment_carries_within_level():
    assert bt.QuadKeyIncrement('03') == '10'
    assert bt.QuadKeyIncrement('033') == '100'
    assert bt.QuadKeyIncrement('230') == '231'


def test_list_sub_qkeys_returns_all_children_at_level():
    subs = bt.ListSubQKeys('02', 4)
    # 2 extra levels of detail -> 4**2 = 16 children, all starting with '02'
    assert len(subs) == 16
    assert len(set(subs)) == 16
    assert all(s.startswith('02') and len(s) == 4 for s in subs)


def test_subtile_count_matches_formula():
    # sum_{level=minlevel}^{MaxLevel} 4**(level-baselevel)
    assert bt.SubtileCount(6, 6, 6) == 1
    assert bt.SubtileCount(6, 6, 7) == 1 + 4
    assert bt.SubtileCount(6, 7, 8) == 4 + 16


# ---------------------------------------------------------------------------
# qKeyToBoundingLatLong / PixelDimensions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("qkey", ['0', '1', '2', '3', '023011', '0231010112'])
def test_bounding_box_is_well_formed(qkey):
    west, north, east, south = bt.qKeyToBoundingLatLong(qkey)
    assert west < east
    assert south < north
    assert bt.MinLongitude <= west < east <= bt.MaxLongitude
    assert bt.MinLatitude <= south < north <= bt.MaxLatitude


def test_bounding_box_center_maps_back_into_same_tile():
    qkey = '023011'
    west, north, east, south = bt.qKeyToBoundingLatLong(qkey)
    clat = (north + south) / 2
    clon = (west + east) / 2
    tx, ty = bt.PixelXYToTileXY(*bt.LatLongToPixelXY(clat, clon, len(qkey)))
    assert bt.TileXYToQuadKey(tx, ty, len(qkey)) == qkey


def test_pixel_dimensions():
    pw, ph = bt.PixelDimensions(east=10, west=0, north=5, south=0, pixels=10)
    assert pw == pytest.approx(1.0)
    assert ph == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# TileXYsToQkeys / CoordsToQkeyList (used to build the top-level CGL grid)
# ---------------------------------------------------------------------------

class _Opts:
    padding = 1
    CGLLevel = 6


def test_tilexys_to_qkeys_marks_padding_tiles():
    qkeys = bt.TileXYsToQkeys((5, 5), (6, 6), _Opts)
    # 2x2 requested area + 1 tile padding on every side -> 4x4 = 16 total
    assert len(qkeys) == 16
    padding_flags = [q[1] for q in qkeys]
    core_flags = [q[1] for q in qkeys if q[0] in (
        bt.TileXYToQuadKey(5, 5, 6), bt.TileXYToQuadKey(6, 5, 6),
        bt.TileXYToQuadKey(5, 6, 6), bt.TileXYToQuadKey(6, 6, 6))]
    assert all(f == 0 for f in core_flags)
    assert sum(padding_flags) == 16 - 4


class _LatLong:
    def __init__(self, longitude, latitude):
        self.longitude = longitude
        self.latitude = latitude


def test_coords_to_qkeylist_upper_left_is_north_west_of_lower_right():
    ul = _LatLong(18.60, 70.75)
    lr = _LatLong(31.90, 59.20)
    qkeys = bt.CoordsToQkeyList(ul, lr, _Opts)
    assert len(qkeys) > 0
    for qk, _padding in qkeys:
        assert len(qk) == _Opts.CGLLevel
