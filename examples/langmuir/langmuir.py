"""Langmuir adsorption: the coverage of a surface in equilibrium with a gas.

The simplest surface model with an exact answer.  Every site of a square
lattice is empty ("E") or holds one adsorbed molecule ("A").  Molecules adsorb
on empty sites with the rate constant ``k_ads`` (proportional to the gas
pressure) and desorb with the rate constant ``k_des``; they do not interact.
In equilibrium the fraction of occupied sites follows the Langmuir isotherm

    coverage = K / (1 + K),    K = k_ads / k_des

The script runs the model for a series of values of ``K`` and compares the
measured coverage to this formula.

The coverage is measured by a small analysis plugin that averages over *time*.
A kMC step takes a different amount of time in every state (short when many
processes are available), so a plain average over the steps would be biased.

Run it with::

    python langmuir.py            # about 5 s
    python langmuir.py --plot     # also writes langmuir.png (needs matplotlib)

Reference: I. Langmuir, J. Am. Chem. Soc. 40 (1918) 1361.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path

import numpy as np

from pykmclib import (
    KMCAnalysisPlugin,
    KMCConfiguration,
    KMCControlParameters,
    KMCInteractions,
    KMCLattice,
    KMCLatticeModel,
    KMCProcess,
    KMCUnitCell,
)

# The values of K = k_ads / k_des of the isotherm.
RATIOS = (0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 10.0)


def build_configuration(size=20):
    """An empty ``size`` x ``size`` square lattice."""
    unit_cell = KMCUnitCell(
        cell_vectors=np.eye(3), basis_points=[[0.0, 0.0, 0.0]]
    )
    lattice = KMCLattice(
        unit_cell=unit_cell,
        repetitions=(size, size, 1),
        periodic=(True, True, False),
    )
    return KMCConfiguration(
        lattice=lattice, types=["E"] * (size * size), possible_types=["E", "A"]
    )


def build_interactions(adsorption_rate=1.0, desorption_rate=1.0):
    """Two processes on a single site each: adsorption and desorption."""
    site = [[0.0, 0.0, 0.0]]
    processes = [
        KMCProcess(
            site,
            elements_before=["E"],
            elements_after=["A"],
            basis_sites=[0],
            rate_constant=float(adsorption_rate),
        ),
        KMCProcess(
            site,
            elements_before=["A"],
            elements_after=["E"],
            basis_sites=[0],
            rate_constant=float(desorption_rate),
        ),
    ]
    return KMCInteractions(processes=processes, implicit_wildcards=True)


class TimeAveragedCoverage(KMCAnalysisPlugin):
    """The fraction of the sites holding ``species``, averaged over time.

    The averages are collected in blocks of the duration ``block_length``.
    """

    def __init__(self, species="A", block_length=1.0):
        self.species = species
        self.block_length = float(block_length)
        self.durations = []  # the length of every completed block ...
        self.averages = []  # ... and the average coverage during it

    def setup(self, step, time, configuration):
        # Called once, before the first step.
        self._type = configuration.possibleTypes()[self.species]
        self._sites = len(configuration.sites())
        self._count = configuration.particlesPerType()[self._type]
        self._time = self._block_start = time
        self._integral = 0.0

    def registerStep(self, step, time, configuration):
        # Called after every step. The state seen at the previous call lasted
        # until now.
        self._integral += self._count * (time - self._time)
        self._count = configuration.particlesPerType()[self._type]
        self._time = time

        if time - self._block_start >= self.block_length:
            duration = time - self._block_start
            self.durations.append(duration)
            self.averages.append(self._integral / duration / self._sites)
            self._block_start = time
            self._integral = 0.0

    def result(self, skip=1):
        """The average over all blocks but the first ``skip``, and its error."""
        durations = np.array(self.durations[skip:])
        averages = np.array(self.averages[skip:])
        if len(averages) < 2:
            return float("nan"), float("nan")
        mean = np.sum(durations * averages) / np.sum(durations)
        return float(mean), float(averages.std(ddof=1) / np.sqrt(len(averages)))

    def printResults(self, stream=sys.stdout):
        stream.write(f"{'block length':>15s} {'coverage':>15s}\n")
        for duration, average in zip(
            self.durations, self.averages, strict=True
        ):
            stream.write(f"{duration:15.5e} {average:15.6f}\n")


def measure_coverage(ratio, size=20, steps=100_000, seed=1):
    """Run the model at ``K = ratio``.

    :returns: the coverage in equilibrium and its standard error.
    """
    adsorption_rate, desorption_rate = float(ratio), 1.0
    configuration = build_configuration(size)
    model = KMCLatticeModel(
        configuration=configuration,
        interactions=build_interactions(adsorption_rate, desorption_rate),
    )

    # The coverage relaxes towards equilibrium as exp(-(k_ads + k_des) * t).
    # Blocks of ten relaxation times are nearly independent of each other, so
    # their scatter gives the error of the mean; the first block starts from
    # the empty surface and is dropped.
    relaxation_time = 1.0 / (adsorption_rate + desorption_rate)
    coverage = TimeAveragedCoverage(
        species="A", block_length=10.0 * relaxation_time
    )

    # analysis_interval=1 (the default): the analysis has to see every step.
    control_parameters = KMCControlParameters(
        number_of_steps=steps,
        dump_interval=steps,
        analysis_interval=1,
        seed=seed,
    )
    # Silence the progress messages of the library: this run is one of a series.
    with contextlib.redirect_stdout(io.StringIO()):
        model.run(control_parameters=control_parameters, analysis=[coverage])
    return coverage.result(skip=1)


def plot(results, filename):
    try:
        import matplotlib
    except ImportError:
        print("matplotlib is not installed, no figure was written.")
        return
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ratios = np.array([row[0] for row in results])
    figure, axes = plt.subplots(figsize=(5.0, 3.6), dpi=110)
    curve = np.logspace(
        np.log10(ratios.min() / 2.0), np.log10(ratios.max() * 2.0), 200
    )
    axes.plot(
        curve,
        curve / (1.0 + curve),
        "k-",
        lw=1.0,
        label="Langmuir isotherm, K / (1 + K)",
    )
    axes.errorbar(
        ratios,
        [row[1] for row in results],
        yerr=[row[2] for row in results],
        fmt="o",
        ms=5,
        label="kMC",
    )
    axes.set_xscale("log")
    axes.set_xlabel(r"$K = k_\mathrm{ads} / k_\mathrm{des}$")
    axes.set_ylabel("coverage")
    axes.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(filename)
    plt.close(figure)
    print(f"Figure written to {filename}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--size",
        type=int,
        default=20,
        help="the lattice has size x size sites (default: %(default)s)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=100_000,
        help="number of kMC steps per run (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2014,
        help="seed of the random number generator",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="write a figure of the isotherm (needs matplotlib)",
    )
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("       K    coverage (kMC)      Langmuir   deviation")
    results = []
    for index, ratio in enumerate(RATIOS):
        coverage, error = measure_coverage(
            ratio, size=args.size, steps=args.steps, seed=args.seed + index
        )
        exact = ratio / (1.0 + ratio)
        results.append((ratio, coverage, error, exact))
        print(
            f"  {ratio:6.2f}   {coverage:.4f} +/- {error:.4f}     {exact:.4f}"
            f"   {coverage - exact:+.4f}"
        )

    header = (
        "K = k_ads/k_des, coverage (kMC), standard error, coverage (Langmuir)"
    )
    np.savetxt(
        args.output_dir / "isotherm.data",
        np.array(results),
        fmt="%12.6f",
        header=header,
    )
    print(f"Results written to {args.output_dir}")

    if args.plot:
        plot(results, args.output_dir / "langmuir.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
