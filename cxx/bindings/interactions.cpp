#include "common.h"

#include "interactions.h"
#include "latticemap.h"
#include "ratecalculator.h"

void bind_interactions(py::module_ &m) {
    py::class_<Interactions>(m, "Interactions")
        .def(py::init([](const std::vector<Process> &processes, const bool implicit_wildcards) {
                 return new Interactions(processes, implicit_wildcards);
             }),
             py::arg("processes"), py::arg("implicit_wildcards"))
        .def(py::init([](const std::vector<CustomRateProcess> &processes, const bool implicit_wildcards,
                         const RateCalculator &rate_calculator) {
                 return new Interactions(processes, implicit_wildcards, rate_calculator);
             }),
             py::arg("processes"), py::arg("implicit_wildcards"), py::arg("rate_calculator"),
             // Interactions only stores a reference to the calculator.
             py::keep_alive<1, 4>())
        .def("maxRange", &Interactions::maxRange)
        .def("useCustomRates", &Interactions::useCustomRates)
        .def("totalAvailableSites", &Interactions::totalAvailableSites)
        .def("totalRate", &Interactions::totalRate)
        .def("pickProcessIndex", &Interactions::pickProcessIndex)
        .def("pickProcess", &Interactions::pickProcess, py::return_value_policy::reference)
        .def("probabilityTable", &Interactions::probabilityTable)
        .def("updateProbabilityTable", &Interactions::updateProbabilityTable)
        .def("updateProcessMatchLists", &Interactions::updateProcessMatchLists, py::arg("configuration"),
             py::arg("lattice_map"))
        .def("clearMatching", &Interactions::clearMatching)
        .def("rateCalculator", &Interactions::rateCalculator, py::return_value_policy::reference_internal)
        .def("processes",
             [](Interactions &interactions) {
                 py::list result;
                 for (Process *process : interactions.processes()) {
                     result.append(py::cast(process, py::return_value_policy::reference));
                 }
                 return result;
             });
}
