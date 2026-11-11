"""pykmclib - lattice kinetic Monte Carlo simulations with a C++ backend.

pykmclib is a re-packaging and Python-side re-development of *KMCLib*, the
general framework for lattice kinetic Monte Carlo (kMC) simulations by Mikael
Leetmaa.  The computationally heavy part is the original KMCLib C++ code,
exposed to Python with pybind11; the Python API follows upstream KMCLib, so the
upstream manual and examples apply with ``KMCLib`` renamed to ``pykmclib``.

Please cite the KMCLib papers when publishing results:

    Mikael Leetmaa and Natalia V. Skorodumova,
    "KMCLib: A general framework for lattice kinetic Monte Carlo (KMC)
    simulations", Comput. Phys. Commun. 185 (2014) 2340.
    DOI: 10.1016/j.cpc.2014.04.017

pykmclib is a derivative work of KMCLib (Copyright (c) 2012-2016 Mikael
Leetmaa, GPL-3.0-or-later) and is distributed under the same terms.
"""

# Copyright (c)  2013-2015  Mikael Leetmaa
#
# This file is part of the KMCLib project distributed under the terms of the
# GNU General Public License version 3, see <http://www.gnu.org/licenses/>.
#

import atexit

__version__ = "0.0.1"

# Check for ATK-Python support.
__atkpython__ = True
try:
    from NanoLanguage import *  # noqa: F401,F403
except Exception:
    __atkpython__ = False

from .Analysis.Composition import Composition
from .Analysis.OnTheFlyMSD import OnTheFlyMSD
from .Analysis.ProcessStatistics import ProcessStatistics
from .Analysis.TimeStepDistribution import TimeStepDistribution
from .Backend.Backend import MPICommons
from .CoreComponents.KMCBucketProcess import KMCBucketProcess
from .CoreComponents.KMCConfiguration import KMCConfiguration
from .CoreComponents.KMCControlParameters import KMCControlParameters
from .CoreComponents.KMCInteractions import KMCInteractions
from .CoreComponents.KMCLattice import KMCLattice
from .CoreComponents.KMCLatticeModel import KMCLatticeModel
from .CoreComponents.KMCLocalConfiguration import KMCLocalConfiguration
from .CoreComponents.KMCProcess import KMCProcess
from .CoreComponents.KMCUnitCell import KMCUnitCell
from .PluginInterfaces.KMCAnalysisPlugin import KMCAnalysisPlugin
from .PluginInterfaces.KMCBreakerPlugin import KMCBreakerPlugin
from .PluginInterfaces.KMCRateCalculatorPlugin import KMCRateCalculatorPlugin
from .Utilities.SaveAndReadUtilities import KMCConfigurationFromScript, KMCInteractionsFromScript

__all__ = [
    "KMCLocalConfiguration",
    "KMCInteractions",
    "KMCConfiguration",
    "KMCLattice",
    "KMCLatticeModel",
    "KMCUnitCell",
    "KMCControlParameters",
    "KMCInteractionsFromScript",
    "KMCConfigurationFromScript",
    "KMCRateCalculatorPlugin",
    "KMCAnalysisPlugin",
    "KMCBreakerPlugin",
    "KMCProcess",
    "KMCBucketProcess",
    "OnTheFlyMSD",
    "TimeStepDistribution",
    "Composition",
    "ProcessStatistics",
    "MPICommons",
    "__version__",
]

# Initialize MPI once, and finalize it on interpreter exit.  (Upstream also
# printed a banner here; pykmclib keeps the import side-effect free.)
MPICommons.init()


def _finalize_mpi():
    MPICommons.finalize()


atexit.register(_finalize_mpi)
