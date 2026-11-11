#include "common.h"

#include "interactions.h"
#include "latticemap.h"
#include "latticemodel.h"
#include "simulationtimer.h"

void bind_latticemodel(py::module_ &m) {
    py::class_<LatticeModel>(m, "LatticeModel")
        .def(py::init([](Configuration &configuration, SimulationTimer &simulation_timer,
                         const LatticeMap &lattice_map, const Interactions &interactions) {
                 return new LatticeModel(configuration, simulation_timer, lattice_map, interactions);
             }),
             py::arg("configuration"), py::arg("simulation_timer"), py::arg("lattice_map"), py::arg("interactions"),
             // The model keeps references to the configuration and the timer.
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>(), py::keep_alive<1, 5>())
        .def("singleStep", &LatticeModel::singleStep)
        .def("propagateTime", &LatticeModel::propagateTime)
        .def("interactions", &LatticeModel::interactions, py::return_value_policy::reference_internal)
        .def("configuration", &LatticeModel::configuration, py::return_value_policy::reference_internal)
        .def("latticeMap", &LatticeModel::latticeMap, py::return_value_policy::reference_internal);
}
