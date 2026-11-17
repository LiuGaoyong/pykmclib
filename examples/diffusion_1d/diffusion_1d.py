"""One-dimensional diffusion: a random walk on a periodic chain.

The first example of the KMCLib manual.  One "B" particle hops left and right
with the same rate constant ``k`` in a sea of "A" particles, and its mean
square displacement (MSD) is collected on the fly.  For an unbiased walk with
hop length ``a`` the MSD grows linearly with the time lag ``t``:

    MSD(t) = 2 k a^2 t + a^2

The slope gives the diffusion coefficient, ``D = k a^2``.  The offset ``a^2``
appears because the positions are recorded right after a hop: an interval
between two recorded positions always contains the hop that ends it, on top of
the ``2 k t`` hops expected in a time ``t``.  Both numbers are exact, so the
simulation can be checked against them.

Run it with::

    python diffusion_1d.py            # about 5 s
    python diffusion_1d.py --plot     # also writes a figure (needs matplotlib)

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

LATTICE_CONSTANT = 5.2  # distance between neighbouring sites, in Angstrom
RATE_CONSTANT = 1.5  # hops per unit time in each direction


def build_configuration(n_sites=10):
    """A periodic chain of ``n_sites`` sites: one "B" in a sea of "A"."""
    unit_cell = KMCUnitCell(
        cell_vectors=np.array(
            [[LATTICE_CONSTANT, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        ),
        basis_points=[[0.0, 0.0, 0.0]],
    )
    lattice = KMCLattice(
        unit_cell=unit_cell,
        repetitions=(n_sites, 1, 1),
        periodic=(True, False, False),
    )

    types = ["A"] * n_sites
    types[n_sites // 2] = "B"
    return KMCConfiguration(
        lattice=lattice, types=types, possible_types=["A", "B"]
    )


def build_interactions(rate_constant=RATE_CONSTANT):
    """Two processes: "B" swaps place with its left or its right neighbour."""
    processes = [
        KMCProcess(
            # Local geometry in units of the cell vectors; the first point is
            # the site the process acts on.
            coordinates=[[0.0, 0.0, 0.0], [direction, 0.0, 0.0]],
            elements_before=["B", "A"],
            elements_after=["A", "B"],
            basis_sites=[0],
            rate_constant=float(rate_constant),
        )
        for direction in (-1.0, 1.0)
    ]
    return KMCInteractions(processes=processes, implicit_wildcards=True)


def fit_line(times, values, errors):
    """Weighted least-squares fit of ``values = slope * times + offset``.

    ``OnTheFlyMSD`` estimates the error of every point as a fraction of the
    measured value. Using those errors directly as weights would favour the
    points that happen to lie low, so the weights are built from the relative
    errors and the time lag instead.

    :returns: ``(slope, offset)``, or ``None`` with fewer than three usable
              points.
    """
    usable = (errors > 0.0) & (values > 0.0)
    times, values, errors = times[usable], values[usable], errors[usable]
    if len(times) < 3:
        return None

    expected_errors = errors / values * times
    slope, offset = np.polyfit(times, values, 1, w=1.0 / expected_errors)
    return float(slope), float(offset)


def plot(msd, fit, expected, filename):
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
    axes.errorbar(
        times,
        msd.results()[0][:cutoff],
        yerr=msd.stdDev()[0][:cutoff],
        fmt=".",
        ms=3,
        lw=0.6,
        label="kMC",
    )
    if fit is not None:
        slope, offset = fit
        axes.plot(
            times,
            slope * times + offset,
            lw=1.2,
            label=f"fit, slope {slope:.1f}",
        )
    axes.plot(
        times,
        expected[0] * times + expected[1],
        "k--",
        lw=1.0,
        label=rf"$2ka^2t+a^2$, slope {expected[0]:.1f}",
    )
    axes.set_xlabel("time lag")
    axes.set_ylabel(r"MSD$_x$ ($\mathrm{\AA}^2$)")
    axes.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(filename)
    plt.close(figure)
    print(f"Figure written to {filename}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--steps",
        type=int,
        default=1_000_000,
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

    model = KMCLatticeModel(
        configuration=build_configuration(), interactions=build_interactions()
    )

    # The position of the particle is recorded after every step
    # (analysis_interval=1) and the last 200 positions are kept. With three hops
    # per unit of time on average, that covers time lags up to about 65, so the
    # MSD histogram is collected up to t_max=50.
    msd = OnTheFlyMSD(history_steps=200, n_bins=100, t_max=50.0, track_type="B")
    control_parameters = KMCControlParameters(
        number_of_steps=args.steps,
        dump_interval=max(1, args.steps // 10),
        analysis_interval=1,
        seed=args.seed,
    )
    model.run(
        control_parameters=control_parameters,
        trajectory_filename=str(args.output_dir / "traj.xyz"),
        trajectory_type="xyz",
        analysis=[msd],
    )

    # Every built-in analysis can print its results as a table.
    with open(args.output_dir / "msd.data", "w") as stream:
        msd.printResults(stream)

    # Only the bins below the "safe cutoff" have seen the full history buffer.
    cutoff = msd.safeCutoff()
    fit = fit_line(
        msd.timeSteps()[:cutoff],
        msd.results()[0][:cutoff],
        msd.stdDev()[0][:cutoff],
    )
    expected = (2.0 * RATE_CONSTANT * LATTICE_CONSTANT**2, LATTICE_CONSTANT**2)

    print()
    print(f"Results written to {args.output_dir}")
    print("                  slope (A^2 per unit time)   offset (A^2)")
    print(
        f"  exact           {expected[0]:12.2f}             {expected[1]:10.2f}"
    )
    if fit is None:
        print("  kMC             not enough data for a fit, run more steps")
    else:
        print(f"  kMC             {fit[0]:12.2f}             {fit[1]:10.2f}")
        print(
            f"Diffusion coefficient D = slope / 2 = {fit[0] / 2.0:.2f} A^2 per"
            f" unit time (exact: {expected[0] / 2.0:.2f})"
        )

    if args.plot:
        plot(msd, fit, expected, args.output_dir / "diffusion_1d.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
