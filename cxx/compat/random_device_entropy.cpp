// Link-time replacement for std::random_device::entropy() in portable Linux
// wheels (enabled with -DKMC_PORTABLE_LINUX_WHEEL=ON, see cxx/CMakeLists.txt).
//
// KMCLib's random.cpp calls std::random_device::entropy() to decide whether
// the DEVICE generator is usable.  With libstdc++ that call is the out-of-line
// function std::random_device::_M_getentropy(), exported with the symbol
// version GLIBCXX_3.4.25.  The manylinux_2_28 policy only allows symbols up to
// GLIBCXX_3.4.24, so auditwheel refuses to tag a wheel that references it.
//
// The module is therefore linked with
//     --wrap=_ZNKSt13random_device13_M_getentropyEv
// which redirects that one reference to the function below, and the extension
// no longer depends on the versioned symbol.
//
// The value matches what libstdc++ itself reports for a hardware or kernel
// entropy source: the number of bits in random_device::result_type.  On Linux
// with glibc, std::random_device is always backed by such a source (it throws
// on construction otherwise), so the DEVICE generator is reported as usable.

#include <limits>
#include <random>

extern "C" double __wrap__ZNKSt13random_device13_M_getentropyEv(const std::random_device *) noexcept {
    return static_cast<double>(std::numeric_limits<std::random_device::result_type>::digits);
}
