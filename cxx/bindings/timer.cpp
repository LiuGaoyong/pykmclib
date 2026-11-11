#include "common.h"

#include "simulationtimer.h"

void bind_simulationtimer(py::module_ &m) {
    py::class_<SimulationTimer>(m, "SimulationTimer")
        .def(py::init<>())
        .def("propagateTime", &SimulationTimer::propagateTime, py::arg("total_rate"))
        .def("simulationTime", &SimulationTimer::simulationTime);
}
