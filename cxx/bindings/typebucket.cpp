#include "common.h"

namespace {

int typebucket_get(const TypeBucket &tb, int i) {
    if (i < 0 || i >= tb.size()) {
        throw py::index_error("TypeBucket index out of range.");
    }
    return tb[i];
}

void typebucket_set(TypeBucket &tb, int i, const int value) {
    if (i < 0 || i >= tb.size()) {
        throw py::index_error("TypeBucket index out of range.");
    }
    tb[i] = value;
}

}  // namespace

void bind_typebucket(py::module_ &m) {
    py::class_<TypeBucket>(m, "TypeBucket")
        .def(py::init<>())
        .def(py::init<int>(), py::arg("size"))
        .def("size", &TypeBucket::size)
        .def("__len__", &TypeBucket::size)
        .def("__getitem__", &typebucket_get)
        .def("__setitem__", &typebucket_set)
        .def("add", &TypeBucket::add, py::arg("other"))
        .def("identical", &TypeBucket::identical, py::arg("other"))
        .def("greaterOrEqual", &TypeBucket::greaterOrEqual, py::arg("other"))
        .def("lessThan", &TypeBucket::lessThan, py::arg("other"))
        .def("match", &TypeBucket::match, py::arg("other"))
        .def(py::self == py::self)
        .def(py::self != py::self)
        // Copy support: the Python side pre-fills std::vector proxies with
        // independent elements, which requires deepcopy to work.
        .def("__copy__", [](const TypeBucket &tb) { return TypeBucket(tb); })
        .def("__deepcopy__", [](const TypeBucket &tb, py::dict) { return TypeBucket(tb); }, py::arg("memo"))
        .def("__repr__",
             [](const TypeBucket &tb) {
                 std::string out = "TypeBucket(";
                 for (int i = 0; i < tb.size(); ++i) {
                     if (i != 0) {
                         out += ", ";
                     }
                     out += std::to_string(tb[i]);
                 }
                 return out + ")";
             });
}
