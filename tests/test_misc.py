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
