"""The SWIG-style container façades exposed through pykmclib.Backend.Backend."""

from __future__ import annotations

import pytest

from pykmclib.Backend import Backend


def test_std_vector_default_construction_and_push_back():
    vec = Backend.StdVectorInt()
    assert vec.size() == 0
    vec.push_back(3)
    vec.push_back(4)
    assert vec.size() == 2
    assert list(vec) == [3, 4]


def test_std_vector_from_sequence():
    vec = Backend.StdVectorString(["A", "B", "C"])
    assert vec.size() == 3
    assert vec[1] == "B"
    assert isinstance(vec, Backend.StdVectorString)


def test_std_vector_sized_construction_is_zero_initialised():
    assert list(Backend.StdVectorInt(3)) == [0, 0, 0]
    assert list(Backend.StdVectorDouble(2)) == [0.0, 0.0]
    assert list(Backend.StdVectorString(2)) == ["", ""]
    assert list(Backend.StdVectorBool(2)) == [False, False]


def test_std_vector_fill_construction_makes_independent_copies():
    vec = Backend.StdVectorTypeBucket(3, Backend.TypeBucket(2))
    vec[0][0] = 1
    assert vec[1][0] == 0
    assert vec[2][0] == 0


def test_std_vector_equality_matches_plain_sequences():
    vec = Backend.StdVectorInt([1, 2, 3])
    assert vec == [1, 2, 3]
    assert vec == (1, 2, 3)
    assert vec != (1, 2, 4)

    nested = Backend.StdVectorStdVectorString([["A"], ["B"]])
    assert nested == (("A",), ("B",))


def test_std_map_facade():
    mapping = Backend.StdMapStringInt({"A": 1, "B": 2})
    mapping["C"] = 3
    assert mapping.size() == 3
    assert mapping == {"A": 1, "B": 2, "C": 3}


def test_coordinate_indexing_round_trip():
    coordinate = Backend.Coordinate(1.0, 2.0, 3.0)
    assert coordinate[0] == 1.0
    coordinate[2] = 7.5
    assert coordinate.z() == 7.5
    with pytest.raises(IndexError):
        coordinate[3]


def test_type_bucket_indexing_and_len():
    bucket = Backend.TypeBucket(2)
    bucket[1] = 4
    assert len(bucket) == size_of(bucket) == 2
    assert bucket[1] == 4
    with pytest.raises(IndexError):
        bucket[2]


def size_of(value):
    return value.size()
