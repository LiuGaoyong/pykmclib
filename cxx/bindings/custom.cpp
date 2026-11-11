#include "common.h"

#include "bucketstestcalculator.h"
#include "isingtestcalculator.h"
#include "ratecalculator.h"

void bind_custom(py::module_ &m) {
    py::class_<BucketsTestCalculator, RateCalculator>(m, "BucketsTestCalculator")
        .def(py::init<const Configuration &>(), py::arg("config"),
             // The calculator keeps a reference to the configuration.
             py::keep_alive<1, 2>())
        .def("cutoff", &BucketsTestCalculator::cutoff)
        .def("cacheRates", &BucketsTestCalculator::cacheRates)
        .def("excludeFromCaching", &BucketsTestCalculator::excludeFromCaching);

    py::class_<IsingTestCalculator, RateCalculator>(m, "IsingTestCalculator")
        .def(py::init<const Configuration &>(), py::arg("config"), py::keep_alive<1, 2>())
        .def("cutoff", &IsingTestCalculator::cutoff)
        .def("cacheRates", &IsingTestCalculator::cacheRates)
        .def("excludeFromCaching", &IsingTestCalculator::excludeFromCaching);
}
