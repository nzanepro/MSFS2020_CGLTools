"""Unit tests for misc.py helper functions."""
import misc


def test_chunks_splits_evenly():
    result = list(misc.chunks([1, 2, 3, 4, 5, 6], 2))
    assert result == [[1, 2], [3, 4], [5, 6]]


def test_chunks_last_chunk_may_be_short():
    result = list(misc.chunks([1, 2, 3, 4, 5], 2))
    assert result == [[1, 2], [3, 4], [5]]


def test_chunks_n_larger_than_list():
    result = list(misc.chunks([1, 2], 10))
    assert result == [[1, 2]]


def test_find_all_locates_every_occurrence():
    assert list(misc.find_all("abcabcabc", "abc")) == [0, 3, 6]


def test_find_all_no_match():
    assert list(misc.find_all("abcdef", "xyz")) == []


def test_find_all_non_overlapping_by_default():
    # "aaaa" contains "aa" starting at 0 and 2 with the default (non-overlapping) search
    assert list(misc.find_all("aaaa", "aa")) == [0, 2]


def test_oldscripts_misc_has_same_helpers():
    # Load oldscripts/misc.py by file path (rather than `import misc`, which
    # would just return the already-cached root misc module under the same
    # name) so this genuinely exercises the oldscripts copy.
    import importlib.util
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "oldscripts", "misc.py")
    spec = importlib.util.spec_from_file_location("oldscripts_misc", path)
    old_misc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old_misc)
    assert list(old_misc.chunks([1, 2, 3], 2)) == [[1, 2], [3]]
    assert list(old_misc.find_all("abcabc", "abc")) == [0, 3]
