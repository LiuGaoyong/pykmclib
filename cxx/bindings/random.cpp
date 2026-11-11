#include "common.h"

#include "random.h"

void bind_random(py::module_ &m) {
    // The Python front end refers to these as Backend.MT, Backend.MINSTD, ...
    m.attr("MT") = py::int_(static_cast<int>(MT));
    m.attr("MINSTD") = py::int_(static_cast<int>(MINSTD));
    m.attr("RANLUX24") = py::int_(static_cast<int>(RANLUX24));
    m.attr("RANLUX48") = py::int_(static_cast<int>(RANLUX48));
    m.attr("DEVICE") = py::int_(static_cast<int>(DEVICE));

    m.def(
        "setRngType",
        [](const int rng_type) { return setRngType(static_cast<RNG_TYPE>(rng_type)); },
        py::arg("rng_type"));
    m.def("seedRandom", &seedRandom, py::arg("time_seed"), py::arg("seed"));
    m.def("randomDouble01", &randomDouble01);
}
