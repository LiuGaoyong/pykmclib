"""Three-dimensional diffusion of oxygen vacancies in a fluorite type oxide.

The third example of the KMCLib manual.  The lattice has two sites per cell:
an oxygen site, occupied by an oxygen ion ("O") or a vacancy ("V"), and a
metal site, which is occupied by a metal ion ("M") or a dopant ("D") or is
empty ("E").  Only the oxygen sub-lattice is mobile: a vacancy swaps place
with an oxygen ion on one of its six neighbouring oxygen sites.

Three choices make the mean square displacement (MSD) of the vacancies behave
differently along each axis:

* x: the lattice is not periodic, the vacancies are confined between two walls;
* y: periodic and unbiased, ordinary diffusion;
* z: periodic, but hops down are faster than hops up, so the vacancies drift.

Run it with::

    python diffusion_3d.py            # about 30 s
    python diffusion_3d.py --plot     # also writes a figure (needs matplotlib)

Reference:
  M. Leetmaa and N. V. Skorodumova, Comput. Phys. Commun. 185 (2014) 2340.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from pykmclib import (
    KMCConfiguration,
    KMCControlParameters,
    KMCInteractions,
    KMCLattice,
    KMCLatticeModel,
    KMCProcess,
    KMCUnitCell,
    OnTheFlyMSD,
)

# The distance between neighbouring oxygen sites, in Angstrom.
LATTICE_CONSTANT = 2.782
# The index of the oxygen site among the basis points of the cell.
OXYGEN_SITE = 0


def build_configuration(
    size=12, vacancy_fraction=0.4, dopant_fraction=0.4, seed=1
):
    """A lattice of ``size``^3 cells with random vacancies and dopants.

    :param vacancy_fraction: the fraction of the oxygen sites that are vacant.
    :param dopant_fraction: the fraction of the metal ions replaced by dopants.
    """
    unit_cell = KMCUnitCell(
        cell_vectors=LATTICE_CONSTANT * np.eye(3),
        # Positions within the cell, in units of the cell vectors: the oxygen
        # site and the metal site.
        basis_points=[[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
    lattice = KMCLattice(
        unit_cell=unit_cell,
        repetitions=(size, size, size),
        periodic=(False, True, True),
    )

    # One row per cell, in the order of the lattice sites: the last cell index
    # runs fastest.
    cells = np.indices((size, size, size)).reshape(3, -1).T
    rng = np.random.default_rng(seed)

    oxygen = np.full(len(cells), "O")
    n_vacancies = int(vacancy_fraction * len(cells))
    oxygen[rng.choice(len(cells), size=n_vacancies, replace=False)] = "V"

    # In this primitive cell of the oxygen sub-lattice only every second metal
    # site exists.
    metal = np.where(cells.sum(axis=1) % 2 == 0, "M", "E")
    occupied = np.flatnonzero(metal == "M")
    n_dopants = int(dopant_fraction * len(occupied))
    metal[rng.choice(occupied, size=n_dopants, replace=False)] = "D"

    # The types are listed cell by cell, and within a cell basis point by basis
    # point.
    types = np.column_stack([oxygen, metal]).ravel().tolist()
    return KMCConfiguration(
        lattice=lattice, types=types, possible_types=["E", "M", "D", "O", "V"]
    )


def build_interactions(
    rate_constant=1.0, rate_constant_up=0.9, rate_constant_down=1.1
):
    """Six processes: a vacancy swaps place with a neighbouring oxygen ion."""
    rate_constants = {
        (1.0, 0.0, 0.0): rate_constant,
        (-1.0, 0.0, 0.0): rate_constant,
        (0.0, 1.0, 0.0): rate_constant,
        (0.0, -1.0, 0.0): rate_constant,
        (0.0, 0.0, 1.0): rate_constant_up,
        (0.0, 0.0, -1.0): rate_constant_down,
    }
    processes = [
        KMCProcess(
            coordinates=[[0.0, 0.0, 0.0], list(direction)],
            elements_before=["V", "O"],
            elements_after=["O", "V"],
            # The process is only tried on oxygen sites.
            basis_sites=[OXYGEN_SITE],
            rate_constant=float(rate),
        )
        for direction, rate in rate_constants.items()
    ]
    return KMCInteractions(processes=processes, implicit_wildcards=True)


def slope(times, values):
    """The slope of a line through the points (``nan`` for fewer than two)."""
    if len(times) < 2:
        return float("nan")
    return float(np.polyfit(times, values, 1)[0])


def plot(msd, filename):
    try:
        import matplotlib
    except ImportError:
        print("matplotlib is not installed, no figure was written.")
        return
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cutoff = msd.safeCutoff()
    times = msd.timeSteps()[:cutoff]
    figure, axes = plt.subplots(figsize=(5.0, 3.6), dpi=110)
    labels = [
        "x: confined by walls",
        "y: free diffusion",
        "z: diffusion with drift",
    ]
    for index, label in enumerate(labels):
        axes.errorbar(
            times,
            msd.results()[index][:cutoff],
            yerr=msd.stdDev()[index][:cutoff],
            fmt=".-",
            ms=3,
            lw=0.8,
            label=label,
        )
    axes.set_xlabel("time lag")
    axes.set_ylabel(r"MSD of the vacancies ($\mathrm{\AA}^2$)")
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
        default=12,
        help="number of cells along each axis (default: %(default)s)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=500_000,
        help="number of kMC steps (default: %(default)s)",
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
        help="write a figure of the MSD (needs matplotlib)",
    )
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    vacancy_fraction = 0.4
    rate_constant, rate_constant_up, rate_constant_down = 1.0, 0.9, 1.1
    configuration = build_configuration(
        size=args.size, vacancy_fraction=vacancy_fraction, seed=args.seed
    )
    interactions = build_interactions(
        rate_constant, rate_constant_up, rate_constant_down
    )
    model = KMCLatticeModel(
        configuration=configuration, interactions=interactions
    )

    # Track every particle of type "V". Each vacancy keeps its last 200
    # positions.
    msd = OnTheFlyMSD(
        history_steps=200, n_bins=100, t_max=100.0, track_type="V"
    )
    control_parameters = KMCControlParameters(
        number_of_steps=args.steps,
        dump_interval=max(1, args.steps // 10),
        analysis_interval=1,
        seed=args.seed,
    )
    model.run(control_parameters=control_parameters, analysis=[msd])

    with open(args.output_dir / "msd.data", "w") as stream:
        msd.printResults(stream)

    # Only the bins below the "safe cutoff" have seen the full history buffer.
    cutoff = msd.safeCutoff()
    times = msd.timeSteps()[:cutoff]
    msd_x, msd_y, msd_z = (msd.results()[index][:cutoff] for index in range(3))
    third = cutoff // 3

    print()
    print(f"Results written to {args.output_dir}")
    if third < 2:
        print("Not enough data to analyse the MSD, run more steps.")
        return 0
    print(
        f"MSD of the vacancies, time lags up to {times[-1]:.1f};"
        " slopes in A^2 per unit time"
    )
    print("  direction    short lags    long lags    ratio    expected")
    expectations = ["< 1, confined", "= 1, diffusion", "> 1, drift"]
    for axis, values, expected in zip(
        "xyz", (msd_x, msd_y, msd_z), expectations, strict=True
    ):
        early = slope(times[:third], values[:third])
        late = slope(times[cutoff - third :], values[cutoff - third :])
        ratio = late / early if early else float("nan")
        print(
            f"  {axis}          {early:10.2f}   {late:10.2f}   {ratio:6.2f}"
            f"    {expected}"
        )

    # Simple estimates: a hop succeeds when the neighbouring oxygen site holds
    # an ion, which is the case with the probability 1 - vacancy_fraction.
    blocking = 1.0 - vacancy_fraction
    slope_estimate = 2.0 * rate_constant * LATTICE_CONSTANT**2 * blocking
    drift_estimate = (
        (rate_constant_down - rate_constant_up) * LATTICE_CONSTANT * blocking
    )
    # The drift adds (velocity * time)^2 to the MSD along z, compared to the
    # unbiased y direction.
    drift = float(
        np.sqrt(max(0.0, np.sum(times**2 * (msd_z - msd_y)) / np.sum(times**4)))
    )
    print(
        f"Slope along y:          {slope(times, msd_y):6.2f} A^2 per unit time"
        f" (estimate: {slope_estimate:.2f})"
    )
    print(
        f"Drift velocity along z: {drift:6.3f} A per unit time"
        f" (estimate: {drift_estimate:.3f})"
    )

    if args.plot:
        plot(msd, args.output_dir / "diffusion_3d.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
