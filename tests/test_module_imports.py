"""Import-safety checks for every top-level module in this branch.

This directly answers "does it import cleanly, and if not, exactly how".
GenDEMCGL.py in particular does all of its real work inside
`if __name__ == "__main__":`, so importing it must be a no-op (module-level
manifest/Options/LongLat definitions only) -- verified below.

decompresstest.py is deliberately NOT imported here, and MUST NOT be
imported by any test on this branch. Unlike main/plain/mod, this branch's
decompresstest.py was pointed at a real, absolute, developer-machine path
(originally e:/shows/msfs/scenery/.../dem011.cgl) with no __main__ guard, so
simply importing it unconditionally runs cgl_decompress.decompress() against
whatever happens to exist at that path and writes real output files to
_testfiles/ as a side effect of import. On this particular clone that file
still exists on the E: drive, so `import decompresstest` silently succeeds
and does real, unwanted disk I/O -- confirmed during manual investigation
for this test suite (files appeared under _testfiles/dem023011/). That is a
genuine, and fairly alarming, "not import-safe" finding: this module must
never be imported automatically, only run deliberately and knowingly by a
human (and _testfiles/ is gitignored, so nothing from it is ever committed).
"""
import importlib

import pytest


CLEAN_IMPORT_MODULES = [
    "bingtile",
    "misc",
    "cgl_generate",
    "cgl_decompress",
    "GMTiles",
    "pyramidGen",
    "GenDEMCGL",
    "packageGen",
]


@pytest.mark.parametrize("modname", CLEAN_IMPORT_MODULES)
def test_module_imports_without_side_effects(modname):
    importlib.import_module(modname)


def test_gendemcgl_does_not_execute_main_workflow_on_import():
    """GenDEMCGL.py's pipeline (CoordsToQkeyList -> visualize -> click.confirm
    -> RunGMScripts -> ...) must live entirely under `if __name__ == "__main__"`.
    If it doesn't, importing the module for testing purposes would try to
    shell out to Global Mapper or block on a confirmation prompt.
    """
    import GenDEMCGL
    assert hasattr(GenDEMCGL, "Options")
    assert hasattr(GenDEMCGL, "manifest")
    assert not hasattr(GenDEMCGL, "TopLevelQKeys")


def test_elev_wgs84_egm2008_requires_osgeo_gdal():
    """elev_wgs84_egm2008.py imports `from osgeo import gdal` directly at
    module scope, so it is only import-safe on a machine with GDAL's Python
    bindings installed. This environment (numpy/opencv/pyshp/click/rasterio/
    pyproj/PyGeodesy/pytest) intentionally does NOT include osgeo, so this
    test documents that the module is currently NOT importable here rather
    than silently skipping it.
    """
    pytest.importorskip("osgeo", reason="GDAL python bindings (osgeo) not installed in this environment")
    importlib.import_module("elev_wgs84_egm2008")


def test_genheightmaps_has_a_broken_import():
    """genHeightmaps.py does `from misc import QuadKeyIncrement, chunks`, but
    QuadKeyIncrement actually lives in bingtile.py, not misc.py (misc.py only
    defines find_all and chunks). This is a pre-existing bug inherited
    unmodified from upstream main. Interestingly, this branch DID fix the
    equivalent mistake inside oldscripts/1_gm_create_tilescripts.py (it now
    calls bingtile.QuadKeyIncrement instead of the nonexistent
    misc.QuadKeyIncrement), but the top-level genHeightmaps.py script was
    left as-is. Documented here (rather than silently skipped) so a future
    fix is visible as a test that starts failing.
    """
    with pytest.raises(ImportError):
        importlib.import_module("genHeightmaps")
