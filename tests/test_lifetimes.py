"""Object lifetimes across the pybind11 boundary.

The C++ core hands out raw pointers to objects owned by other objects; the
bindings have to keep the owner alive for as long as Python holds the pointer.
"""

from __future__ import annotations

import gc
import sys

from test_simulation import build_model


def test_processes_keep_their_interactions_alive():
    model = build_model()
    interactions = model._backend().interactions()

    before = sys.getrefcount(interactions)
    processes = interactions.processes()
    assert len(processes) == 2
    # Every returned process holds a reference to the owning Interactions.
    assert sys.getrefcount(interactions) == before + len(processes)

    first = processes[0]
    del processes, interactions, model
    gc.collect()
    assert first.rateConstant() == 4.0


def test_picked_process_keeps_its_interactions_alive():
    model = build_model()
    backend = model._backend()
    interactions = backend.interactions()
    interactions.updateProbabilityTable()

    before = sys.getrefcount(interactions)
    picked = interactions.pickProcess()
    assert sys.getrefcount(interactions) == before + 1

    del interactions, backend, model
    gc.collect()
    assert picked.rateConstant() in (1.0, 4.0)
