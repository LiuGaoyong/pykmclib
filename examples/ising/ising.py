"""Two-dimensional Ising spin model with a custom rate calculator.

The second example of the KMCLib manual, after the model that introduced the
rejection-free ("n-fold way") kinetic Monte Carlo algorithm.  Every site of a
periodic square lattice carries a spin, up ("U") or down ("D").  The only
elementary processes are the two spin flips; what makes the model interesting
is that the rate of a flip depends on the four neighbouring spins:

    rate = min(1, exp(-dE / kT))
    dE = J * (aligned neighbours - opposite neighbours)

Such environment dependent rates are supplied by a *rate calculator*: a class
derived from ``KMCRateCalculatorPlugin`` whose ``rate`` method is called by the
C++ backend whenever it needs the rate of a process at a site.

Starting from random spins below the critical temperature (kT/J = 1, while
kT_c/J = 1.13), the spins order: domains of aligned spins grow until one of
them fills the lattice.  The magnetisation and the fraction of aligned
neighbour pairs then fluctuate around the exact values known for the
two-dimensional Ising model.

Run it with::

    python ising.py                    # Python rate calculator, about 10 s
    python ising.py --calculator cpp   # the built-in C++ rate calculator
    python ising.py --plot             # also writes a figure (needs matplotlib)

References:
  A. B. Bortz, M. H. Kalos and J. L. Lebowitz, J. Comput. Phys. 17 (1975) 10.
  L. Onsager, Phys. Rev. 65 (1944) 117; C. N. Yang, Phys. Rev. 85 (1952) 808.
  M. Leetmaa and N. V. Skorodumova, Comput. Phys. Commun. 185 (2014) 2340.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
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
    KMCRateCalculatorPlugin,
    KMCUnitCell,
)

# Process numbers: the positions of the processes in the list given to
# KMCInteractions.
FLIP_UP_TO_DOWN = 0
FLIP_DOWN_TO_UP = 1


def build_configuration(size=40, seed=1):
    """A periodic ``size`` x ``size`` lattice: random spins, half of them up."""
    unit_cell = KMCUnitCell(
        cell_vectors=np.eye(3), basis_points=[[0.0, 0.0, 0.0]]
    )
    lattice = KMCLattice(
        unit_cell=unit_cell,
        repetitions=(size, size, 1),
        periodic=(True, True, False),
    )

    spins = np.array(
        ["U", "D"] * (size * size // 2) + ["U"] * (size * size % 2)
    )
    np.random.default_rng(seed).shuffle(spins)
    return KMCConfiguration(
        lattice=lattice, types=spins.tolist(), possible_types=["U", "D"]
    )


def build_interactions():
    """The two spin flips.

    Their rate constants are placeholders: the rate calculator sets the rates.
    """
    site = [[0.0, 0.0, 0.0]]
    processes = [
        KMCProcess(
            coordinates=site,
            elements_before=["U"],
            elements_after=["D"],
            basis_sites=[0],
            rate_constant=1.0,
        ),
        KMCProcess(
            coordinates=site,
            elements_before=["D"],
            elements_after=["U"],
            basis_sites=[0],
            rate_constant=1.0,
        ),
    ]
    return KMCInteractions(processes=processes, implicit_wildcards=True)


class IsingRateCalculator(KMCRateCalculatorPlugin):
    """Metropolis flip rates of the Ising model at the temperature kT/J."""

    kbt_over_j = 1.0

    def rate(
        self,
        coords,
        types_before,
        types_after,
        rate_constant,
        process_number,
        global_coordinate,
    ):
        # The backend hands over all sites within `cutoff()` of the site the
        # process acts on, sorted by distance: the site itself comes first,
        # followed by its four neighbours.
        up_neighbours = sum(1 for spin in types_before[1:5] if spin == "U")
        down_neighbours = 4 - up_neighbours

        if process_number == FLIP_UP_TO_DOWN:
            energy_change = up_neighbours - down_neighbours
        else:
            energy_change = down_neighbours - up_neighbours
        return min(1.0, math.exp(-energy_change / self.kbt_over_j))

    def cutoff(self):
        # Nearest neighbours only, in units of the cell vectors.
        return 1.0

    def cacheRates(self):
        # The rate depends on the local environment only, never on the position
        # or the time, so the backend may remember it: Python is then called
        # once per distinct environment.
        return True


def rate_calculator(kbt_over_j):
    """An ``IsingRateCalculator`` class for the given temperature.

    The interactions take a class, not an instance, hence this function.
    """
    return type(
        "IsingRateCalculator",
        (IsingRateCalculator,),
        {"kbt_over_j": float(kbt_over_j)},
    )


class SpinOrder(KMCAnalysisPlugin):
    """Record the magnetisation and the fraction of aligned neighbour pairs.

    A custom analysis: ``setup`` is called before the first step,
    ``registerStep`` every ``analysis_interval`` steps and ``finalize`` after
    the last one.
    """

    def __init__(self):
        self.times = []
        self.magnetisation = []
        self.aligned_fraction = []
        self.snapshots = []

    @staticmethod
    def spins(configuration):
        """The spins as an array of +1 / -1 with the shape of the lattice."""
        size_a, size_b, _ = configuration.cellRepetitions()
        up = np.array(configuration.types()) == "U"
        return np.where(up, 1, -1).reshape(size_a, size_b)

    def setup(self, step, time, configuration):
        self.registerStep(step, time, configuration)

    def registerStep(self, step, time, configuration):
        spins = self.spins(configuration)
        aligned = np.mean(spins == np.roll(spins, 1, axis=0)) + np.mean(
            spins == np.roll(spins, 1, axis=1)
        )
        self.times.append(time)
        self.magnetisation.append(spins.mean())
        self.aligned_fraction.append(aligned / 2.0)
        self.snapshots.append(spins)

    def printResults(self, stream=sys.stdout):
        stream.write(f"{'time':>15s} {'magnetisation':>15s} {'aligned':>15s}\n")
        for row in zip(
            self.times, self.magnetisation, self.aligned_fraction, strict=True
        ):
            stream.write("{:15.5e} {:15.5f} {:15.5f}\n".format(*row))


def exact_magnetisation(kbt_over_j):
    """The magnetisation of the infinite lattice in equilibrium (Yang 1952)."""
    # In the usual notation, E = -J' * sum over pairs of s_i * s_j, this model
    # has J' = J / 2.
    coupling = 0.5 / kbt_over_j
    argument = math.sinh(2.0 * coupling) ** -4
    return (1.0 - argument) ** 0.125 if argument < 1.0 else 0.0


def exact_aligned_fraction(kbt_over_j):
    """The fraction of aligned neighbour pairs in equilibrium (Onsager 1944)."""
    coupling = 0.5 / kbt_over_j
    modulus = 2.0 * math.sinh(2.0 * coupling) / math.cosh(2.0 * coupling) ** 2
    # The complete elliptic integral of the first kind, by the midpoint rule.
    angles = (np.arange(20000) + 0.5) * (0.5 * math.pi / 20000)
    elliptic = np.sum(1.0 / np.sqrt(1.0 - (modulus * np.sin(angles)) ** 2)) * (
        0.5 * math.pi / 20000
    )
    tanh = math.tanh(2.0 * coupling)
    pair_correlation = (
        0.5 / tanh * (1.0 + 2.0 / math.pi * (2.0 * tanh**2 - 1.0) * elliptic)
    )
    return 0.5 * (1.0 + pair_correlation)


def plot(order, exact, filename):
    try:
        import matplotlib
    except ImportError:
        print("matplotlib is not installed, no figure was written.")
        return
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(
        1, 4, figsize=(11.0, 2.9), dpi=110, width_ratios=[1, 1, 1, 1.5]
    )
    chosen = [0, len(order.snapshots) // 40, len(order.snapshots) - 1]
    for axis, index in zip(axes[:3], chosen, strict=True):
        axis.imshow(
            order.snapshots[index],
            cmap="coolwarm",
            vmin=-1,
            vmax=1,
            interpolation="nearest",
        )
        axis.set_title(f"t = {order.times[index]:.0f}", fontsize=10)
        axis.set_xticks([])
        axis.set_yticks([])

    axes[3].plot(
        order.times, np.abs(order.magnetisation), label="|magnetisation|"
    )
    axes[3].plot(
        order.times, order.aligned_fraction, label="aligned neighbour pairs"
    )
    for value in exact:
        axes[3].axhline(value, color="k", ls="--", lw=0.8)
    axes[3].plot([], [], "k--", lw=0.8, label="exact, in equilibrium")
    axes[3].set_xlabel("time")
    axes[3].set_ylim(0.0, 1.0)
    axes[3].legend(frameon=False, fontsize=8, loc="center right")
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
        default=1_000_000,
        help="number of kMC steps (default: %(default)s)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="kT/J (default: %(default)s)",
    )
    parser.add_argument(
        "--calculator",
        choices=["python", "cpp"],
        default="python",
        help="the rate calculator: the Python class of this script, or the "
        "C++ one built into pykmclib",
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
        help="write a figure with snapshots (needs matplotlib)",
    )
    args = parser.parse_args(argv)
    if args.calculator == "cpp" and args.temperature != 1.0:
        parser.error("the built-in C++ calculator is written for kT/J = 1")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    configuration = build_configuration(size=args.size, seed=args.seed)
    interactions = build_interactions()
    if args.calculator == "python":
        # A class, not an instance: the interactions create the calculator when
        # the model is set up.
        interactions.setRateCalculator(
            rate_calculator=rate_calculator(args.temperature)
        )
    else:
        # A string selects one of the calculators compiled into the backend.
        interactions.setRateCalculator(rate_calculator="IsingTestCalculator")
    model = KMCLatticeModel(
        configuration=configuration, interactions=interactions
    )

    order = SpinOrder()
    control_parameters = KMCControlParameters(
        number_of_steps=args.steps,
        dump_interval=max(1, args.steps // 10),
        analysis_interval=max(1, args.steps // 200),
        seed=args.seed,
    )
    started = time.perf_counter()
    model.run(control_parameters=control_parameters, analysis=[order])
    elapsed = time.perf_counter() - started

    with open(args.output_dir / "order.data", "w") as stream:
        order.printResults(stream)
    np.savetxt(
        args.output_dir / "spins_final.txt", order.snapshots[-1], fmt="%2d"
    )

    # Average over the last quarter of the records, when the lattice had time
    # to order.
    late = slice(-max(1, len(order.times) // 4), None)
    magnetisation = np.abs(order.magnetisation)
    exact = (
        exact_magnetisation(args.temperature),
        exact_aligned_fraction(args.temperature),
    )

    print()
    print(f"Results written to {args.output_dir}")
    print(
        f"{args.steps} steps with the {args.calculator} rate calculator"
        f" took {elapsed:.1f} s"
    )
    print(
        "                              start   late in the run"
        "   exact, in equilibrium"
    )
    print(
        f"  |magnetisation|          {magnetisation[0]:8.3f}"
        f" {magnetisation[late].mean():13.3f} {exact[0]:17.3f}"
    )
    print(
        f"  aligned neighbour pairs  {order.aligned_fraction[0]:8.3f}"
        f" {np.mean(order.aligned_fraction[late]):13.3f} {exact[1]:17.3f}"
    )

    if args.plot:
        plot(order, exact, args.output_dir / "ising.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
