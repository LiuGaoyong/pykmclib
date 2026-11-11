#include "common.h"

#include "ratecalculator.h"

namespace {

// Trampoline: lets Python classes override the two C++ callbacks that the
// simulation invokes from inside the KMC loop.
class PyRateCalculator : public RateCalculator {
public:
    using RateCalculator::RateCalculator;

    double backendRateCallback(const std::vector<double> geometry, const int len,
                               const std::vector<std::string> &types_before,
                               const std::vector<std::string> &types_after, const double rate_constant,
                               const int process_number, const double global_x, const double global_y,
                               const double global_z) const override {
        PYBIND11_OVERRIDE(double, RateCalculator, backendRateCallback, geometry, len, types_before, types_after,
                          rate_constant, process_number, global_x, global_y, global_z);
    }

    double backendRateCallbackBuckets(const std::vector<double> geometry, const int len,
                                      const std::vector<TypeBucket> &occupation,
                                      const std::vector<TypeBucket> &update,
                                      const std::vector<std::string> &type_map, const double rate_constant,
                                      const int process_number, const double global_x, const double global_y,
                                      const double global_z) const override {
        PYBIND11_OVERRIDE(double, RateCalculator, backendRateCallbackBuckets, geometry, len, occupation, update,
                          type_map, rate_constant, process_number, global_x, global_y, global_z);
    }
};

class PySimpleDummyBaseClass : public SimpleDummyBaseClass {
public:
    using SimpleDummyBaseClass::SimpleDummyBaseClass;

    std::string whoAmI() const override {
        PYBIND11_OVERRIDE(std::string, SimpleDummyBaseClass, whoAmI);
    }
};

}  // namespace

void bind_ratecalculator(py::module_ &m) {
    py::class_<RateCalculator, PyRateCalculator>(m, "RateCalculator")
        .def(py::init<>())
        .def("backendRateCallback", &RateCalculator::backendRateCallback, py::arg("geometry"), py::arg("len"),
             py::arg("types_before"), py::arg("types_after"), py::arg("rate_constant"), py::arg("process_number"),
             py::arg("global_x"), py::arg("global_y"), py::arg("global_z"))
        .def("backendRateCallbackBuckets", &RateCalculator::backendRateCallbackBuckets, py::arg("geometry"),
             py::arg("len"), py::arg("occupation"), py::arg("update"), py::arg("type_map"),
             py::arg("rate_constant"), py::arg("process_number"), py::arg("global_x"), py::arg("global_y"),
             py::arg("global_z"));

    py::class_<SimpleDummyBaseClass, PySimpleDummyBaseClass>(m, "SimpleDummyBaseClass")
        .def(py::init<>())
        .def("whoAmI", &SimpleDummyBaseClass::whoAmI);

    m.def("callWhoAmI", &callWhoAmI, py::arg("obj"));
    m.def("getRate", &getRate, py::arg("rate_calculator"), py::arg("geometry"), py::arg("types_before"),
          py::arg("types_after"), py::arg("rate_constant"), py::arg("process_number"), py::arg("global_x"),
          py::arg("global_y"), py::arg("global_z"));
}
