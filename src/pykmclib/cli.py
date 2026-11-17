"""Command line interface: run a lattice KMC simulation from a Hydra configuration.

Usage::

    pykmclib model=diffusion1d                       # the packaged example
    pykmclib model=diffusion1d control.seed=7        # override any value
    pykmclib -m model=diffusion1d control.seed=1,2,3 # one run per value
    pykmclib model=script configuration_script=config.py interactions_script=processes.py
    pykmclib --config-dir ./conf model=my_model      # models from your own directory

The configuration is composed by `Hydra <https://hydra.cc>`_ from the YAML files
in ``pykmclib/conf``.  Every object of the simulation is described by its
constructor (``_target_``) and built with ``hydra.utils.instantiate``, so a
model is either declared entirely in YAML or loaded from KMCLib style Python
scripts through ``KMCConfigurationFromScript`` / ``KMCInteractionsFromScript``.

The trajectory and the results of the analysis plugins are written to the
Hydra output directory of the run (``outputs/<date>/<time>`` by default).

Hydra is an optional dependency: ``pip install "pykmclib[cli]"``.  Python 3.14
needs hydra-core 1.4 or newer; the extra selects a suitable version.
"""

from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["main", "run", "site_types"]

_MISSING_HYDRA = """\
The pykmclib command line interface needs hydra-core, which is not installed.
Install it with:

    pip install "pykmclib[cli]"
"""

_OLD_HYDRA = """\
hydra-core {version} does not work on Python 3.14 or newer; version 1.4 is needed.
Upgrade it with:

    pip install --upgrade "pykmclib[cli]"
"""


def site_types(default, count, overrides=None):
    """Build the ``types`` list of a configuration without spelling out every site.

    :param default: The type of every site that is not overridden.
    :param count: The total number of sites.
    :param overrides: A mapping from site index to type.
    :returns: A list with ``count`` type names.
    """
    count = int(count)
    types = [default] * count
    for index, name in (overrides or {}).items():
        index = int(index)
        if not 0 <= index < count:
            raise ValueError(f"site index {index} is outside the range 0..{count - 1}")
        types[index] = name
    return types


def _rate_calculator(spec):
    """Resolve ``model.rate_calculator``: a dotted class path or the name of a built-in calculator."""
    if isinstance(spec, str) and "." in spec:
        from hydra.utils import get_class

        return get_class(spec)
    return spec


def run(cfg, output_dir):
    """Build the model described by ``cfg``, run it, and write the results to ``output_dir``.

    :param cfg: The composed configuration (see ``pykmclib/conf/config.yaml``).
    :param output_dir: The directory for the trajectory and the analysis results.
    :returns: The ``KMCLatticeModel`` after the run.
    """
    from hydra.utils import instantiate

    from pykmclib import KMCLatticeModel

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # The front end checks its arguments against the builtin containers, so
    # the OmegaConf nodes are converted to plain lists and dicts.
    configuration = instantiate(cfg.model.configuration, _convert_="all")
    interactions = instantiate(cfg.model.interactions, _convert_="all")
    if cfg.model.get("rate_calculator") is not None:
        interactions.setRateCalculator(rate_calculator=_rate_calculator(cfg.model.rate_calculator))
    model = KMCLatticeModel(configuration=configuration, interactions=interactions)

    control_parameters = instantiate(cfg.control, _convert_="all")
    analysis = [instantiate(plugin, _convert_="all") for plugin in cfg.analysis]
    breakers = [instantiate(plugin, _convert_="all") for plugin in cfg.breakers]

    trajectory_filename = cfg.trajectory.filename
    if trajectory_filename is not None:
        trajectory_filename = str(output_dir / trajectory_filename)

    model.run(
        control_parameters=control_parameters,
        trajectory_filename=trajectory_filename,
        trajectory_type=cfg.trajectory.type,
        # The front end only accepts non-empty plugin lists.
        analysis=analysis or None,
        breakers=breakers or None,
    )

    for index, plugin in enumerate(analysis):
        if hasattr(plugin, "printResults"):
            with open(output_dir / f"analysis_{index}_{type(plugin).__name__}.txt", "w") as stream:
                plugin.printResults(stream)
    return model


def _version_tuple(version):
    """The leading ``(major, minor)`` of a version string."""
    parts = []
    for part in version.split(".")[:2]:
        digits = "".join(character for character in part if character.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def _hydra_problem(hydra_version, python_version):
    """Why this hydra-core cannot be used on this Python, or ``None`` if it can."""
    # The argument parser of hydra-core < 1.4 raises on Python 3.14.
    if tuple(python_version[:2]) >= (3, 14) and _version_tuple(hydra_version) < (1, 4):
        return _OLD_HYDRA.format(version=hydra_version)
    return None


def _task(cfg):
    from hydra.core.hydra_config import HydraConfig

    run(cfg, HydraConfig.get().runtime.output_dir)


def main():
    """Entry point of the ``pykmclib`` command."""
    try:
        import hydra
    except ImportError:
        sys.stderr.write(_MISSING_HYDRA)
        return 1

    problem = _hydra_problem(hydra.__version__, sys.version_info)
    if problem is not None:
        sys.stderr.write(problem)
        return 1

    hydra.main(version_base="1.3", config_path="conf", config_name="config")(_task)()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
