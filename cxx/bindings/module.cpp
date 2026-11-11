#include "common.h"

PYBIND11_MODULE(_backend, m) {
    m.doc() =
        "C++ backend of pykmclib (a repackaging of KMCLib, GPL-3.0-or-later).\n"
        "Low level module: the Python facing API lives in pykmclib.Backend.";

    bind_mpicommons(m);
    bind_random(m);
    bind_coordinate(m);
    bind_typebucket(m);
    bind_configuration(m);
    bind_latticemap(m);
    bind_process(m);
    bind_ratecalculator(m);
    bind_custom(m);
    bind_interactions(m);
    bind_simulationtimer(m);
    bind_ontheflymsd(m);
    bind_latticemodel(m);
}
