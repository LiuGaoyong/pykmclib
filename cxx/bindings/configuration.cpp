#include "common.h"

void bind_configuration(py::module_ &m) {
    py::class_<Configuration>(m, "Configuration")
        .def(py::init<const std::vector<std::vector<double>> &, const std::vector<std::vector<std::string>> &,
                      const std::map<std::string, int> &>(),
             py::arg("coordinates"), py::arg("elements"), py::arg("possible_types"))
        .def("coordinates", &Configuration::coordinates)
        .def("atomIDCoordinates", &Configuration::atomIDCoordinates)
        .def("atomIdCoordinates", &Configuration::atomIdCoordinates)
        .def("elements", &Configuration::elements)
        .def("atomIDElements", &Configuration::atomIDElements)
        .def("types", &Configuration::types)
        .def("atomID", &Configuration::atomID)
        .def("movedAtomIDs", &Configuration::movedAtomIDs)
        .def("recentMoveVectors", &Configuration::recentMoveVectors)
        .def("particlesPerType", &Configuration::particlesPerType)
        .def("latestEventProcess", &Configuration::latestEventProcess)
        .def("latestEventSite", &Configuration::latestEventSite)
        .def("typeName", &Configuration::typeName, py::arg("type"))
        .def("typeNames", &Configuration::typeNames)
        .def("setUpdateInfo", &Configuration::setUpdateInfo, py::arg("update_info"))
        .def("updateInfo", &Configuration::updateInfo)
        .def("possibleTypes", &Configuration::possibleTypes)
        .def("__repr__", [](const Configuration &c) {
            return "Configuration(" + std::to_string(c.coordinates().size()) + " sites, " +
                   std::to_string(c.possibleTypes().size()) + " types)";
        });
}
