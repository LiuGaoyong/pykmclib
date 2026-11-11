#include "common.h"

#include "mpicommons.h"

void bind_mpicommons(py::module_ &m) {
    py::class_<MPICommons>(m, "MPICommons")
        .def_static("init", &MPICommons::init)
        .def_static("finalize", &MPICommons::finalize)
        .def_static("myRank", &MPICommons::myRank, py::arg("comm") = static_cast<int>(MPI_COMM_WORLD))
        .def_static("size", &MPICommons::size, py::arg("comm") = static_cast<int>(MPI_COMM_WORLD))
        .def_static("barrier", &MPICommons::barrier, py::arg("comm") = static_cast<int>(MPI_COMM_WORLD))
        .def_static("isMaster", &MPICommons::isMaster, py::arg("comm") = static_cast<int>(MPI_COMM_WORLD));
}
