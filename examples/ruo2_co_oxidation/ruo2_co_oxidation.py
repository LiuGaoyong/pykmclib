"""CO oxidation at RuO2(110): a first-principles kMC model from the literature.

The model of K. Reuter and M. Scheffler, Phys. Rev. B 73 (2006) 045433.  The
surface has two kinds of adsorption sites, arranged in alternating rows:
bridge ("br") and coordinatively unsaturated ("cus") sites.  Each site is empty
("E") or holds an oxygen atom ("O") or a CO molecule ("CO").  The processes are

* adsorption and desorption of CO on either site,
* dissociative adsorption of O2 on two neighbouring sites, and the reverse,
* hops of O and CO to a neighbouring empty site,
* reaction of neighbouring O and CO to CO2, which leaves the surface at once.

That is 22 kinds of processes; the paper counts 26 because it lists the
(negligible) re-adsorption of CO2 as well.  All rate constants follow from the
binding energies and barriers of Table III of the paper, the temperature and
the partial pressures of the two gases.

The script scans the CO pressure at 600 K and 1 atm of O2 and reports the
occupation of the sites and the turnover frequency (TOF): the number of CO2
molecules formed per site and second.

Run it with::

    python ruo2_co_oxidation.py          # about 1 min
    python ruo2_co_oxidation.py --plot   # also writes a figure (matplotlib)
"""

from __future__ import annotations

import argparse
import contextlib
import io
import math
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

# Physical constants.
BOLTZMANN_EV = 8.617333262e-5  # eV / K
BOLTZMANN_J = 1.380649e-23  # J / K
PLANCK_EV = 4.135667696e-15  # eV s
PLANCK_J = 6.62607015e-34  # J s
ATOMIC_MASS = 1.66053907e-27  # kg
ATMOSPHERE = 101325.0  # Pa

# The surface unit cell: 6.43 A across the rows, 3.12 A along them; one br and
# one cus site.
CELL_ACROSS, CELL_ALONG = 6.43, 3.12  # Angstrom
# The index of the two sites among the basis points of the cell.
BRIDGE, CUS = 0, 1
SITE_NAMES = ("br", "cus")
SPECIES = ("E", "O", "CO")

# Table III of Reuter and Scheffler (2006), in eV.
BINDING_ENERGY = {
    ("CO", BRIDGE): -1.6,
    ("CO", CUS): -1.3,
    ("O", BRIDGE): -2.3,
    ("O", CUS): -1.0,
}
# Diffusion barriers: (species, from, to).
DIFFUSION_BARRIER = {
    ("CO", BRIDGE, BRIDGE): 0.6,
    ("CO", BRIDGE, CUS): 1.6,
    ("CO", CUS, BRIDGE): 1.3,
    ("CO", CUS, CUS): 1.7,
    ("O", BRIDGE, BRIDGE): 0.7,
    ("O", BRIDGE, CUS): 2.3,
    ("O", CUS, BRIDGE): 1.0,
    ("O", CUS, CUS): 1.6,
}
# Reaction barriers: (site of the CO, site of the O).
REACTION_BARRIER = {
    (BRIDGE, BRIDGE): 1.5,
    (BRIDGE, CUS): 0.8,
    (CUS, BRIDGE): 1.2,
    (CUS, CUS): 0.9,
}

# The gas molecules: mass (atomic units), rotational temperature (K), symmetry
# number, vibrational temperature (K) and degeneracy of the electronic ground
# state.
MOLECULES = {
    "CO": (28.010, 2.779, 1, 3122.0, 1),
    "O2": (31.998, 2.080, 2, 2274.0, 3),
}


def chemical_potential(molecule, temperature, pressure):
    """The chemical potential of an ideal gas of ``molecule`` in eV.

    The zero of energy is the molecule at rest in its ground state.

    :param temperature: in K.
    :param pressure: in atm.
    """
    mass, t_rotation, symmetry, t_vibration, degeneracy = MOLECULES[molecule]
    kt = BOLTZMANN_J * temperature
    wavelength = PLANCK_J / math.sqrt(2.0 * math.pi * mass * ATOMIC_MASS * kt)
    translation = kt / (pressure * ATMOSPHERE * wavelength**3)
    rotation = temperature / (symmetry * t_rotation)
    vibration = 1.0 / (1.0 - math.exp(-t_vibration / temperature))
    partition_function = translation * rotation * vibration * degeneracy
    return -BOLTZMANN_EV * temperature * math.log(partition_function)


