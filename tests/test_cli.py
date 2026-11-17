"""The ``pykmclib`` command (Hydra based, optional dependency)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys

import pytest

from pykmclib.cli import site_types

needs_hydra = pytest.mark.skipif(importlib.util.find_spec("hydra") is None, reason="hydra-core is not installed")

ENTRY_POINT = "import sys; from pykmclib.cli import main; sys.exit(main())"

CONFIGURATION_SCRIPT = """\
from pykmclib import *

unit_cell = KMCUnitCell(cell_vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                        basis_points=[[0.0, 0.0, 0.0]])
lattice = KMCLattice(unit_cell=unit_cell, repetitions=(4, 4, 1), periodic=(True, True, False))
configuration = KMCConfiguration(lattice=lattice, types=["B"] * 16, possible_types=["A", "B"])
"""

INTERACTIONS_SCRIPT = """\
from pykmclib import *

processes = [
    KMCProcess([[0.0, 0.0, 0.0]], ["A"], ["B"], basis_sites=[0], rate_constant=4.0),
    KMCProcess([[0.0, 0.0, 0.0]], ["B"], ["A"], basis_sites=[0], rate_constant=1.0),
]
interactions = KMCInteractions(processes=processes, implicit_wildcards=True)
"""


def pykmclib(*args, cwd, prelude=""):
    """Run the console script entry point in a fresh interpreter."""
    return subprocess.run(
        [sys.executable, "-c", prelude + ENTRY_POINT, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )


def run_directories(root):
    """The Hydra output directories below ``root`` (one per run)."""
    return sorted(path.parent for path in root.rglob(".hydra"))


def test_site_types_fills_and_overrides():
    assert site_types("A", 4) == ["A", "A", "A", "A"]
    assert site_types("A", 4, {1: "B", "3": "C"}) == ["A", "B", "A", "C"]
    with pytest.raises(ValueError):
        site_types("A", 4, {4: "B"})


def test_missing_hydra_is_reported(tmp_path):
    result = pykmclib("model=diffusion1d", cwd=tmp_path, prelude="import sys; sys.modules['hydra'] = None; ")
    assert result.returncode == 1
    assert "pykmclib[cli]" in result.stderr


def test_old_hydra_is_rejected_on_python_3_14(tmp_path):
    prelude = (
        "import sys, types; "
        "sys.modules['hydra'] = types.SimpleNamespace(__version__='1.3.8'); "
        "sys.version_info = (3, 14, 0, 'final', 0); "
    )
    result = pykmclib("model=diffusion1d", cwd=tmp_path, prelude=prelude)
    assert result.returncode == 1
    assert "1.3.8" in result.stderr


@needs_hydra
def test_packaged_example_runs(tmp_path):
    result = pykmclib(
        "model=diffusion1d", "control.number_of_steps=200", "control.dump_interval=100", "control.seed=3", cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr

    (output,) = run_directories(tmp_path)
    assert (output / "traj.xyz").read_text().strip()
    assert "MSD_x" in (output / "analysis_0_OnTheFlyMSD.txt").read_text()


@needs_hydra
def test_model_from_scripts(tmp_path):
    (tmp_path / "config.py").write_text(CONFIGURATION_SCRIPT)
    (tmp_path / "processes.py").write_text(INTERACTIONS_SCRIPT)

    result = pykmclib(
        "model=script",
        "configuration_script=config.py",
        "interactions_script=processes.py",
        "control.number_of_steps=50",
        "control.dump_interval=10",
        "control.seed=5",
        "trajectory.filename=traj.py",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr

    (output,) = run_directories(tmp_path)
    assert (output / "traj.py").read_text().strip()


@needs_hydra
def test_multirun_creates_one_directory_per_value(tmp_path):
    result = pykmclib(
        "--multirun",
        "model=diffusion1d",
        "control.number_of_steps=50",
        "control.dump_interval=50",
        "control.seed=1,2",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert len(run_directories(tmp_path)) == 2


@needs_hydra
def test_a_model_is_required(tmp_path):
    result = pykmclib(cwd=tmp_path)
    assert result.returncode != 0
    assert "model" in result.stderr
