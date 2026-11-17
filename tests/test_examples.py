"""The scripts and the Hydra configurations in ``examples/`` run.

Every test runs a very short simulation.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

# The examples are part of the repository, not of the installed package.
pytestmark = pytest.mark.skipif(
    not EXAMPLES.is_dir(), reason="the examples directory is not available"
)

# Example -> (arguments for a run of about a second, files it has to write).
SCRIPTS = {
    "diffusion_1d": (["--steps", "2000"], ["msd.data", "traj.xyz"]),
    "ising": (
        ["--steps", "2000", "--size", "10"],
        ["order.data", "spins_final.txt"],
    ),
    "diffusion_3d": (["--steps", "2000", "--size", "4"], ["msd.data"]),
    "langmuir": (["--steps", "2000", "--size", "6"], ["isotherm.data"]),
    "zgb": (["--steps", "1000", "--size", "8"], ["phase_diagram.data"]),
    "ruo2_co_oxidation": (
        ["--steps", "1000", "--cells", "4", "--p-co", "2", "7"],
        ["scan.data"],
    ),
}

# Example -> overrides that shrink the model of its Hydra configuration.
CONFIGURATIONS = {
    "ising": ["model.configuration.size=10", "control.analysis_interval=100"],
    "diffusion_3d": ["model.configuration.size=4"],
    "zgb": ["model.configuration.size=8"],
    "ruo2_co_oxidation": [
        "model.configuration.cells_across=4",
        "model.configuration.cells_along=4",
    ],
}


def run(arguments, cwd):
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )


def load(name):
    """Import ``examples/<name>/<name>.py`` as a module."""
    spec = importlib.util.spec_from_file_location(
        name, EXAMPLES / name / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_example_is_covered():
    directories = {
        path.name
        for path in EXAMPLES.iterdir()
        if (path / f"{path.name}.py").is_file()
    }
    assert directories == set(SCRIPTS)

    configurations = {
        path.stem for path in EXAMPLES.glob("*/conf/model/*.yaml")
    }
    assert configurations == set(CONFIGURATIONS) | {"langmuir"}


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_script_runs(name, tmp_path):
    arguments, outputs = SCRIPTS[name]
    script = EXAMPLES / name / f"{name}.py"

    result = run(
        [str(script), *arguments, "--output-dir", str(tmp_path)], cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr

    for output in outputs:
        assert (tmp_path / output).read_text().strip(), output


@pytest.mark.parametrize("name", sorted(CONFIGURATIONS))
def test_configuration_runs(name, tmp_path):
    # These configurations refer to the functions of the example, which Python
    # finds because `python -m` puts the working directory on the module search
    # path.
    result = run(
        [
            "-m",
            "pykmclib.cli",
            "--config-dir",
            "conf",
            f"model={name}",
            "control.number_of_steps=300",
            "control.dump_interval=300",
            f"hydra.run.dir={tmp_path.as_posix()}",
            *CONFIGURATIONS[name],
        ],
        cwd=EXAMPLES / name,
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.glob("analysis_0_*.txt"))


def test_yaml_only_configuration_runs_from_anywhere(tmp_path):
    result = run(
        [
            "-m",
            "pykmclib.cli",
            "--config-dir",
            str(EXAMPLES / "langmuir" / "conf"),
            "model=langmuir",
            "adsorption_rate=2.0",
            "control.number_of_steps=300",
            "control.dump_interval=300",
            f"hydra.run.dir={(tmp_path / 'run').as_posix()}",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "run" / "analysis_0_Composition.txt").read_text().strip()


def test_ruo2_rate_constants():
    model = load("ruo2_co_oxidation")

    # The chemical potential of oxygen tabulated by Reuter and Scheffler, per
    # atom at 1 atm.
    for temperature, tabulated in (
        (300.0, -0.27),
        (600.0, -0.61),
        (1000.0, -1.10),
    ):
        assert model.chemical_potential(
            "O2", temperature, 1.0
        ) / 2.0 == pytest.approx(tabulated, abs=0.006)

    table = model.process_table(temperature=600.0, p_co=7.0, p_o2=1.0)
    assert len(table) == 36
    assert len({row[0] for row in table}) == 22
    assert sorted(
        number for numbers in model.REACTIONS.values() for number in numbers
    ) == list(range(28, 36))

    rates = {row[0]: row[-1] for row in table}
    assert all(rate > 0.0 for rate in rates.values())
    # Half of k_B T / h times the Boltzmann factor of the 0.9 eV barrier.
    assert rates["reaction CO cus + O cus"] == pytest.approx(1.72e5, rel=0.01)
    # Desorption follows from adsorption by detailed balance, so the pressure
    # drops out of it.
    other = {
        row[0]: row[-1]
        for row in model.process_table(temperature=600.0, p_co=1.0, p_o2=1.0)
    }
    assert rates["CO desorption cus"] == pytest.approx(
        other["CO desorption cus"]
    )
    assert rates["CO adsorption cus"] == pytest.approx(
        7.0 * other["CO adsorption cus"]
    )
