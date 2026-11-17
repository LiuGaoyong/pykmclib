# pykmclib

**pykmclib** is a Python re-release and further development of
[KMCLib](https://github.com/leetmaa/KMCLib), a framework for lattice kinetic Monte Carlo (lattice kMC)
simulations. The C++ backend is KMCLib's original implementation, bound with **pybind11** and built
with **scikit-build-core + CMake**, so it can be installed directly from PyPI / conda-forge.

> Status: `0.0.1` (alpha). The Python layer keeps the same API as upstream KMCLib. Of upstream's
> own 190 unit tests, 187 pass and 3 are known failures that depend on the platform, the numpy
> version or the machine load (see [docs/porting-notes.md](docs/porting-notes.md)); the 8
> end-to-end functional tests pass.

## Installation

pykmclib has **not been released to PyPI or conda-forge yet**. Until the first release, install it
from the repository; this requires CMake ≥ 3.21 and a C++17 compiler (pybind11 and
scikit-build-core are installed automatically as build-time dependencies):

```bash
pip install git+https://github.com/LiuGaoyong/pykmclib.git
```

Once a release is published, the usual commands apply:

```bash
pip install pykmclib
# or
conda install -c conda-forge pykmclib

pip install --no-binary pykmclib pykmclib   # uses the sdist (self-contained, includes the C++ sources)
```

Wheels are built for CPython 3.10–3.14 on:

| Platform | Architectures | Notes |
| --- | --- | --- |
| Linux | x86_64, aarch64 (arm64) | both `manylinux2014` (glibc ≥ 2.17) and `manylinux_2_28` (glibc ≥ 2.28); pip picks the right one. No musllinux wheels |
| macOS | x86_64 (10.15+), arm64 (11.0+) | |
| Windows | x86_64 | |

## Quick start

A 1D diffusion model: a periodic chain of 10 lattice sites, with a single B atom in the middle
performing a random walk in a sea of A atoms.

```python
import numpy as np
from pykmclib import (
    KMCUnitCell,
    KMCLattice,
    KMCConfiguration,
    KMCProcess,
    KMCInteractions,
    KMCLatticeModel,
    KMCControlParameters,
    OnTheFlyMSD,
)

unit_cell = KMCUnitCell(
    cell_vectors=np.array([[5.2, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]), basis_points=[[0.0, 0.0, 0.0]]
)
lattice = KMCLattice(unit_cell=unit_cell, repetitions=(10, 1, 1), periodic=(True, False, False))

types = ["A"] * 10
types[5] = "B"
configuration = KMCConfiguration(lattice=lattice, types=types, possible_types=["A", "B"])

left = KMCProcess(
    [[0.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
    elements_before=["B", "A"],
    elements_after=["A", "B"],
    basis_sites=[0],
    rate_constant=1.5,
)
right = KMCProcess(
    [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
    elements_before=["B", "A"],
    elements_after=["A", "B"],
    basis_sites=[0],
    rate_constant=1.5,
)
interactions = KMCInteractions(processes=[left, right], implicit_wildcards=True)

model = KMCLatticeModel(configuration=configuration, interactions=interactions)
msd = OnTheFlyMSD(history_steps=200, n_bins=100, t_max=2500.0, track_type="B")

model.run(
    KMCControlParameters(number_of_steps=200_000, dump_interval=50_000, seed=1234),
    trajectory_filename="traj.xyz",
    trajectory_type="xyz",
    analysis=[msd],
)
```

Concepts such as `sites`, `rates` and `interactions` are the same as in the upstream manual
(<http://leetmaa.github.io/KMCLib/manual-v1.1/>). To use the upstream manual and examples, just
change `from KMCLib import ...` to `from pykmclib import ...`.

## Command line

The `pykmclib` command runs a simulation from a [Hydra](https://hydra.cc) configuration. Hydra is
an optional dependency:

```bash
pip install "pykmclib[cli]"
```

```bash
pykmclib model=diffusion1d                         # the packaged example (the model above)
pykmclib model=diffusion1d control.seed=7 control.number_of_steps=100000
pykmclib -m model=diffusion1d control.seed=1,2,3   # one run per seed
```

Each run gets its own output directory (`outputs/<date>/<time>`, or `multirun/...` with `-m`)
holding the trajectory, one `analysis_<n>_<Plugin>.txt` per analysis plugin, the log, and the
fully resolved configuration under `.hydra/`.

A model can be defined in two ways:

- **In YAML.** Every object is described by its constructor (`_target_`) and its arguments; see
  [`src/pykmclib/conf/model/diffusion1d.yaml`](src/pykmclib/conf/model/diffusion1d.yaml). Put
  your own files in `<dir>/model/<name>.yaml` and run
  `pykmclib --config-dir <dir> model=<name>`. `pykmclib.cli.site_types` builds a long `types`
  list from a default type and a few overrides.
- **From Python scripts** in the upstream KMCLib style, which suits large lattices:

  ```bash
  pykmclib model=script configuration_script=config.py interactions_script=processes.py
  ```

  The first `KMCConfiguration` / `KMCInteractions` object found in each script is used.

The run settings live under `control` (the arguments of `KMCControlParameters`), `trajectory`
(`filename`, `type`), `analysis` and `breakers` (lists of plugins, each with a `_target_`);
`model.rate_calculator` takes a dotted path to a `KMCRateCalculatorPlugin` class or the name of a
built-in C++ calculator. `pykmclib --cfg job model=diffusion1d` prints the composed configuration
without running it.

On Python 3.14 the command needs hydra-core 1.4, which is currently a release candidate; the
`cli` extra selects it automatically.

## Changes relative to upstream

While keeping the API compatible, the following has been done so far:

| Change | Description |
| --- | --- |
| Packaging and build | scikit-build-core + CMake 3.21+, C++17; `mpiflag.h` and md5 are generated/extracted in the build directory and no longer written back into the source tree; upstream's `-Werror` and `cmake_force_cxx_compiler` (incompatible with CMake 4) are dropped |
| Binding layer | SWIG → **pybind11**, working on all three platforms (including Windows); callbacks (custom rates written in Python) are implemented with trampolines |
| Namespace | `KMCLib` → `pykmclib` (the upstream Python layer uses absolute imports, which a script rewrites mechanically) |
| Dependencies | The only runtime dependency is `numpy`; pybind11/cmake are needed only at build time; `hydra-core` is optional (the `cli` extra) |
| Command line | New `pykmclib` command driven by Hydra configurations (not part of upstream) |
| Import side effects | The banner printed at import time is removed; MPI is still initialized/finalized exactly once |
| Typing | The package ships `py.typed` and a generated stub for the compiled backend (`Backend/_backend.pyi`); the upstream front end itself is not annotated |

## Repository layout

```
CMakeLists.txt         PEP 517 entry point
cxx/                   Build adaptation layer: CMake logic + pybind11 bindings (bindings/)
third_party/KMCLib/    git subtree snapshot of upstream KMCLib (never edited)
src/pykmclib/          Python package (renamed upstream front end + Backend facade,
                       cli.py and conf/ for the command line)
tests/                 Tests for this repository
scripts/               gen_python_layer.py / gen_stubs.py / run_upstream_tests.py / upstream_info.py
docs/                  upstream-notes.md (snapshot and syncing), porting-notes.md (binding layer),
                       build-and-release.md (build and release)
conda/                 Draft conda-forge recipe
```

**Why git subtree rather than submodule**: both the PyPI sdist and conda-forge require
self-contained sources, and scikit-build-core does not initialize submodules when building an
sdist; on top of that, the upstream build system has to be reworked. A subtree keeps the sources in
the tree while still recording the upstream commit via `git-subtree-split`. See
[docs/upstream-notes.md](docs/upstream-notes.md) for the full comparison.

## Development

```bash
uv sync                                          # create the environment + compile the C++ extension
uv run pytest -q                                 # tests for this repository
uv run python scripts/run_upstream_tests.py --units      # upstream's 190 unit tests
uv run python scripts/run_upstream_tests.py --functests  # upstream end-to-end cases
uv build                                         # wheel + sdist
uv run python scripts/upstream_info.py           # the currently pinned upstream commit
uv run python scripts/gen_stubs.py               # refresh the backend type stub after changing bindings
uv run ruff check . && uv run ruff format --check .
```

See [docs/build-and-release.md](docs/build-and-release.md) for details.

## Citation

When publishing research that uses this software, please cite the two KMCLib papers:

> Mikael Leetmaa and Natalia V. Skorodumova,
> *KMCLib: A general framework for lattice kinetic Monte Carlo (KMC) simulations*,
> Comput. Phys. Commun. **185** (2014) 2340. DOI: [10.1016/j.cpc.2014.04.017](https://doi.org/10.1016/j.cpc.2014.04.017)

> Mikael Leetmaa and Natalia V. Skorodumova,
> *KMCLib 1.1: Extended random number support and technical updates*,
> Comput. Phys. Commun. (2015). DOI: [10.1016/j.cpc.2015.06.016](https://doi.org/10.1016/j.cpc.2015.06.016)

For the MSD algorithm, please additionally cite: *Mean square displacements with error estimates
from non-equidistant time-step kinetic Monte Carlo simulations*, Comput. Phys. Commun. (2015),
DOI: [10.1016/j.cpc.2015.02.006](https://doi.org/10.1016/j.cpc.2015.02.006)

## License

**GPL-3.0-or-later**. pykmclib links against and distributes KMCLib (Copyright © 2012–2016 Mikael
Leetmaa, GPL-3.0-or-later), so as a derivative work it is covered by GPLv3 as a whole. The `LICENSE`
file in the repository root is the full GPLv3 text; the original upstream license is in
`third_party/KMCLib/LICENSE.txt`. The MD5 implementation is public domain.
