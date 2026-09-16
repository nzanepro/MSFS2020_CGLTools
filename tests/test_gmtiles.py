"""Tests for the *script-text generation* logic in GMTiles.py only.

SAFETY: this file must NEVER call runGMScript / RunGMScripts / RunGMScriptsDetached
/ visualize, and must never invoke global_mapper.exe (directly or via
subprocess). Those calls launch the real, GUI desktop application, which
would hang indefinitely on a license/nag dialog in this unattended
environment. We only verify the generated *.gms script text is well-formed.

Note this branch's CreateGlobalMapperScript takes `Basepath` as a
pathlib.Path (does `opts.Basepath / f"tilescript_..."`), unlike
main/plain/try3 which accept a plain string.
"""
import os
from pathlib import Path

import pytest
import shapefile

import GMTiles as gmt
import bingtile as bt


class _Options:
    def __init__(self, basepath: Path):
        self.Basepath = Path(basepath)
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
        assert f"dem_{qkey}.bil" in line
        assert "GEN_PRJ_FILE=YES" in line
        assert "LAT_LON_BOUNDS=" in line
        bounds_str = line.split("LAT_LON_BOUNDS=")[1].split(" ")[0]
        west, south, east, north = (float(x) for x in bounds_str.split(","))
        assert west < east
        assert south < north


def test_create_global_mapper_script_requires_path_basepath(tmp_path):
    class BadOptions(_Options):
        def __init__(self, basepath):
            super().__init__(basepath)
            self.Basepath = str(basepath)  # plain string, not a Path

    with pytest.raises(TypeError):
        gmt.CreateGlobalMapperScript(0, [], BadOptions(tmp_path))


def test_create_coverage_poly_shapefile_round_trips_and_writes_prj(tmp_path):
    qkeys = [
        [bt.TileXYToQuadKey(23, 11, 6), 0],
        [bt.TileXYToQuadKey(24, 11, 6), 1],
    ]
    gmt.createCoveragePolyShapefile(qkeys, tmp_path)

    reader = shapefile.Reader(str(tmp_path / "qKeyCoverage.shp"))
    shapes = reader.shapes()
    records = reader.records()
    assert len(shapes) == len(qkeys)
    names = [r[0] for r in records]
    assert names == [q[0] for q in qkeys]
    paddingflags = [bool(r[1]) for r in records]
    assert paddingflags == [False, True]
    for shp in shapes:
        assert len(shp.points) == 5
        assert shp.points[0] == shp.points[-1]

    # this branch also writes a .prj sidecar alongside the shapefile
    prj_path = tmp_path / "qKeyCoverage.prj"
    assert prj_path.exists()
    assert "GEOGCS" in prj_path.read_text()
    assert "WGS_1984" in prj_path.read_text()


def test_write_bil_header_contains_expected_fields(tmp_path):
    hdr_path = tmp_path / "dem_023011.hdr"
    gmt.writeBILHeader(hdr_path)
    text = hdr_path.read_text()
    assert "NROWS          257" in text
    assert "NCOLS          257" in text
    assert "NBITS          16" in text
    assert "BYTEORDER      I" in text


def test_calculate_max_disk_usage_is_positive_and_scales_with_qkey_count():
    class Opts:
        CGLLevel = 6
        MaxLevel = 8
    usage_1 = gmt.calculateMaxDiskUsageMB(1, Opts)
    usage_2 = gmt.calculateMaxDiskUsageMB(2, Opts)
    assert usage_1 > 0
    assert usage_2 > usage_1
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
    gmt.createCoveragePolyShapefile([[bt.TileXYToQuadKey(1, 1, 6), 0]], tmp_path)
    # deliberately do NOT call runGMScript / RunGMScripts /
    # RunGMScriptsDetached / visualize here.
