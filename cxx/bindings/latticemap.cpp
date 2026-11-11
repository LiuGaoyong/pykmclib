#include "common.h"

#include "latticemap.h"

void bind_latticemap(py::module_ &m) {
    py::class_<LatticeMap>(m, "LatticeMap")
        .def(
            py::init([](const int n_basis, const std::vector<int> &repetitions,
                        const std::vector<bool> &periodic) {
                return LatticeMap(n_basis, repetitions, periodic);
            }),
            py::arg("n_basis"), py::arg("repetitions"), py::arg("periodic"))
        .def("nBasis", &LatticeMap::nBasis)
        .def("neighbourIndices", &LatticeMap::neighbourIndices, py::arg("index"), py::arg("shells") = 1)
        .def("supersetNeighbourIndices", &LatticeMap::supersetNeighbourIndices, py::arg("indices"),
             py::arg("shells"))
        .def("indicesFromCell", &LatticeMap::indicesFromCell, py::arg("i"), py::arg("j"), py::arg("k"))
        .def("indexFromMoveInfo", &LatticeMap::indexFromMoveInfo, py::arg("index"), py::arg("i"), py::arg("j"),
             py::arg("k"), py::arg("basis"))
        .def("indexToCell",
             [](const LatticeMap &map, const int index) {
                 int i = 0;
                 int j = 0;
                 int k = 0;
                 map.indexToCell(index, i, j, k);
                 return py::make_tuple(i, j, k);
             },
             py::arg("index"))
        .def("basisSiteFromIndex", &LatticeMap::basisSiteFromIndex, py::arg("index"))
        .def("periodicA", &LatticeMap::periodicA)
        .def("periodicB", &LatticeMap::periodicB)
        .def("periodicC", &LatticeMap::periodicC)
        .def("repetitionsA", &LatticeMap::repetitionsA)
        .def("repetitionsB", &LatticeMap::repetitionsB)
        .def("repetitionsC", &LatticeMap::repetitionsC)
        .def("wrap",
             [](const LatticeMap &map, const Coordinate &c) {
                 Coordinate wrapped(c);
                 map.wrap(wrapped);
                 return wrapped;
             },
             py::arg("coordinate"))
        .def("wrapCell",
             [](const LatticeMap &map, const Coordinate &c, const int direction) {
                 Coordinate wrapped(c);
                 map.wrap(wrapped, direction);
                 return wrapped;
             },
             py::arg("coordinate"), py::arg("direction"));
}
