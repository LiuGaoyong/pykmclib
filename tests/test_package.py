"""Package level checks: the extension loads and the public API is exported."""

from __future__ import annotations

import re

import pytest


def test_version_is_pep440():
    import pykmclib

    assert re.fullmatch(r"\d+\.\d+\.\d+([abc]\d+|\.dev\d+|\.post\d+)?", pykmclib.__version__)


def test_version_is_released_as_pykmclib():
    import pykmclib

    assert pykmclib.__version__ == "0.0.1"


def test_backend_extension_is_importable():
    from pykmclib.Backend import Backend

    assert callable(Backend.MPICommons.isMaster)
    assert Backend.MPICommons.isMaster() is True
    assert callable(Backend.MPICommons.barrier)


def test_builtin_cpp_rate_calculators_are_registered():
    from pykmclib.Backend import Custom

    names = {name for name in dir(Custom) if name.endswith("Calculator")}
    assert {"BucketsTestCalculator", "IsingTestCalculator"} <= names


def test_public_api_is_exported():
    import pykmclib

    for name in (
        "KMCLatticeModel",
        "KMCConfiguration",
        "KMCInteractions",
        "KMCProcess",
        "KMCLattice",
        "KMCUnitCell",
        "KMCControlParameters",
        "OnTheFlyMSD",
        "KMCRateCalculatorPlugin",
        "MPICommons",
    ):
        assert name in pykmclib.__all__
        assert getattr(pykmclib, name) is not None


@pytest.mark.parametrize("rng_name", ["MT", "MINSTD", "RANLUX24", "RANLUX48"])
def test_rng_types_are_exposed_and_accepted(rng_name):
    from pykmclib.Backend import Backend

    assert isinstance(getattr(Backend, rng_name), int)
    assert Backend.setRngType(getattr(Backend, rng_name))
