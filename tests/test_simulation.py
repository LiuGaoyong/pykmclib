"""End-to-end simulations on small lattices."""

from __future__ import annotations

import numpy as np
import pytest

from pykmclib import (
    KMCConfiguration,
    KMCControlParameters,
    KMCInteractions,
    KMCLattice,
    KMCLatticeModel,
    KMCProcess,
    KMCUnitCell,
)
from pykmclib.Exceptions.Error import Error


def build_model(types=None, possible_types=("A", "B"), processes=None):
    unit_cell = KMCUnitCell(cell_vectors=np.eye(3), basis_points=[[0.0, 0.0, 0.0]])
    lattice = KMCLattice(unit_cell=unit_cell, repetitions=(4, 4, 1), periodic=(True, True, False))
    configuration = KMCConfiguration(
        lattice=lattice,
        types=["B"] * 16 if types is None else types,
        possible_types=list(possible_types),
    )
    if processes is None:
        coordinates = [[0.0, 0.0, 0.0]]
        processes = [
            KMCProcess(coordinates, ["A"], ["B"], basis_sites=[0], rate_constant=4.0),
            KMCProcess(coordinates, ["B"], ["A"], basis_sites=[0], rate_constant=1.0),
        ]
    interactions = KMCInteractions(processes=processes, implicit_wildcards=True)
    return KMCLatticeModel(configuration=configuration, interactions=interactions)


def simulation_time(model):
    """The simulation clock, as exposed by the Python front end's timer."""
    return model._KMCLatticeModel__cpp_timer.simulationTime()


def test_ab_flip_simulation_runs():
    model = build_model()
    model.run(control_parameters=KMCControlParameters(number_of_steps=200, dump_interval=100, seed=2013))
    assert simulation_time(model) > 0.0


def test_simulation_is_deterministic_with_a_seed():
    first = build_model()
    first.run(control_parameters=KMCControlParameters(number_of_steps=50, dump_interval=50, seed=1234))

    second = build_model()
    second.run(control_parameters=KMCControlParameters(number_of_steps=50, dump_interval=50, seed=1234))

    assert simulation_time(first) == simulation_time(second)


def test_trajectory_file_is_written(tmp_path):
    model = build_model()
    trajectory = tmp_path / "traj.xyz"
    model.run(
        control_parameters=KMCControlParameters(number_of_steps=50, dump_interval=10, seed=17),
        trajectory_filename=str(trajectory),
        trajectory_type="xyz",
    )
    assert trajectory.exists()
    assert trajectory.read_text().strip()


def test_no_available_process_raises():
    coordinates = [[0.0, 0.0, 0.0]]
    only_a_to_b = [KMCProcess(coordinates, ["A"], ["B"], basis_sites=[0], rate_constant=1.0)]
    model = build_model(processes=only_a_to_b)
    with pytest.raises(Error):
        model.run(control_parameters=KMCControlParameters(number_of_steps=10, dump_interval=10, seed=5))