def impingement_rate(molecule, temperature, pressure):
    """The number of molecules hitting half a surface unit cell per second.

    From the kinetic theory of gases.  Each site, or pair of sites, gets half
    of the area of the cell.
    """
    mass = MOLECULES[molecule][0] * ATOMIC_MASS
    area = 0.5 * CELL_ACROSS * CELL_ALONG * 1.0e-20  # m^2
    momentum = math.sqrt(2.0 * math.pi * mass * BOLTZMANN_J * temperature)
    return pressure * ATMOSPHERE * area / momentum


def neighbours(site, other):
    """Where the sites of kind ``other`` next to a site of kind ``site`` are.

    The positions are relative to the site, in units of the cell vectors.
    """
    if site == other:
        return ([0.0, 1.0, 0.0], [0.0, -1.0, 0.0])  # the same row
    return ([0.5, 0.0, 0.0], [-0.5, 0.0, 0.0])  # the two rows next to it


def process_table(temperature=600.0, p_co=7.0, p_o2=1.0):
    """All processes of the model, one row each.

    A row is ``(name, site, neighbour, before, after, rate constant)``.
    ``site`` is the kind of site the process acts on, ``neighbour`` the relative
    position of the second site involved (``None`` for processes on a single
    site). The order of the rows is the same for all conditions, so a process
    number always means the same process.

    :param temperature: in K.
    :param p_co: partial pressure of CO in atm.
    :param p_o2: partial pressure of O2 in atm.
    """
    kt = BOLTZMANN_EV * temperature
    # k_B T / h, about 1.25e13 per second at 600 K.
    attempt_frequency = kt / PLANCK_EV
    mu_co = chemical_potential("CO", temperature, p_co)
    mu_o2 = chemical_potential("O2", temperature, p_o2)
    rows = []

    def add(name, site, neighbour, before, after, rate):
        rows.append((name, site, neighbour, before, after, rate))

    # CO: adsorption without a barrier on any empty site. Desorption follows
    # from detailed balance: the ratio of the rate constants of adsorption and
    # desorption is exp((mu_gas - E_binding) / kT).
    for site in (BRIDGE, CUS):
        name = SITE_NAMES[site]
        adsorption = impingement_rate("CO", temperature, p_co)
        binding = BINDING_ENERGY["CO", site]
        desorption = adsorption * math.exp((binding - mu_co) / kt)
        add(f"CO adsorption {name}", site, None, ["E"], ["CO"], adsorption)
        add(f"CO desorption {name}", site, None, ["CO"], ["E"], desorption)

    # O2: dissociative adsorption on a pair of empty neighbouring sites, and
    # the reverse. Every pair is listed once: br-br and cus-cus with the upper
    # site, br-cus from the br site.
    for site, other, positions in (
        (BRIDGE, BRIDGE, neighbours(BRIDGE, BRIDGE)[:1]),
        (CUS, CUS, neighbours(CUS, CUS)[:1]),
        (BRIDGE, CUS, neighbours(BRIDGE, CUS)),
    ):
        adsorption = impingement_rate("O2", temperature, p_o2)
        binding = BINDING_ENERGY["O", site] + BINDING_ENERGY["O", other]
        desorption = adsorption * math.exp((binding - mu_o2) / kt)
        pair = f"{SITE_NAMES[site]}-{SITE_NAMES[other]}"
        empty, oxygen = ["E", "E"], ["O", "O"]
        for position in positions:
            add(
                f"O2 adsorption {pair}",
                site,
                position,
                empty,
                oxygen,
                adsorption,
            )
            add(
                f"O2 desorption {pair}",
                site,
                position,
                oxygen,
                empty,
                desorption,
            )

    # Diffusion: a hop to an empty neighbouring site, over the barrier of
    # Table III.
    for (species, site, other), barrier in DIFFUSION_BARRIER.items():
        rate = attempt_frequency * math.exp(-barrier / kt)
        name = f"{species} diffusion {SITE_NAMES[site]}-{SITE_NAMES[other]}"
        for position in neighbours(site, other):
            add(name, site, position, [species, "E"], ["E", species], rate)

    # Reaction: CO + O -> CO2, which desorbs at once and leaves two empty sites.
    # The paper uses half of k_B T / h as the prefactor of these four processes.
    for (site, other), barrier in REACTION_BARRIER.items():
        rate = 0.5 * attempt_frequency * math.exp(-barrier / kt)
        name = f"reaction CO {SITE_NAMES[site]} + O {SITE_NAMES[other]}"
        for position in neighbours(site, other):
            add(name, site, position, ["CO", "O"], ["E", "E"], rate)
    return rows


