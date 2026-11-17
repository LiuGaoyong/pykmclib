# pykmclib examples

Six lattice kinetic Monte Carlo models, each in its own directory with a script that runs as it
is, a README with the expected results, and (except for the first) a configuration for the
`pykmclib` command. The first three are the examples of the
[KMCLib manual](http://leetmaa.github.io/KMCLib/manual-v1.1/); the others are surface models
from the literature with results that can be checked.

| Example | Model | Checked against | Run time |
| ------- | ----- | --------------- | -------- |
| [diffusion_1d](diffusion_1d/) | random walk of one particle on a chain | the exact mean square displacement | 5 s |
| [ising](ising/) | 2D Ising spins ordering below the critical temperature | the exact magnetisation and energy (Yang, Onsager) | 10 s |
| [diffusion_3d](diffusion_3d/) | oxygen vacancies in a fluorite structured oxide | confined, free and driven diffusion along x, y and z | 30 s |
| [langmuir](langmuir/) | adsorption and desorption on a surface | the Langmuir isotherm | 5 s |
| [zgb](zgb/) | Ziff–Gulari–Barshad model of CO oxidation | the two kinetic phase transitions (Ziff et al. 1986) | 30 s |
| [ruo2_co_oxidation](ruo2_co_oxidation/) | CO oxidation at RuO₂(110), 22 kinds of processes from first-principles energies | turnover frequency and site occupations (Reuter and Scheffler 2006) | 1 min |

Which example shows which part of pykmclib:

| Feature | Examples |
| ------- | -------- |
| lattice, configuration, processes, running a model | all, simplest in diffusion_1d and langmuir |
| several sites per unit cell, `basis_sites` | diffusion_3d, ruo2_co_oxidation |
| processes on pairs of sites | diffusion_1d, diffusion_3d, zgb, ruo2_co_oxidation |
| `OnTheFlyMSD` | diffusion_1d, diffusion_3d |
| `Composition` | zgb, and the configuration of langmuir |
| custom rates: `KMCRateCalculatorPlugin`, built-in C++ calculators | ising |
| custom analysis: `KMCAnalysisPlugin` | ising, langmuir, zgb, ruo2_co_oxidation |
| stopping a run: `KMCBreakerPlugin` | zgb |
| continuing a run | zgb, ruo2_co_oxidation |
| trajectory output | diffusion_1d |
| time-weighted averages | langmuir, ruo2_co_oxidation |

## Running the scripts

The scripts need pykmclib and numpy, nothing else:

```bash
python examples/langmuir/langmuir.py
python examples/langmuir/langmuir.py --help
```

Every script takes `--steps`, `--seed` and `--output-dir` (default: `output/` next to the
script), and prints a comparison with the expected result. `--plot` also writes the figure
shown in the README of the example; it needs matplotlib, which is what the `examples` extra of
pykmclib installs:

```bash
pip install matplotlib                # or, in a checkout of the repository: uv sync --extra examples
python examples/langmuir/langmuir.py --plot
```

Without matplotlib `--plot` prints a note and the script finishes normally.

## Running the configurations

The models also run through the `pykmclib` command, which adds overrides and parameter sweeps
from the command line:

```bash
# Declared entirely in YAML: runs from anywhere.
pykmclib --config-dir examples/langmuir/conf model=langmuir adsorption_rate=4.0

# Built by the functions of the example script: run from the directory of the script.
cd examples/zgb
python -m pykmclib.cli -m --config-dir conf model=zgb model.interactions.y=0.35,0.45,0.55
```

The configurations of ising, diffusion_3d, zgb and ruo2_co_oxidation name functions and classes
of their script, such as `zgb.build_interactions`, which Python has to be able to import.
`python -m pykmclib.cli` puts the working directory on the module search path; with the
`pykmclib` script set `PYTHONPATH=.` instead. Each run writes its results to
`outputs/<date>/<time>` (`multirun/...` for sweeps) below the working directory.

## Writing your own

All scripts have the same layout, which is a reasonable starting point for a new model:

```python
def build_configuration(...):   # the lattice and what is on it
def build_interactions(...):    # the processes and their rate constants
def main(argv=None):            # run, analyse, compare
```

`build_configuration` and `build_interactions` are what the Hydra configurations call, so a
model written this way runs from a script and from the command line alike.

## References

- M. Leetmaa and N. V. Skorodumova, Comput. Phys. Commun. 185 (2014) 2340.
  DOI: [10.1016/j.cpc.2014.04.017](https://doi.org/10.1016/j.cpc.2014.04.017)
- A. B. Bortz, M. H. Kalos and J. L. Lebowitz, J. Comput. Phys. 17 (1975) 10.
  DOI: [10.1016/0021-9991(75)90060-1](https://doi.org/10.1016/0021-9991(75)90060-1)
- I. Langmuir, J. Am. Chem. Soc. 40 (1918) 1361.
  DOI: [10.1021/ja02242a004](https://doi.org/10.1021/ja02242a004)
- R. M. Ziff, E. Gulari and Y. Barshad, Phys. Rev. Lett. 56 (1986) 2553.
  DOI: [10.1103/PhysRevLett.56.2553](https://doi.org/10.1103/PhysRevLett.56.2553)
- A. P. J. Jansen, *An Introduction to Kinetic Monte Carlo Simulations of Surface Reactions*,
  Springer (2012). DOI: [10.1007/978-3-642-29488-4](https://doi.org/10.1007/978-3-642-29488-4)
- K. Reuter and M. Scheffler, Phys. Rev. B 73 (2006) 045433.
  DOI: [10.1103/PhysRevB.73.045433](https://doi.org/10.1103/PhysRevB.73.045433)
- M. Andersen, C. Panosetti and K. Reuter, Front. Chem. 7 (2019) 202.
  DOI: [10.3389/fchem.2019.00202](https://doi.org/10.3389/fchem.2019.00202)

The README of each example lists the references for its model in full.
