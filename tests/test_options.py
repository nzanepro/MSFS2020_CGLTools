"""Unit tests for the Options.py dataclass this branch introduces (not present
on main/other variants, where the same fields live inline in GenDEMCGL.py).
"""
import multiprocessing as mp

from Options import Options


def test_options_has_expected_fields_and_types():
    assert isinstance(Options.CGLLevel, int)
    assert isinstance(Options.MaxLevel, int)
    assert isinstance(Options.padding, int)
    assert isinstance(Options.DEMInputFiles, list)
    assert isinstance(Options.GMExePath, str)
    assert isinstance(Options.Basepath, str)
    assert isinstance(Options.TargetName, str)
    assert isinstance(Options.MultiThreadPyramids, bool)


def test_options_level_ordering_is_sane():
    # CGLLevel is the base/lowest-detail level baked into every CGL; MaxLevel
    # is the highest-detail level cut from source DEMs. MaxLevel must be >=
    # CGLLevel or the whole pyramid scheme (createPyramids/createCGLs) makes
    # no sense.
    assert Options.MaxLevel >= Options.CGLLevel


def test_options_thread_counts_are_positive():
    assert Options.GMThreads >= 1
    assert Options.ProcessingThreads >= 1
    assert Options.GMThreads <= mp.cpu_count() * 4  # sanity upper bound


def test_options_padding_is_boolean_like():
    assert Options.padding in (0, 1)
