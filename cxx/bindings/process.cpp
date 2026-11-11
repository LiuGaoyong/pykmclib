#include "common.h"

#include "matchlist.h"
#include "matchlistentry.h"

void bind_process(py::module_ &m) {
    py::class_<ProcessBucketMatchListEntry>(m, "ProcessBucketMatchListEntry")
        .def_readwrite("match_types", &ProcessBucketMatchListEntry::match_types,
                       py::return_value_policy::reference_internal)
        .def_readwrite("update_types", &ProcessBucketMatchListEntry::update_types,
                       py::return_value_policy::reference_internal)
        .def_readwrite("has_move_coordinate", &ProcessBucketMatchListEntry::has_move_coordinate)
        .def_readwrite("index", &ProcessBucketMatchListEntry::index)
        .def_readwrite("distance", &ProcessBucketMatchListEntry::distance)
        .def_readwrite("coordinate", &ProcessBucketMatchListEntry::coordinate,
                       py::return_value_policy::reference_internal)
        .def_readwrite("move_coordinate", &ProcessBucketMatchListEntry::move_coordinate,
                       py::return_value_policy::reference_internal);

    py::class_<Process>(m, "Process")
        .def(py::init<const Configuration &, const Configuration &, const double, const std::vector<int> &,
                      const std::vector<int> &, const std::vector<Coordinate> &, const int>(),
             py::arg("first"), py::arg("second"), py::arg("rate"), py::arg("basis_sites"),
             py::arg("move_origins") = std::vector<int>(), py::arg("move_vectors") = std::vector<Coordinate>(),
             py::arg("process_number") = -1)
        .def("totalRate", &Process::totalRate)
        .def("cacheRate", &Process::cacheRate)
        .def("rateConstant", &Process::rateConstant)
        .def("nSites", &Process::nSites)
        // Upstream's verbose initial-match report prints this, and the SWIG
        // proxy printed as a tuple.
        .def("sites",
             [](const Process &p) {
                 const std::vector<int> &sites = p.sites();
                 py::tuple result(sites.size());
                 for (size_t i = 0; i < sites.size(); ++i) {
                     result[i] = sites[i];
                 }
                 return result;
             })
        .def("affectedIndices", [](const Process &p) { return p.affectedIndices(); })
        .def("basisSites", [](const Process &p) { return p.basisSites(); })
        .def("idMoves", [](Process &p) { return p.idMoves(); })
        .def("cutoff", &Process::cutoff)
        .def("range", &Process::range)
        .def("processNumber", &Process::processNumber)
        .def("bucketProcess", &Process::bucketProcess)
        .def("isListed", &Process::isListed, py::arg("index"))
        .def("processMatchList", [](const Process &p) { return p.processMatchList(); })
        .def("__repr__", [](const Process &p) {
            return "Process(number=" + std::to_string(p.processNumber()) +
                   ", rate=" + std::to_string(p.rateConstant()) + ")";
        });

    py::class_<CustomRateProcess, Process>(m, "CustomRateProcess")
        .def(py::init<const Configuration &, const Configuration &, const double, const std::vector<int> &,
                      const double, const std::vector<int> &, const std::vector<Coordinate> &, const int,
                      const bool>(),
             py::arg("first"), py::arg("second"), py::arg("rate"), py::arg("basis_sites"), py::arg("cutoff"),
             py::arg("move_origins") = std::vector<int>(), py::arg("move_vectors") = std::vector<Coordinate>(),
             py::arg("process_number") = -1, py::arg("cache_rate") = false)
        .def("__repr__", [](const CustomRateProcess &p) {
            return "CustomRateProcess(number=" + std::to_string(p.processNumber()) +
                   ", cutoff=" + std::to_string(p.cutoff()) + ")";
        });
}
