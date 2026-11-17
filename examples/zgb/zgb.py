"""The Ziff-Gulari-Barshad (ZGB) model of CO oxidation on a catalyst surface.

A classic of non-equilibrium statistical physics with only three kinds of
processes on a square lattice:

* CO adsorbs on an empty site;
* O2 adsorbs on two neighbouring empty sites and dissociates;
* adsorbed CO and O on neighbouring sites react to CO2, which leaves at once.

The gas contains the fraction ``y`` of CO and ``1 - y`` of O2, and nothing ever
desorbs unreacted.  Depending on ``y`` the surface ends up in one of three
states: covered by oxygen ("O poisoned", y < y1 = 0.39), reactive (y1 < y < y2),
or covered by CO ("CO poisoned", y > y2 = 0.526).  The first transition is
continuous, the second one is abrupt.

The script scans ``y`` and reports the coverages and the CO2 production rate.
It shows how to combine a built-in analysis (``Composition``), a custom
analysis (counting the events of some processes) and a *breaker* that stops a
run as soon as the surface is poisoned.

Run it with::

    python zgb.py            # about 30 s
    python zgb.py --plot     # also writes a figure (needs matplotlib)

References:
  R. M. Ziff, E. Gulari and Y. Barshad, Phys. Rev. Lett. 56 (1986) 2553.
  A. P. J. Jansen, An Introduction to Kinetic Monte Carlo Simulations of
  Surface Reactions, Springer (2012), section 7.4.3.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path

import numpy as np

from pykmclib import (
    Composition,
    KMCAnalysisPlugin,
    KMCBreakerPlugin,
    KMCConfiguration,
    KMCControlParameters,
    KMCInteractions,
    KMCLattice,
    KMCLatticeModel,
    KMCProcess,
    KMCUnitCell,
)

# The transition points of the model, from large simulations in the literature.
Y1, Y2 = 0.3874, 0.5256

# The values of y of the scan.
# fmt: off
Y_VALUES = (
    0.30, 0.34, 0.37, 0.39, 0.41, 0.44, 0.47,
    0.50, 0.52, 0.53, 0.54, 0.56, 0.60,
)
# fmt: on

# Process numbers: the positions in the list built by `build_interactions`.
REACTION_PROCESSES = (3, 4, 5, 6)


def build_configuration(size=40):
    """An empty ``size`` x ``size`` square lattice.

    A site is empty ("E") or holds "CO" or "O".
    """
    unit_cell = KMCUnitCell(
        cell_vectors=np.eye(3), basis_points=[[0.0, 0.0, 0.0]]
    )
    lattice = KMCLattice(
        unit_cell=unit_cell,
        repetitions=(size, size, 1),
        periodic=(True, True, False),
    )
    return KMCConfiguration(
        lattice=lattice,
        types=["E"] * (size * size),
        possible_types=["E", "CO", "O"],
    )


def build_interactions(y=0.45, reaction_rate=1000.0):
    """The seven processes of the model for the CO fraction ``y`` of the gas.

    Time is measured in units of the time in which, on average, one molecule
    hits each site. The reaction of the original model is instantaneous; here it
    is merely much faster (``reaction_rate``) than adsorption.
    """
    site = [0.0, 0.0, 0.0]
    right, left = [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]
    up, down = [0.0, 1.0, 0.0], [0.0, -1.0, 0.0]

    # 0: CO adsorption.
    processes = [
        KMCProcess(
            [site], ["E"], ["CO"], basis_sites=[0], rate_constant=float(y)
        )
    ]

    # 1, 2: O2 adsorption on a pair of empty sites. A molecule that hits a site
    # (rate 1 - y) picks one of the four neighbours, and a pair can be hit on
    # either of its two sites, which makes (1 - y) / 2 per pair. Every pair is
    # listed once: with its right or its upper site.
    for neighbour in (right, up):
        processes.append(
            KMCProcess(
                [site, neighbour],
                ["E", "E"],
                ["O", "O"],
                basis_sites=[0],
                rate_constant=(1.0 - y) / 2.0,
            )
        )

    # 3 - 6: reaction of a CO with an O on any of the four neighbouring sites.
    for neighbour in (right, left, up, down):
        processes.append(
            KMCProcess(
                [site, neighbour],
                ["CO", "O"],
                ["E", "E"],
                basis_sites=[0],
                rate_constant=float(reaction_rate),
            )
        )
    return KMCInteractions(processes=processes, implicit_wildcards=True)


class EventCounter(KMCAnalysisPlugin):
    """Count how often one of the given processes happens.

    :param processes: the numbers of the processes to count.
    :param skip_steps: leave out this many steps at the start of the run.
    """

    def __init__(self, processes=REACTION_PROCESSES, skip_steps=0):
        self.processes = frozenset(processes)
        self.skip_steps = int(skip_steps)
        self.count = 0
        self.start_time = self.end_time = 0.0
        self.sites = 1

    def setup(self, step, time, configuration):
        self.start_time = self.end_time = time
        self.sites = len(configuration.sites())

    def registerStep(self, step, time, configuration):
        if step <= self.skip_steps:
            self.start_time = self.end_time = time
            return
        # The configuration remembers which process was executed in the latest
        # step.
        if configuration.latestEventProcess() in self.processes:
            self.count += 1
        self.end_time = time

    def rate(self):
        """Events per site and unit of time."""
        elapsed = self.end_time - self.start_time
        return self.count / (self.sites * elapsed) if elapsed > 0.0 else 0.0

    def printResults(self, stream=sys.stdout):
        elapsed = self.end_time - self.start_time
        stream.write(f"{self.count} events in {elapsed:.6e} time units\n")
        stream.write(f"rate per site: {self.rate():.6e}\n")


class Poisoned(KMCBreakerPlugin):
    """Stop the run when the surface is completely covered by one species.

    Nothing can happen any more in such a state, and the model would raise an
    error on the next step. ``evaluate`` is called every ``interval()`` steps;
    returning True ends the run.
    """

    def __init__(self):
        self.species = None  # set to "CO" or "O" when the surface is poisoned

    def evaluate(self, step, time, configuration):
        counts = dict(
            zip(
                configuration.possibleTypes(),
                configuration.particlesPerType(),
                strict=True,
            )
        )
        if counts["E"] == 0 and (counts["CO"] == 0 or counts["O"] == 0):
            self.species = "CO" if counts["O"] == 0 else "O"
            return True
        return False

    def interval(self):
        return 1


def simulate(y, size=40, steps=100_000, seed=1):
    """Run the model at the CO fraction ``y``.

    :returns: a dict with the final ``state`` ("reactive", "O poisoned" or
              "CO poisoned"), the coverages ``co`` and ``o`` and the CO2
              production ``rate`` per site and unit of time.
    """
    configuration = build_configuration(size)
    model = KMCLatticeModel(
        configuration=configuration, interactions=build_interactions(y)
    )
    sites = size * size
    poisoned = Poisoned()

    def run(analysis, seed):
        control_parameters = KMCControlParameters(
            number_of_steps=steps, dump_interval=steps, seed=seed
        )
        # Silence the progress messages of the library: this run is one of a
        # series.
        with contextlib.redirect_stdout(io.StringIO()):
            model.run(
                control_parameters=control_parameters,
                analysis=analysis,
                breakers=[poisoned],
            )

    # First let the surface reach its steady state. A model can be run several
    # times; each run continues from the configuration and the time at which
    # the previous one stopped.
    run(analysis=None, seed=seed)

    # Then measure. Composition averages the number of particles of each type
    # over blocks of time; its block averages run over the steps, which is
    # accurate enough here (the langmuir example shows an average weighted by
    # time).
    composition = Composition(time_interval=5.0)
    reactions = EventCounter(REACTION_PROCESSES)
    if poisoned.species is None:
        run(analysis=[composition, reactions], seed=seed + 1)

    if poisoned.species is not None:
        return {
            "state": f"{poisoned.species} poisoned",
            "co": float(poisoned.species == "CO"),
            "o": float(poisoned.species == "O"),
            "rate": 0.0,
        }

    # One row per block, one column per type in the order of `possible_types`
    # after the wildcard "*".
    blocks = np.array(composition.data())
    if len(blocks) == 0:
        blocks = np.array([configuration.particlesPerType()], dtype=float)
    return {
        "state": "reactive",
        "co": float(blocks[:, 2].mean() / sites),
        "o": float(blocks[:, 3].mean() / sites),
        "rate": reactions.rate(),
    }


def plot(results, filename):
    try:
        import matplotlib
    except ImportError:
        print("matplotlib is not installed, no figure was written.")
        return
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    y_values = [row["y"] for row in results]
    figure, axes = plt.subplots(figsize=(5.0, 3.6), dpi=110)
    axes.plot(
        y_values, [row["o"] for row in results], "o-", ms=4, label="O coverage"
    )
    axes.plot(
        y_values,
        [row["co"] for row in results],
        "s-",
        ms=4,
        label="CO coverage",
    )
    axes.plot(
        y_values,
        [row["rate"] for row in results],
        "^-",
        ms=4,
        label=r"CO$_2$ production rate",
    )
    for transition in (Y1, Y2):
        axes.axvline(transition, color="k", ls="--", lw=0.8)
    axes.plot([], [], "k--", lw=0.8, label=r"$y_1$, $y_2$ (literature)")
    axes.set_xlabel("fraction of CO in the gas, y")
    axes.set_ylabel("coverage, rate per site")
    axes.legend(frameon=False, fontsize=8, loc="center left")
    figure.tight_layout()
    figure.savefig(filename)
    plt.close(figure)
    print(f"Figure written to {filename}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--size",
        type=int,
        default=40,
        help="the lattice has size x size sites (default: %(default)s)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=100_000,
        help="number of kMC steps to reach the steady state, and again to "
        "measure (default: %(default)s)",
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
        help="write a figure of the phase diagram (needs matplotlib)",
    )
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("      y   CO coverage    O coverage    CO2 rate   state")
    results = []
    for index, y in enumerate(Y_VALUES):
        result = simulate(
            y, size=args.size, steps=args.steps, seed=args.seed + 2 * index
        )
        results.append({"y": y, **result})
        print(
            f"  {y:5.2f}   {result['co']:11.4f}   {result['o']:11.4f}"
            f"   {result['rate']:9.4f}   {result['state']}"
        )

    table = np.array(
        [[row["y"], row["co"], row["o"], row["rate"]] for row in results]
    )
    header = (
        "y, CO coverage, O coverage, CO2 production rate per site and unit time"
    )
    np.savetxt(
        args.output_dir / "phase_diagram.data",
        table,
        fmt="%12.6f",
        header=header,
    )
    print(f"Results written to {args.output_dir}")
    print(
        f"Literature: O poisoned below y1 = {Y1}, CO poisoned above y2 = {Y2}"
    )

    if args.plot:
        plot(results, args.output_dir / "zgb.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
