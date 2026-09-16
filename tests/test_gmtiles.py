"""Tests for the *script-text generation* logic in GMTiles.py only.

SAFETY: this file must NEVER call runGMScript / RunGMScripts / visualize, and
must never invoke global_mapper.exe (directly or via subprocess). Those calls
launch the real, GUI desktop application, which would hang indefinitely on a
license/nag dialog in this unattended environment. We only verify the
generated *.gms script text is well-formed.
"""
import os

import pytest
import shapefile

import GMTiles as gmt
import bingtile as bt


class _Options:
    def __init__(self, basepath):
        self.Basepath = str(basepath)
        self.DEMInputFiles = [r'C:\test\dem_a.bil', r'C:\test\dem_b.gmc']
        self.CGLLevel = 6
        self.MaxLevel = 8


def test_create_global_mapper_script_contains_expected_directives(tmp_path):
    opts = _Options(tmp_path)
    subqkeys = [bt.TileXYToQuadKey(23, 11, 6), bt.TileXYToQuadKey(23, 12, 6)]

    gmt.CreateGlobalMapperScript(0, subqkeys, opts)

    script_path = tmp_path / "tilescript_000.gms"
    assert script_path.exists()
    text = script_path.read_text()
    lines = text.splitlines()

    assert lines[0] == "GLOBAL_MAPPER_SCRIPT VERSION=1.00"
    for demfile in opts.DEMInputFiles:
        assert any(l.startswith("IMPORT") and demfile in l for l in lines)
    assert any(l.startswith('LOAD_PROJECTION PROJ="EPSG:4326"') for l in lines)

    export_lines = [l for l in lines if l.startswith("EXPORT_ELEVATION")]
    assert len(export_lines) == len(subqkeys)
    for qkey, line in zip(subqkeys, export_lines):
        assert "TYPE=BIL" in line
        assert "BYTES_PER_SAMPLE=2" in line
        assert f"dem{qkey}.bil" in line
        # bounding box present and well-formed (west,south,east,north)
        assert "LAT_LON_BOUNDS=" in line
        bounds_str = line.split("LAT_LON_BOUNDS=")[1].split(" ")[0]
        west, south, east, north = (float(x) for x in bounds_str.split(","))
        assert west < east
        assert south < north


def test_create_global_mapper_script_filenames_scale_with_index(tmp_path):
    opts = _Options(tmp_path)
    gmt.CreateGlobalMapperScript(0, [], opts)
    gmt.CreateGlobalMapperScript(7, [], opts)
    assert (tmp_path / "tilescript_000.gms").exists()
    assert (tmp_path / "tilescript_007.gms").exists()


def test_create_coverage_poly_shapefile_round_trips(tmp_path):
    qkeys = [
        [bt.TileXYToQuadKey(23, 11, 6), 0],
        [bt.TileXYToQuadKey(24, 11, 6), 1],
    ]
    gmt.createCoveragePolyShapefile(qkeys, str(tmp_path))

    reader = shapefile.Reader(str(tmp_path / "qKeyCoverage.shp"))
    shapes = reader.shapes()
    records = reader.records()
    assert len(shapes) == len(qkeys)
    assert len(records) == len(qkeys)
    names = [r[0] for r in records]
    assert names == [q[0] for q in qkeys]
    paddingflags = [bool(r[1]) for r in records]
    assert paddingflags == [False, True]
    # each polygon should have 4 corners closing back to the start (5 pts)
    for shp in shapes:
        assert len(shp.points) == 5
        assert shp.points[0] == shp.points[-1]


def test_calculate_max_disk_usage_is_positive_and_scales_with_qkey_count():
    class Opts:
        CGLLevel = 6
        MaxLevel = 8
    usage_1 = gmt.calculateMaxDiskUsageMB(1, Opts)
    usage_2 = gmt.calculateMaxDiskUsageMB(2, Opts)
    assert usage_1 > 0
    assert usage_2 > usage_1
    # roughly double for double the qkeys (small constant offset aside)
    assert usage_2 == pytest.approx(2 * usage_1, rel=0.05)


def test_no_global_mapper_executable_is_invoked_by_script_generation(monkeypatch, tmp_path):
    """Guard-rail test: make sure script generation never shells out."""
    def _boom(*args, **kwargs):
        raise AssertionError("subprocess must not be invoked by script generation")
    monkeypatch.setattr(gmt.subprocess, "run", _boom)
    monkeypatch.setattr(gmt.subprocess, "Popen", _boom)

    opts = _Options(tmp_path)
    gmt.CreateGlobalMapperScript(0, [bt.TileXYToQuadKey(1, 1, 6)], opts)
    gmt.createGMVisualizationScript(opts)
    gmt.createCoveragePolyShapefile([[bt.TileXYToQuadKey(1, 1, 6), 0]], str(tmp_path))
    # deliberately do NOT call runGMScript / RunGMScripts / visualize here.
