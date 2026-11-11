#ifndef PYKMCLIB_BINDINGS_COMMON_H
#define PYKMCLIB_BINDINGS_COMMON_H

// Shared includes for the pybind11 binding translation units.
//
// Everything the bindings touch lives in the pristine upstream tree; this
// directory only adds the Python-visible layer.  Containers are converted by
// pybind11's stl.h (Python lists/dicts), which is why the SWIG-style
// StdVector* names are provided as plain Python façade classes in
// src/pykmclib/Backend/Backend.py instead of as opaque C++ types.

#include <map>
#include <string>
#include <utility>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/operators.h>
#include <pybind11/stl.h>

#include "coordinate.h"
#include "typebucket.h"
#include "configuration.h"
#include "process.h"
#include "customrateprocess.h"

namespace py = pybind11;

void bind_coordinate(py::module_ &m);
void bind_typebucket(py::module_ &m);
void bind_configuration(py::module_ &m);
void bind_latticemap(py::module_ &m);
void bind_process(py::module_ &m);
void bind_interactions(py::module_ &m);
void bind_latticemodel(py::module_ &m);
void bind_simulationtimer(py::module_ &m);
void bind_ontheflymsd(py::module_ &m);
void bind_ratecalculator(py::module_ &m);
void bind_mpicommons(py::module_ &m);
void bind_random(py::module_ &m);
void bind_custom(py::module_ &m);

#endif  // PYKMCLIB_BINDINGS_COMMON_H
