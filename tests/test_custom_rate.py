"""Python side rate calculators, driven from C++ through pybind11 trampolines.

This exercises the feature that only works when the binding layer dispatches
virtual calls from C++ back into Python (one call per rate evaluation).
"""

from __future__ import annotations

import numpy as np

from pykmclib import (
    KMCConfiguration,
    KMCControlParameters,
    KMCInteractions,
    KMCLattice,
    KMCLatticeModel,
    KMCProcess,
    KMCRateCalculatorPlugin,
    KMCUnitCell,
)


class DoubleRateCalculator(KMCRateCalculatorPlugin):
    """Doubles every rate and counts how often C++ called back."""

    def initialize(self):
        self.calls = 0

    def rate(self, coords, types_before, types_after, rate_constant, process_number, global_coordinate):
        assert coords.shape[1] == 3
        assert isinstance(types_before, (list, tuple))
        self.calls += 1
        return 2.0 * rate_constant

    def cutoff(self):
        return 1.0

    def cacheRates(self):
        return False

    def excludeFromCaching(self):
        return []


def build_model(rate_calculator=None):
    unit_cell = KMCUnitCell(cell_vectors=np.eye(3), basis_points=[[0.0, 0.0, 0.0]])
    lattice = KMCLattice(unit_cell=unit_cell, repetitions=(4, 4, 1), periodic=(True, True, False))
    configuration = KMCConfiguration(lattice=lattice, types=["B"] * 16, possible_types=["A", "B"])
    coordinates = [[0.0, 0.0, 0.0]]
    processes = [
        KMCProcess(coordinates, ["A"], ["B"], basis_sites=[0], rate_constant=2.0),
        KMCProcess(coordinates, ["B"], ["A"], basis_sites=[0], rate_constant=1.0),
    ]
    interactions = KMCInteractions(processes=processes, implicit_wildcards=True)
    if rate_calculator is not None:
        interactions.setRateCalculator(rate_calculator=rate_calculator)
    return KMCLatticeModel(configuration=configuration, interactions=interactions)


def run(model, steps=200, seed=99):
    model.run(control_parameters=KMCControlParameters(number_of_steps=steps, dump_interval=steps, seed=seed))
    return model._KMCLatticeModel__cpp_timer.simulationTime()


def test_python_rate_calculator_is_called_from_cpp():
    model = build_model(rate_calculator=DoubleRateCalculator)
    model.run(control_parameters=KMCControlParameters(number_of_steps=20, dump_interval=20, seed=7))

    calculator = model._backend().interactions().rateCalculator()
    assert isinstance(calculator, DoubleRateCalculator)
    assert calculator.calls > 0


def test_custom_rates_are_used_by_the_backend():
    model = build_model(rate_calculator=DoubleRateCalculator)
    assert model._backend().interactions().useCustomRates() is True

    plain = build_model()
    assert plain._backend().interactions().useCustomRates() is False


def test_doubling_the_rates_halves_the_simulation_time():
    plain_time = run(build_model(), steps=200, seed=2013)
    doubled_time = run(build_model(rate_calculator=DoubleRateCalculator), steps=200, seed=2013)

    ratio = doubled_time / plain_time
    assert abs(ratio - 0.5) < 0.05, ratio