# The numbers of the reaction processes, by the kind of reaction.
REACTIONS = {}
for _number, _row in enumerate(process_table()):
    if _row[0].startswith("reaction "):
        _kind = _row[0].removeprefix("reaction ")
        REACTIONS.setdefault(_kind, []).append(_number)


def build_configuration(cells_across=10, cells_along=10, bridge="O", cus="E"):
    """A surface of ``cells_across`` x ``cells_along`` unit cells.

    :param bridge: what the bridge sites hold at the start: "E", "O" or "CO".
    :param cus: what the cus sites hold at the start.
    """
    unit_cell = KMCUnitCell(
        cell_vectors=[
            [CELL_ACROSS, 0.0, 0.0],
            [0.0, CELL_ALONG, 0.0],
            [0.0, 0.0, 10.0],
        ],
        # In units of the cell vectors: the cus rows lie halfway between the
        # bridge rows.
        basis_points=[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
    )
    lattice = KMCLattice(
        unit_cell=unit_cell,
        repetitions=(cells_across, cells_along, 1),
        periodic=(True, True, False),
    )
    # The types are listed cell by cell, and within a cell basis point by basis
    # point.
    types = [bridge, cus] * (cells_across * cells_along)
    return KMCConfiguration(
        lattice=lattice, types=types, possible_types=list(SPECIES)
    )


def build_interactions(temperature=600.0, p_co=7.0, p_o2=1.0):
    """The processes of the model for the given conditions.

    :param temperature: in K.
    :param p_co: partial pressure of CO in atm.
    :param p_o2: partial pressure of O2 in atm.
    """
    processes = []
    table = process_table(temperature, p_co, p_o2)
    for _, site, neighbour, before, after, rate in table:
        coordinates = [[0.0, 0.0, 0.0]]
        if neighbour is not None:
            coordinates.append(neighbour)
        processes.append(
            KMCProcess(
                coordinates=coordinates,
                elements_before=before,
                elements_after=after,
                # The process only applies to sites of this kind.
                basis_sites=[site],
                rate_constant=rate,
            )
        )
    return KMCInteractions(processes=processes, implicit_wildcards=True)


class TurnoverFrequency(KMCAnalysisPlugin):
    """Count the reaction events: the CO2 formed per site and second.

    :param skip_steps: leave out this many steps at the start of the run.
    """

    def __init__(self, skip_steps=0):
        self.skip_steps = int(skip_steps)
        self.kind = {
            number: name
            for name, numbers in REACTIONS.items()
            for number in numbers
        }
        self.counts = dict.fromkeys(REACTIONS, 0)
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
        kind = self.kind.get(configuration.latestEventProcess())
        if kind is not None:
            self.counts[kind] += 1
        self.end_time = time

    def tof(self):
        """CO2 molecules per site and second."""
        elapsed = self.end_time - self.start_time
        if elapsed <= 0.0:
            return 0.0
        return sum(self.counts.values()) / (self.sites * elapsed)

    def shares(self):
        """The fraction of the CO2 formed by each kind of reaction."""
        total = sum(self.counts.values())
        return {
            name: count / total if total else 0.0
            for name, count in self.counts.items()
        }

    def printResults(self, stream=sys.stdout):
        elapsed = self.end_time - self.start_time
        stream.write(f"elapsed time: {elapsed:.6e} s\n")
        stream.write(f"TOF: {self.tof():.6e} CO2 per site and second\n")
        for name, count in self.counts.items():
            stream.write(f"{name:>22s}: {count} events\n")


class SiteOccupation(KMCAnalysisPlugin):
    """The average occupation of the bridge and of the cus sites.

    The configuration is looked at every ``sampling_interval`` steps. A state of
    a kMC simulation lasts until the next step, so every sample is weighted by
    that time.

    :param skip_steps: leave out this many steps at the start of the run.
    """

    def __init__(self, sampling_interval=100, skip_steps=0):
        self.sampling_interval = int(sampling_interval)
        self.skip_steps = int(skip_steps)
        # One row per kind of site, one column per species.
        self.weights = np.zeros((2, len(SPECIES)))
        self._sample = None
        self._time = 0.0

    def setup(self, step, time, configuration):
        self._sample = None

    def registerStep(self, step, time, configuration):
        if self._sample is not None:
            # The sampled state lasted from the previous step until this one.
            self.weights += self._sample * (time - self._time)
            self._sample = None
        if step > self.skip_steps and step % self.sampling_interval == 0:
            # One row per cell: what its bridge and its cus site hold.
            types = np.array(configuration.types()).reshape(-1, 2)
            sample = np.zeros_like(self.weights)
            for site in (BRIDGE, CUS):
                for column, name in enumerate(SPECIES):
                    sample[site, column] = np.mean(types[:, site] == name)
            self._sample = sample
            self._time = time

    def occupation(self):
        """A dict ``{(site, species): fraction}``, keys like ("cus", "CO")."""
        total = self.weights.sum(axis=1, keepdims=True)
        fractions = np.divide(
            self.weights,
            total,
            out=np.zeros_like(self.weights),
            where=total > 0.0,
        )
        return {
            (SITE_NAMES[site], name): float(fractions[site, column])
            for site in (BRIDGE, CUS)
            for column, name in enumerate(SPECIES)
        }

    def printResults(self, stream=sys.stdout):
        for (site, name), fraction in self.occupation().items():
            stream.write(f"{name:>3s} on {site:>3s}: {fraction:.6f}\n")


def simulate(
    p_co,
    temperature=600.0,
    p_o2=1.0,
    cells=10,
    steps=250_000,
    bridge="O",
    cus="E",
    seed=1,
):
    """Run the model at one set of conditions.

    :returns: ``(turnover, occupation)``, the two analysis objects of the
              measuring run.
    """
    configuration = build_configuration(cells, cells, bridge=bridge, cus=cus)
    model = KMCLatticeModel(
        configuration=configuration,
        interactions=build_interactions(temperature, p_co, p_o2),
    )

    def run(analysis, seed):
        control_parameters = KMCControlParameters(
            number_of_steps=steps, dump_interval=steps, seed=seed
        )
        # Silence the progress messages of the library: this run is one of a
        # series.
        with contextlib.redirect_stdout(io.StringIO()):
            model.run(control_parameters=control_parameters, analysis=analysis)

    # First let the surface adapt to the gas, then measure. The second run
    # continues from the configuration and the time at which the first one
    # stopped.
    run(analysis=None, seed=seed)
    turnover, occupation = TurnoverFrequency(), SiteOccupation()
    run(analysis=[turnover, occupation], seed=seed + 1)
    return turnover, occupation


def plot(results, filename):
    try:
        import matplotlib
    except ImportError:
        print("matplotlib is not installed, no figure was written.")
        return
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pressures = [row["p_co"] for row in results]
    figure, (top, bottom) = plt.subplots(
        2, 1, figsize=(5.0, 5.2), dpi=110, sharex=True
    )
    top.errorbar(
        pressures,
        [row["tof"] for row in results],
        yerr=[row["tof_error"] for row in results],
        fmt="o-",
        ms=4,
    )
    top.set_xscale("log")
    top.set_yscale("log")
    top.set_ylabel(r"TOF (CO$_2$ site$^{-1}$ s$^{-1}$)")

    for site, style in (("cus", "-"), ("br", "--")):
        for name, colour in (("O", "tab:red"), ("CO", "tab:gray")):
            values = [row["occupation"][site, name] for row in results]
            bottom.plot(
                pressures,
                values,
                style,
                color=colour,
                marker="o",
                ms=3,
                label=f"{name} on {site}",
            )
    bottom.set_xlabel(r"$p_\mathrm{CO}$ (atm)")
    bottom.set_ylabel("occupation")
    bottom.legend(frameon=False, fontsize=8, ncols=2, loc="center left")
    figure.tight_layout()
    figure.savefig(filename)
    plt.close(figure)
    print(f"Figure written to {filename}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--temperature",
        type=float,
        default=600.0,
        help="in K (default: %(default)s)",
    )
    parser.add_argument(
        "--p-o2",
        type=float,
        default=1.0,
        help="partial pressure of O2 in atm (default: %(default)s)",
    )
    parser.add_argument(
        "--p-co",
        type=float,
        nargs="+",
        default=[1.0, 2.0, 4.0, 7.0, 10.0, 15.0, 25.0],
        help="partial pressures of CO in atm, one run each "
        "(default: a scan from 1 to 25 atm)",
    )
    parser.add_argument(
        "--cells",
        type=int,
        default=10,
        help="the surface has cells x cells unit cells (default: 10)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=250_000,
        help="number of kMC steps to adapt to the gas, and again to measure "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--bridge",
        choices=SPECIES,
        default="O",
        help="what the bridge sites hold at the start (default: %(default)s)",
    )
    parser.add_argument(
        "--cus",
        choices=SPECIES,
        default="E",
        help="what the cus sites hold at the start (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2006,
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
        help="write a figure of the scan (needs matplotlib)",
    )
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"T = {args.temperature:g} K, p(O2) = {args.p_o2:g} atm,"
        f" {args.cells} x {args.cells} cells"
    )
    print(
        "  p(CO)     TOF, CO2 per site and s     occupation of br"
        "       occupation of cus      share of"
    )
    print(
        "  (atm)                                  O       CO     "
        "        O       CO           CO cus + O cus"
    )
    results = []
    for index, p_co in enumerate(args.p_co):
        turnover, occupation = simulate(
            p_co,
            temperature=args.temperature,
            p_o2=args.p_o2,
            cells=args.cells,
            steps=args.steps,
            bridge=args.bridge,
            cus=args.cus,
            seed=args.seed + 2 * index,
        )
        events = sum(turnover.counts.values())
        # The reaction events are independent: their number scatters by its
        # square root.
        tof = turnover.tof()
        tof_error = tof / math.sqrt(events) if events else 0.0
        fractions, shares = occupation.occupation(), turnover.shares()
        results.append(
            {
                "p_co": p_co,
                "tof": tof,
                "tof_error": tof_error,
                "occupation": fractions,
                "shares": shares,
            }
        )
        print(
            f"  {p_co:5.3g}    {tof:10.3e} +/- {tof_error:8.1e}"
            f"    {fractions['br', 'O']:6.3f}  {fractions['br', 'CO']:6.3f}"
            f"         {fractions['cus', 'O']:6.3f}"
            f"  {fractions['cus', 'CO']:6.3f}"
            f"         {shares['CO cus + O cus']:6.2f}"
        )

    # One row per pressure: the TOF, the occupations and the shares.
    columns = [(site, name) for site in SITE_NAMES for name in ("O", "CO")]
    table = np.array(
        [
            [row["p_co"], row["tof"], row["tof_error"]]
            + [row["occupation"][column] for column in columns]
            + [row["shares"][kind] for kind in REACTIONS]
            for row in results
        ]
    )
    header = (
        "p_CO (atm), TOF (1/site/s), error, O on br, CO on br, O on cus,"
        " CO on cus, share of: " + ", ".join(REACTIONS)
    )
    np.savetxt(
        args.output_dir / "scan.data", table, fmt="%12.5e", header=header
    )
    print(f"Results written to {args.output_dir}")
    print(
        "Reuter and Scheffler (2006) at 600 K, 1 atm O2 and 7 atm CO,"
        " the most active conditions:"
    )
    print(
        "  TOF 2.2e+04; br: 0.94 O, 0.06 CO; cus: 0.26 O, 0.73 CO;"
        " share of CO cus + O cus: 0.86"
    )

    if args.plot:
        plot(results, args.output_dir / "ruo2_co_oxidation.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
