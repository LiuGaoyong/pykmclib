#include "common.h"

namespace {

double coord_get(const Coordinate &c, int i) {
    if (i < 0 || i > 2) {
        throw py::index_error("Coordinate index out of range.");
    }
    return c[i];
}

void coord_set(Coordinate &c, int i, const double value) {
    if (i < 0 || i > 2) {
        throw py::index_error("Coordinate index out of range.");
    }
    c[i] = value;
}

}  // namespace

void bind_coordinate(py::module_ &m) {
    py::class_<Coordinate>(m, "Coordinate")
        .def(py::init<>())
        .def(py::init<double, double, double>(), py::arg("x"), py::arg("y"), py::arg("z"))
        .def("x", [](const Coordinate &c) { return static_cast<double>(c.x()); })
        .def("y", [](const Coordinate &c) { return static_cast<double>(c.y()); })
        .def("z", [](const Coordinate &c) { return static_cast<double>(c.z()); })
        .def("norm", &Coordinate::norm)
        .def("dot", &Coordinate::dot, py::arg("other"))
        .def("outerProdDiag", &Coordinate::outerProdDiag, py::arg("other"))
        .def("distance", &Coordinate::distance, py::arg("other"))
        .def("distanceToOrigin", &Coordinate::distanceToOrigin)
        .def("data", &Coordinate::data)
        .def("print", &Coordinate::print)
        .def("__getitem__", &coord_get)
        .def("__setitem__", &coord_set)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self < py::self)
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(py::self += py::self)
        .def("__copy__", [](const Coordinate &c) { return Coordinate(c); })
        .def("__deepcopy__", [](const Coordinate &c, py::dict) { return Coordinate(c); }, py::arg("memo"))
        .def(py::self * double())
        .def("__repr__",
             [](const Coordinate &c) {
                 return "Coordinate(" + std::to_string(c.x()) + ", " + std::to_string(c.y()) + ", " +
                        std::to_string(c.z()) + ")";
             })
        .def("__str__",
             [](const Coordinate &c) {
                 return "Coordinate(" + std::to_string(c.x()) + ", " + std::to_string(c.y()) + ", " +
                        std::to_string(c.z()) + ")";
             });
}
