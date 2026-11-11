#include "common.h"

#include "ontheflymsd.h"

void bind_ontheflymsd(py::module_ &m) {
    py::class_<OnTheFlyMSD>(m, "OnTheFlyMSD")
        .def(py::init<const Configuration &, const int, const int, const double, const double, const std::string,
                      const std::vector<Coordinate> &, const int>(),
             py::arg("configuration"), py::arg("history_steps"), py::arg("n_bins"), py::arg("t_max"),
             py::arg("t0"), py::arg("track_type"), py::arg("abc_to_xyz"), py::arg("blocksize") = 0,
             // The MSD calculator keeps a reference to the configuration.
             py::keep_alive<1, 2>())
        .def("registerStep", &OnTheFlyMSD::registerStep, py::arg("time"), py::arg("configuration"))
        .def("histogramBuffer", &OnTheFlyMSD::histogramBuffer)
        .def("histogramBufferSqr", &OnTheFlyMSD::histogramBufferSqr)
        .def("histogramBinCounts", &OnTheFlyMSD::histogramBinCounts)
        .def("historyStepsHistogramBinCounts", &OnTheFlyMSD::historyStepsHistogramBinCounts)
        .def("hstepCounts", &OnTheFlyMSD::hstepCounts);
}
