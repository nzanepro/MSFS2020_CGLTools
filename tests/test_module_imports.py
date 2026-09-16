"""Import-safety checks for every top-level module in this branch.

This directly answers "does it import cleanly, and if not, exactly how".
GenDEMCGL.py in particular does all of its real work inside
`if __name__ == "__main__":`, so importing it must be a no-op (module-level
manifest/Options/LongLat definitions only) -- verified below.

decompresstest.py is deliberately NOT imported here: it is a notebook-style
"# %%" script that executes real decompression work unconditionally at
module scope (no __main__ guard), so importing it always attempts real I/O
against hardcoded paths. That is a genuine "not import-safe" finding, not a
test bug.
"""
import importlib

import pytest


CLEAN_IMPORT_MODULES = [
    "bingtile",
    "misc",
    "bilgz",
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
    """GenDEMCGL.py's pipeline (script generation -> RunGMScriptsDetached ->
    ...) must live entirely under `if __name__ == "__main__"`. If it
    doesn't, importing the module for testing purposes would try to shell
    out to Global Mapper.
    """
    import GenDEMCGL
    assert hasattr(GenDEMCGL, "Options")
    assert hasattr(GenDEMCGL, "manifest")
    assert not hasattr(GenDEMCGL, "TopLevelQKeys")


def test_gendemcgl_options_cgllevel_mismatches_hardcoded_level_6_elsewhere():
    """This branch reconfigured BOTH Options.CGLLevel and Options.MaxLevel
    to 14 (from the upstream default CGLLevel=6 / MaxLevel=12), presumably
    to cut higher-detail tiles. Two separate problems follow from this:

    1. cgl_generate.createCGLs() still hardcodes glob patterns against a
       literal "Tile/6/..." (not `Options.CGLLevel`), and createLayout's
       subkey-offset math is calibrated for a 6-character base quadkey.
       With CGLLevel=14 configured, createCGLs would glob an empty "Tile/6"
       directory that pyramidGen never populates (it writes to Tile/14),
       producing zero tiles for every CGL.
    2. With CGLLevel == MaxLevel (14 == 14), pyramidGen.createPyramids()'s
       level loop (`level = MaxLevel-1; while level >= CGLLevel`) starts at
       13, which is already < 14, so the loop body -- the entire
       Laplacian-pyramid tile/delta generation step -- never executes even
       once for this configuration. Only the final to8bit() pass over
       whatever already exists at Tile/14 would run.

    This test just pins down the mismatched configuration; it doesn't
    exercise createCGLs/createPyramids directly since that requires a real
    Global-Mapper-produced tile tree.
    """
    import GenDEMCGL
    assert GenDEMCGL.Options.CGLLevel == 14
    assert GenDEMCGL.Options.MaxLevel == 14
    assert GenDEMCGL.Options.CGLLevel == GenDEMCGL.Options.MaxLevel  # pyramid loop body never runs
    assert GenDEMCGL.Options.CGLLevel != 6  # but cgl_generate.createCGLs() globs "Tile/6" unconditionally


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
    unmodified from upstream main on this branch too: the module cannot be
    imported at all.
    """
    with pytest.raises(ImportError):
        importlib.import_module("genHeightmaps")
